"""
Confirmation Node

Pharmacy domain node for confirming customer debt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.application.use_cases.confirm_debt import (
    ConfirmDebtRequest,
    ConfirmDebtUseCase,
)

if TYPE_CHECKING:
    from app.clients.pharmacy_erp_client import PharmacyERPClient

logger = logging.getLogger(__name__)


class ConfirmationNode(BaseAgent):
    """Pharmacy node specialized in debt confirmation."""

    def __init__(
        self,
        erp_client: PharmacyERPClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize confirmation node.

        Args:
            erp_client: Pharmacy ERP client instance
            config: Node configuration
        """
        super().__init__("confirmation_node", config or {})
        self._erp_client = erp_client
        self._use_case: ConfirmDebtUseCase | None = None

    def _get_use_case(self) -> ConfirmDebtUseCase:
        """Get or create the use case with lazy initialization."""
        if self._use_case is None:
            if self._erp_client is None:
                from app.clients.pharmacy_erp_client import PharmacyERPClient

                self._erp_client = PharmacyERPClient()
            self._use_case = ConfirmDebtUseCase(self._erp_client)
        return self._use_case

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process debt confirmation.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            debt_id = state_dict.get("debt_id")
            customer_id = state_dict.get("customer_id") or state_dict.get("user_id")

            if not debt_id:
                return self._handle_no_debt_id()

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
                request = ConfirmDebtRequest(
                    debt_id=debt_id,
                    customer_id=customer_id,
                )
                response = await use_case.execute(request)

            if not response.success or not response.confirmed:
                return self._handle_confirmation_failed(
                    response.error or "Confirmation failed",
                    state_dict,
                )

            # Confirmation successful
            total_debt = state_dict.get("total_debt", 0)

            return {
                "messages": [
                    {
                        "role": "assistant",
                        "content": (
                            f"Tu deuda de **${total_debt:,.2f}** ha sido confirmada.\n\n"
                            "Para generar la factura, escribe *FACTURA*."
                        ),
                    }
                ],
                "current_agent": self.name,
                "agent_history": [self.name],
                "debt_status": "confirmed",
                "awaiting_confirmation": False,
                "confirmation_received": True,
                "workflow_step": "confirmed",
                "is_complete": False,
            }

        except Exception as e:
            logger.error(f"Error in confirmation node: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    def _handle_no_debt_id(self) -> dict[str, Any]:
        """Handle missing debt ID."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No hay una deuda seleccionada para confirmar. "
                        "Por favor primero consulta tu deuda."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

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
        }

    def _handle_confirmation_failed(
        self,
        error: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle confirmation failure."""
        logger.warning(f"Debt confirmation failed: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No se pudo confirmar la deuda. "
                        "Por favor intenta de nuevo o contacta a soporte."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Confirmation node error: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, tuve un problema procesando la confirmacion. "
                        "Por favor intenta de nuevo."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
