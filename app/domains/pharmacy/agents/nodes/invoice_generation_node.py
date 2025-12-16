"""
Invoice/Receipt Generation Node

Pharmacy domain node for generating payment receipts via Plex ERP.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class InvoiceGenerationNode(BaseAgent):
    """
    Pharmacy node specialized in receipt/invoice generation.

    Uses PlexClient to create payment receipts in the Plex ERP system.
    Requires that the debt has been confirmed (debt_status="confirmed").
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize invoice generation node.

        Args:
            plex_client: PlexClient instance for API calls
            config: Node configuration
        """
        super().__init__("invoice_generation_node", config or {})
        self._plex_client = plex_client

    def _get_plex_client(self) -> PlexClient:
        """Get or create Plex client."""
        if self._plex_client is None:
            from app.clients.plex_client import PlexClient
            self._plex_client = PlexClient()
        return self._plex_client

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process receipt/invoice generation.

        Args:
            message: User message
            state_dict: Current state dictionary

        Returns:
            State updates
        """
        try:
            debt_id = state_dict.get("debt_id")
            plex_customer_id = state_dict.get("plex_customer_id")
            debt_status = state_dict.get("debt_status")

            if not debt_id:
                return self._handle_no_debt_id()

            if not plex_customer_id:
                return self._handle_no_customer()

            # Check if debt is confirmed
            if debt_status != "confirmed":
                return self._handle_not_confirmed()

            # Get payment amount (partial or full)
            total_debt = state_dict.get("total_debt", 0) or 0
            payment_amount = state_dict.get("payment_amount") or total_debt
            is_partial = state_dict.get("is_partial_payment", False)
            customer_name = state_dict.get("customer_name", "Cliente")

            # Convert to Decimal for Plex API
            amount = Decimal(str(payment_amount))

            if amount <= 0:
                return self._handle_no_amount()

            # Calculate remaining balance for partial payments
            remaining_balance = Decimal(str(total_debt)) - amount if is_partial else Decimal("0")

            logger.info(
                f"Creating receipt: customer_id={plex_customer_id}, "
                f"amount=${amount}, total_debt=${total_debt}, is_partial={is_partial}"
            )

            plex_client = self._get_plex_client()

            # Build items from debt data if available
            items = self._build_receipt_items(state_dict.get("debt_data"))

            async with plex_client:
                receipt_data = await plex_client.create_receipt(
                    customer_id=plex_customer_id,
                    amount=amount,  # Use payment_amount instead of total_debt
                    items=items,
                )

            # Format response
            receipt_number = receipt_data.get(
                "numero_recibo",
                receipt_data.get("id", "N/A")
            )

            response_text = self._format_receipt_response(
                receipt_number=str(receipt_number),
                amount_paid=float(amount),
                total_debt=float(total_debt),
                remaining_balance=float(remaining_balance),
                customer_name=customer_name,
                is_partial=is_partial,
            )

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "receipt_number": str(receipt_number),
                "invoice_number": str(receipt_number),
                "debt_status": "invoiced",
                "workflow_step": "invoiced",
                "is_complete": True,
                "remaining_balance": float(remaining_balance),
            }

        except Exception as e:
            logger.error(f"Error in invoice generation node: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    def _build_receipt_items(
        self,
        debt_data: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Build receipt items from debt data."""
        if not debt_data:
            return []

        items = debt_data.get("items", [])
        receipt_items = []

        for item in items:
            receipt_items.append({
                "descripcion": item.get("description", "Item"),
                "importe": item.get("amount", 0),
                "cantidad": item.get("quantity", 1),
            })

        return receipt_items

    def _format_receipt_response(
        self,
        receipt_number: str,
        amount_paid: float,
        total_debt: float,
        remaining_balance: float,
        customer_name: str,
        is_partial: bool = False,
    ) -> str:
        """Format receipt response message for full or partial payment."""
        if is_partial:
            return f"""**Recibo de Pago Parcial Generado** ✅

{customer_name}, tu recibo de pago parcial ha sido generado exitosamente.

📄 **Número de Recibo:** {receipt_number}
💰 **Monto Pagado:** ${amount_paid:,.2f}
📊 **Deuda Total:** ${total_debt:,.2f}
⏳ **Saldo Pendiente:** ${remaining_balance:,.2f}

Gracias por tu pago. Recuerda que aún tienes un saldo pendiente de ${remaining_balance:,.2f}.

¿Hay algo más en que pueda ayudarte?"""
        else:
            return f"""**Recibo Generado** ✅

{customer_name}, tu recibo de pago ha sido generado exitosamente.

📄 **Número de Recibo:** {receipt_number}
💰 **Total Pagado:** ${amount_paid:,.2f}
✅ **Estado:** Deuda saldada completamente

Gracias por tu pago. ¿Hay algo más en que pueda ayudarte?"""

    def _handle_no_debt_id(self) -> dict[str, Any]:
        """Handle missing debt ID."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No hay una deuda seleccionada para generar recibo. "
                        "Por favor primero consulta y confirma tu deuda."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

    def _handle_no_customer(self) -> dict[str, Any]:
        """Handle missing customer identification."""
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

    def _handle_not_confirmed(self) -> dict[str, Any]:
        """Handle debt not confirmed."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "La deuda debe estar confirmada antes de generar el recibo. "
                        "Por favor confirma tu deuda primero respondiendo *SI*."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": False,
        }

    def _handle_no_amount(self) -> dict[str, Any]:
        """Handle zero or invalid amount."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No hay un monto válido para generar el recibo. "
                        "Por favor consulta tu deuda nuevamente."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Invoice generation node error: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, tuve un problema generando el recibo. "
                        "Por favor intenta de nuevo o contacta a la farmacia."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
