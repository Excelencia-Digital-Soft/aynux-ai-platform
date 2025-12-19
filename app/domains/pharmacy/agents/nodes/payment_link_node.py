"""
Payment Link Generation Node

Pharmacy domain node for generating Mercado Pago payment links.
Creates a Checkout Pro preference and sends the payment link to the customer.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from app.config.settings import get_settings
from app.core.agents import BaseAgent

if TYPE_CHECKING:
    from app.clients.mercado_pago_client import MercadoPagoClient

logger = logging.getLogger(__name__)


class PaymentLinkNode(BaseAgent):
    """
    Pharmacy node for generating Mercado Pago payment links.

    Creates a Checkout Pro preference and returns a payment URL
    that the customer can use to pay through Mercado Pago.

    Requires:
        - debt_status = "confirmed"
        - plex_customer_id set
        - payment_amount or total_debt set

    Produces:
        - mp_preference_id: Mercado Pago preference ID
        - mp_init_point: Payment link URL
        - mp_external_reference: Reference for webhook correlation
        - awaiting_payment: True
        - debt_status: "payment_pending"
    """

    def __init__(
        self,
        plex_client: Any = None,  # Accept for graph compatibility, not used
        mp_client: MercadoPagoClient | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize payment link node.

        Args:
            plex_client: PlexClient (accepted for graph compatibility, not used)
            mp_client: MercadoPagoClient instance (optional, created lazily)
            config: Node configuration
        """
        super().__init__("payment_link_node", config or {})
        self._mp_client = mp_client
        # Note: plex_client is accepted for graph initialization compatibility
        # but PaymentLinkNode uses MercadoPagoClient for payment link generation

    def _get_mp_client(self) -> MercadoPagoClient:
        """Get or create Mercado Pago client."""
        if self._mp_client is None:
            from app.clients.mercado_pago_client import MercadoPagoClient

            self._mp_client = MercadoPagoClient()
        return self._mp_client

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate Mercado Pago payment link for confirmed debt.

        Args:
            message: User message (not used, triggered by routing)
            state_dict: Current state dictionary

        Returns:
            State updates with payment link info
        """
        try:
            # Check if MP is enabled
            settings = get_settings()
            if not settings.MERCADO_PAGO_ENABLED:
                logger.warning("Mercado Pago integration is disabled")
                return self._handle_mp_disabled()

            # Validate prerequisites
            debt_status = state_dict.get("debt_status")
            if debt_status != "confirmed":
                logger.warning(f"Cannot generate payment link: debt_status={debt_status}")
                return self._handle_not_confirmed()

            plex_customer_id = state_dict.get("plex_customer_id")
            if not plex_customer_id:
                logger.warning("Cannot generate payment link: no plex_customer_id")
                return self._handle_no_customer()

            # Get payment details
            total_debt = state_dict.get("total_debt", 0) or 0
            payment_amount = state_dict.get("payment_amount") or total_debt
            is_partial = state_dict.get("is_partial_payment", False)
            customer_name = state_dict.get("customer_name", "Cliente")
            customer_phone = state_dict.get("customer_id")  # WhatsApp number
            debt_id = state_dict.get("debt_id", "unknown")

            amount = Decimal(str(payment_amount))
            if amount <= 0:
                logger.warning(f"Invalid payment amount: {amount}")
                return self._handle_invalid_amount()

            # Create external reference for webhook correlation
            # Format: customer_id:debt_id:uuid (allows webhook to identify transaction)
            unique_id = uuid.uuid4().hex[:8]
            external_reference = f"{plex_customer_id}:{debt_id}:{unique_id}"

            logger.info(
                f"Creating MP payment link: customer={plex_customer_id}, "
                f"amount=${amount}, is_partial={is_partial}, ref={external_reference}"
            )

            # Create Mercado Pago preference
            mp_client = self._get_mp_client()

            async with mp_client:
                preference = await mp_client.create_preference(
                    amount=amount,
                    description=f"Pago de deuda - {customer_name}",
                    external_reference=external_reference,
                    payer_phone=customer_phone,
                    payer_name=customer_name,
                )

            init_point = preference["init_point"]
            preference_id = preference["preference_id"]

            # Use sandbox URL in sandbox mode
            if settings.MERCADO_PAGO_SANDBOX and preference.get("sandbox_init_point"):
                init_point = preference["sandbox_init_point"]

            logger.info(f"MP preference created: {preference_id}, link={init_point[:50]}...")

            # Format response message
            response_text = self._format_payment_link_message(
                customer_name=customer_name,
                amount=float(amount),
                total_debt=float(total_debt),
                remaining_balance=float(total_debt - amount) if is_partial else 0.0,
                payment_url=init_point,
                is_partial=is_partial,
            )

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                # Mercado Pago context
                "mp_preference_id": preference_id,
                "mp_init_point": init_point,
                "mp_payment_status": "pending",
                "mp_external_reference": external_reference,
                # Workflow state
                "awaiting_payment": True,
                "debt_status": "payment_pending",
                "workflow_step": "payment_link_sent",
                "is_complete": True,  # Conversation ends, webhook handles the rest
            }

        except Exception as e:
            logger.error(f"Error generating payment link: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    def _format_payment_link_message(
        self,
        customer_name: str,
        amount: float,
        total_debt: float,
        remaining_balance: float,
        payment_url: str,
        is_partial: bool = False,
    ) -> str:
        """Format payment link message for WhatsApp."""
        if is_partial:
            return f"""**Link de Pago Parcial Generado**

{customer_name}, aqui esta tu link de pago:

**Monto a pagar:** ${amount:,.2f}
**Deuda total:** ${total_debt:,.2f}
**Saldo pendiente despues del pago:** ${remaining_balance:,.2f}

**Link de pago:**
{payment_url}

Haz clic en el link para pagar con Mercado Pago.

Recibiras una confirmacion automatica cuando el pago se procese.

_Este link es valido por 24 horas._"""
        else:
            return f"""**Link de Pago Generado**

{customer_name}, aqui esta tu link de pago:

**Monto a pagar:** ${amount:,.2f}

**Link de pago:**
{payment_url}

Haz clic en el link para pagar con Mercado Pago.

Recibiras una confirmacion automatica cuando el pago se procese.

_Este link es valido por 24 horas._"""

    def _handle_mp_disabled(self) -> dict[str, Any]:
        """Handle when Mercado Pago is disabled."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, el sistema de pagos en linea no esta disponible en este momento. "
                        "Por favor contacta directamente a la farmacia para realizar tu pago."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

    def _handle_not_confirmed(self) -> dict[str, Any]:
        """Handle when debt is not confirmed."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "La deuda debe estar confirmada antes de generar el link de pago. "
                        "Por favor confirma tu deuda primero respondiendo *SI*."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": False,
        }

    def _handle_no_customer(self) -> dict[str, Any]:
        """Handle when customer is not identified."""
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

    def _handle_invalid_amount(self) -> dict[str, Any]:
        """Handle when payment amount is invalid."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "El monto de pago no es valido. "
                        "Por favor consulta tu deuda nuevamente."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
        }

    def _handle_error(self, error: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Handle processing error."""
        logger.error(f"Payment link node error: {error}")
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, hubo un problema generando el link de pago. "
                        "Por favor intenta de nuevo en unos minutos o contacta a la farmacia."
                    ),
                }
            ],
            "current_agent": self.name,
            "error_count": state_dict.get("error_count", 0) + 1,
            "is_complete": False,
        }
