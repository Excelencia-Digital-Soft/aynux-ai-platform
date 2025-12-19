"""
Confirmation Node

Pharmacy domain node for confirming customer debt.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


class ConfirmationNode(BaseAgent):
    """
    Pharmacy node specialized in debt confirmation.

    This node handles user confirmation of their debt before proceeding
    to payment/receipt generation.
    """

    def __init__(
        self,
        plex_client: PlexClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize confirmation node.

        Args:
            plex_client: PlexClient instance (for future use)
            config: Node configuration
        """
        super().__init__("confirmation_node", config or {})
        self._plex_client = plex_client

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
            plex_customer_id = state_dict.get("plex_customer_id")

            if not debt_id:
                return self._handle_no_debt_id()

            if not plex_customer_id:
                return self._handle_no_customer()

            # Parse user response
            message_clean = message.strip().upper()

            if message_clean in ["SI", "SÍ", "YES", "S", "CONFIRMO", "CONFIRMAR"]:
                return self._confirm_debt(state_dict)
            elif message_clean in ["NO", "N", "CANCELAR"]:
                return self._cancel_confirmation()
            else:
                return self._request_clear_response()

        except Exception as e:
            logger.error(f"Error in confirmation node: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    def _confirm_debt(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle debt confirmation (full or partial payment) - auto-proceed to payment link."""
        total_debt = state_dict.get("total_debt", 0) or 0
        payment_amount = state_dict.get("payment_amount") or total_debt
        is_partial = state_dict.get("is_partial_payment", False)
        customer_name = state_dict.get("customer_name", "Cliente")
        auto_proceed = state_dict.get("auto_proceed_to_invoice", False)

        # Calculate remaining balance for partial payments
        remaining_balance = total_debt - payment_amount if is_partial else 0

        if is_partial:
            logger.info(
                f"Partial payment confirmed: customer={customer_name}, "
                f"payment=${payment_amount}, total_debt=${total_debt}, remaining=${remaining_balance}"
            )
            message = (
                f"Tu pago parcial de **${payment_amount:,.2f}** ha sido confirmado.\n\n"
                f"**Resumen:**\n"
                f"- Deuda total: ${total_debt:,.2f}\n"
                f"- Monto a pagar: ${payment_amount:,.2f}\n"
                f"- Saldo pendiente: ${remaining_balance:,.2f}\n\n"
                "Generando link de pago..."
            )
        else:
            logger.info(f"Full debt confirmed: customer={customer_name}, amount=${total_debt}")
            message = (
                f"Tu deuda de **${total_debt:,.2f}** ha sido confirmada.\n\n"
                "Generando link de pago..."
            )

        result = {
            "messages": [{"role": "assistant", "content": message}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "debt_status": "confirmed",
            "awaiting_confirmation": False,
            "confirmation_received": True,
            "workflow_step": "confirmed",
            "remaining_balance": remaining_balance,
        }

        # Auto-proceed to payment link generation
        # Always go to payment_link_node after confirmation
        result["next_agent"] = "payment_link_node"
        result["is_complete"] = False

        return result

    def _cancel_confirmation(self) -> dict[str, Any]:
        """Handle confirmation cancellation."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Entendido, la confirmación ha sido cancelada.\n\n"
                        "¿Hay algo más en que pueda ayudarte?"
                    ),
                }
            ],
            "current_agent": self.name,
            "awaiting_confirmation": False,
            "is_complete": True,
        }

    def _request_clear_response(self) -> dict[str, Any]:
        """Request clear yes/no response."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Por favor responde *SI* para confirmar tu deuda "
                        "o *NO* para cancelar."
                    ),
                }
            ],
            "current_agent": self.name,
            "awaiting_confirmation": True,
            "confirmation_received": False,
            "is_complete": False,
        }

    def _handle_no_debt_id(self) -> dict[str, Any]:
        """Handle missing debt ID."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "No hay una deuda seleccionada para confirmar. "
                        "Por favor primero consulta tu deuda escribiendo *DEUDA*."
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

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Confirmation node error: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, tuve un problema procesando la confirmación. "
                        "Por favor intenta de nuevo."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
        }
