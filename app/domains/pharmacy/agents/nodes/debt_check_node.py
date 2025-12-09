"""
Debt Check Node

Pharmacy domain node for checking customer debt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.application.use_cases.check_debt import (
    CheckDebtRequest,
    CheckDebtUseCase,
)

if TYPE_CHECKING:
    from app.clients.pharmacy_erp_client import PharmacyERPClient

logger = logging.getLogger(__name__)


class DebtCheckNode(BaseAgent):
    """Pharmacy node specialized in debt checking (Consulta Deuda)."""

    def __init__(
        self,
        erp_client: PharmacyERPClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize debt check node.

        Args:
            erp_client: Pharmacy ERP client instance
            config: Node configuration
        """
        super().__init__("debt_check_node", config or {})
        self._erp_client = erp_client
        self._use_case: CheckDebtUseCase | None = None

    def _get_use_case(self) -> CheckDebtUseCase:
        """Get or create the use case with lazy initialization."""
        if self._use_case is None:
            if self._erp_client is None:
                from app.clients.pharmacy_erp_client import PharmacyERPClient

                self._erp_client = PharmacyERPClient()
            self._use_case = CheckDebtUseCase(self._erp_client)
        return self._use_case

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process debt check queries.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            # Extract customer ID from state (phone number from WhatsApp)
            customer_id = state_dict.get("customer_id") or state_dict.get("user_id")

            if not customer_id:
                return self._handle_no_customer()

            # Execute use case (ensures _erp_client is initialized)
            use_case = self._get_use_case()

            # Need to use context manager for httpx client
            # _get_use_case() guarantees _erp_client is not None
            erp_client = self._erp_client
            if erp_client is None:
                return self._handle_error("ERP client not configured", state_dict)

            async with erp_client:
                request = CheckDebtRequest(customer_id=customer_id)
                response = await use_case.execute(request)

            if not response.success:
                return self._handle_error(response.error or "Unknown error", state_dict)

            if not response.has_debt:
                return self._handle_no_debt(customer_id)

            # Format debt response and set up confirmation flow
            debt = response.debt
            if debt is None:
                return self._handle_no_debt(customer_id)

            response_text = self._format_debt_response(debt)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "debt_id": debt.id,
                "debt_data": debt.to_dict(),
                "debt_status": debt.status.value,
                "total_debt": float(debt.total_debt),
                "has_debt": True,
                "workflow_step": "debt_checked",
                "awaiting_confirmation": True,  # Wait for user to confirm
                "is_complete": False,
            }

        except Exception as e:
            logger.error(f"Error in debt check node: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    def _format_debt_response(self, debt: Any) -> str:
        """Format debt information as user-friendly response."""
        items_text = self._format_items(debt.items)
        due_date_text = (
            debt.due_date.strftime("%d/%m/%Y") if debt.due_date else "No especificada"
        )

        return f"""**Consulta de Deuda**

Hola {debt.customer_name},

Tu deuda pendiente es de **${debt.total_debt:,.2f}**

**Detalle:**
{items_text}

Fecha de vencimiento: {due_date_text}

Para confirmar esta deuda y generar la factura, responde *SI*.
Para cancelar, responde *NO*."""

    def _format_items(self, items: list[Any]) -> str:
        """Format debt items."""
        if not items:
            return "- Sin detalle disponible"
        return "\n".join(
            [f"- {item.description}: ${float(item.amount):,.2f}" for item in items]
        )

    def _handle_no_customer(self) -> dict[str, Any]:
        """Handle missing customer ID."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No pude identificar tu cuenta. "
                        "Por favor contacta a soporte."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
            "has_debt": False,
        }

    def _handle_no_debt(self, customer_id: str) -> dict[str, Any]:
        """Handle no debt found."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No tienes deudas pendientes. "
                        "Hay algo mas en que pueda ayudarte?"
                    ),
                }
            ],
            "current_agent": self.name,
            "has_debt": False,
            "is_complete": True,
        }

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Debt check error: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, tuve un problema consultando tu deuda. "
                        "Por favor intenta de nuevo."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
