"""
Payment Link Generation Node

Pharmacy domain node for generating Mercado Pago payment links.
Creates a Checkout Pro preference and sends the payment link to the customer.

Implements CASO 4 from docs/pharmacy_flujo_mejorado_v2.md:
- Confirmation before generating payment link
- Partial payment support with amount validation
- Clear messages showing payment details and remaining balance

Requires pharmacy_id in state to load pharmacy-specific configuration from database.
The pharmacy_id is propagated from bypass routing when a BypassRule is linked to a pharmacy.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.mercado_pago_client import MercadoPagoClient
from app.core.agents import BaseAgent
from app.core.tenancy import PharmacyConfigService

if TYPE_CHECKING:
    from app.core.tenancy import PharmacyConfig

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
        - pharmacy_id set (propagated from bypass routing, for loading pharmacy config from DB)

    Produces:
        - mp_preference_id: Mercado Pago preference ID
        - mp_init_point: Payment link URL
        - mp_external_reference: Reference for webhook correlation (includes pharmacy_id)
        - awaiting_payment: True
        - debt_status: "payment_pending"
    """

    def __init__(
        self,
        plex_client: Any = None,  # Accept for graph compatibility, not used
        db_session_factory: Callable[[], AsyncSession] | None = None,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize payment link node.

        Args:
            plex_client: PlexClient (accepted for graph compatibility, not used)
            db_session_factory: Factory function to create async DB sessions
            config: Node configuration
        """
        super().__init__("payment_link_node", config or {})
        self._db_session_factory = db_session_factory
        # Note: plex_client is accepted for graph initialization compatibility
        # but PaymentLinkNode uses MercadoPagoClient for payment link generation

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
            # Validate pharmacy_id (required for DB config)
            pharmacy_id_str = state_dict.get("pharmacy_id")
            if not pharmacy_id_str:
                logger.error("Cannot generate payment link: no pharmacy_id in state")
                return self._handle_no_organization()

            from uuid import UUID
            try:
                pharmacy_id = UUID(str(pharmacy_id_str))
            except ValueError:
                logger.error(f"Invalid pharmacy_id format: {pharmacy_id_str}")
                return self._handle_no_organization()

            # Load pharmacy config from database by pharmacy ID
            pharmacy_config = await self._load_pharmacy_config(pharmacy_id)
            if not pharmacy_config:
                return self._handle_config_not_found()

            # Check if MP is enabled for this pharmacy
            if not pharmacy_config.mp_enabled:
                logger.warning(f"Mercado Pago integration is disabled for pharmacy {pharmacy_id}")
                return self._handle_mp_disabled()

            # Validate MP credentials
            if not pharmacy_config.mp_access_token:
                logger.error(f"No MP access token configured for pharmacy {pharmacy_id}")
                return self._handle_mp_not_configured()

            # Validate prerequisites
            debt_status = state_dict.get("debt_status")
            if debt_status != "confirmed":
                logger.warning(f"Cannot generate payment link: debt_status={debt_status}")
                return self._handle_not_confirmed()

            plex_customer_id = state_dict.get("plex_customer_id")
            if not plex_customer_id:
                logger.warning("Cannot generate payment link: no plex_customer_id")
                return self._handle_no_customer()

            # Get payment details (convert to Decimal for financial precision)
            total_debt = Decimal(str(state_dict.get("total_debt", 0) or 0))
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
            # Format: customer_id:debt_id:pharmacy_id:uuid (pharmacy_id for unique identification)
            unique_id = uuid.uuid4().hex[:8]
            external_reference = f"{plex_customer_id}:{debt_id}:{pharmacy_id}:{unique_id}"

            logger.info(
                f"Creating MP payment link: customer={plex_customer_id}, "
                f"amount=${amount}, is_partial={is_partial}, ref={external_reference}"
            )

            # Create Mercado Pago client with pharmacy-specific credentials
            mp_client = MercadoPagoClient(
                access_token=pharmacy_config.mp_access_token,
                notification_url=pharmacy_config.mp_notification_url,
                sandbox=pharmacy_config.mp_sandbox,
                timeout=pharmacy_config.mp_timeout,
            )

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
            if pharmacy_config.mp_sandbox and preference.get("sandbox_init_point"):
                init_point = preference["sandbox_init_point"]

            logger.info(f"MP preference created: {preference_id}, link={init_point[:50]}...")

            # Format response message with pharmacy name
            response_text = self._format_payment_link_message(
                customer_name=customer_name,
                amount=float(amount),
                total_debt=float(total_debt),
                remaining_balance=float(total_debt - amount) if is_partial else 0.0,
                payment_url=init_point,
                is_partial=is_partial,
                pharmacy_name=pharmacy_config.pharmacy_name or "Farmacia",
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
                # Clear routing flags to prevent stuck state
                "next_agent": None,
                "awaiting_debt_action": False,
                "awaiting_payment_amount_input": False,
                "awaiting_payment_option_selection": False,
            }

        except Exception as e:
            logger.error(f"Error generating payment link: {e!s}", exc_info=True)
            return self._handle_error(str(e), state_dict)

    async def _load_pharmacy_config(self, pharmacy_id) -> PharmacyConfig | None:
        """Load pharmacy configuration from database by pharmacy ID."""
        try:
            # Use db_session_factory if provided, otherwise use global context
            if self._db_session_factory:
                async with self._db_session_factory() as session:
                    config_service = PharmacyConfigService(session)
                    return await config_service.get_config_by_id(pharmacy_id)
            else:
                # Fallback to global async db context
                from app.database.async_db import get_async_db_context
                async with get_async_db_context() as session:
                    config_service = PharmacyConfigService(session)
                    return await config_service.get_config_by_id(pharmacy_id)
        except ValueError as e:
            logger.error(f"Failed to load pharmacy config: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading pharmacy config: {e}", exc_info=True)
            return None

    def _format_payment_link_message(
        self,
        customer_name: str,
        amount: float,
        total_debt: float,
        remaining_balance: float,
        payment_url: str,
        is_partial: bool = False,
        pharmacy_name: str = "Farmacia",
    ) -> str:
        """
        Format payment link message for WhatsApp.

        CASO 4 from pharmacy_flujo_mejorado_v2.md:
        Clear, formatted message with all payment details.

        Args:
            customer_name: Customer's name
            amount: Amount to pay
            total_debt: Total debt amount
            remaining_balance: Remaining balance after payment
            payment_url: Mercado Pago payment URL
            is_partial: True if this is a partial payment
            pharmacy_name: Name of the pharmacy

        Returns:
            Formatted message for WhatsApp
        """
        # Use Argentine number formatting (. as thousand separator)
        amount_str = f"${amount:,.2f}".replace(",", ".")
        total_str = f"${total_debt:,.2f}".replace(",", ".")
        remaining_str = f"${remaining_balance:,.2f}".replace(",", ".")

        if is_partial:
            return f"""💊 *{pharmacy_name}*

━━━━━━━━━━━━━━━━━━━━
💳 *LINK DE PAGO PARCIAL*
━━━━━━━━━━━━━━━━━━━━

Hola *{customer_name}*, tu link de pago está listo:

💰 *Monto a pagar:* {amount_str}
📊 Deuda total: {total_str}
📝 Saldo pendiente después del pago: *{remaining_str}*

━━━━━━━━━━━━━━━━━━━━
🔗 *Link de pago:*
{payment_url}
━━━━━━━━━━━━━━━━━━━━

📱 Haz clic en el link para pagar con Mercado Pago.

✅ Recibirás una confirmación automática cuando el pago se procese.

⏰ _Este link es válido por 24 horas._

¿Necesitas ayuda? Escribe *AYUDA*"""
        else:
            return f"""💊 *{pharmacy_name}*

━━━━━━━━━━━━━━━━━━━━
💳 *LINK DE PAGO GENERADO*
━━━━━━━━━━━━━━━━━━━━

Hola *{customer_name}*, tu link de pago está listo:

💰 *Monto a pagar:* {amount_str}

━━━━━━━━━━━━━━━━━━━━
🔗 *Link de pago:*
{payment_url}
━━━━━━━━━━━━━━━━━━━━

📱 Haz clic en el link para pagar con Mercado Pago.

✅ Recibirás una confirmación automática cuando el pago se procese.

⏰ _Este link es válido por 24 horas._

¿Necesitas ayuda? Escribe *AYUDA*"""

    def _handle_no_organization(self) -> dict[str, Any]:
        """Handle when organization_id is missing."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, no se pudo identificar la farmacia. "
                        "Por favor contacta a soporte."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
        }

    def _handle_config_not_found(self) -> dict[str, Any]:
        """Handle when pharmacy config is not found in database."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, la configuracion de pago no esta disponible. "
                        "Por favor contacta a la farmacia."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
        }

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
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
        }

    def _handle_mp_not_configured(self) -> dict[str, Any]:
        """Handle when Mercado Pago is not configured."""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Disculpa, el sistema de pagos no esta configurado. "
                        "Por favor contacta a la farmacia."
                    ),
                }
            ],
            "current_agent": self.name,
            "is_complete": True,
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
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
            # Clear routing to prevent loop, but keep debt flow awaiting confirmation
            "next_agent": None,
            "awaiting_debt_action": True,
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
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
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
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
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
            "is_complete": True,
            # Clear routing flags to prevent stuck state
            "next_agent": None,
            "awaiting_debt_action": False,
            "awaiting_payment_amount_input": False,
            "debt_status": None,
        }
