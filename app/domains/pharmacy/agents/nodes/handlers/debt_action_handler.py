"""
Debt Action Handler

Handler for processing debt action menu selection (CASO 3).
Handles the post-debt display menu with payment and detail options.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.debt_formatter_service import DebtFormatterService
from app.domains.pharmacy.agents.utils.message_parser import MessageParser, get_message_parser
from app.domains.pharmacy.agents.utils.plex_debt_mapper import PlexDebtMapper

if TYPE_CHECKING:
    from app.core.tenancy.pharmacy_config_service import PharmacyConfig

logger = logging.getLogger(__name__)

# Default minimum payment amount
DEFAULT_MINIMUM_PAYMENT = 1000.0


class DebtActionHandler(BasePharmacyHandler):
    """
    Handler for debt action menu selection (CASO 3).

    Handles the post-debt action menu:
    1️⃣ Pagar total
    2️⃣ Pagar parcial
    3️⃣ Ver detalle de facturas
    4️⃣ Volver al menú

    Single Responsibility: Process debt action menu selection.
    """

    def __init__(
        self,
        message_parser: MessageParser | None = None,
    ) -> None:
        """
        Initialize handler.

        Args:
            message_parser: MessageParser instance
        """
        super().__init__()
        self._parser = message_parser
        self._pharmacy_config: PharmacyConfig | None = None

    def _get_parser(self) -> MessageParser:
        """Get or create message parser."""
        if self._parser is None:
            self._parser = get_message_parser()
        return self._parser

    async def handle(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle debt action menu selection (CASO 3).

        Options:
        1️⃣ Pagar total
        2️⃣ Pagar parcial
        3️⃣ Ver detalle de facturas
        4️⃣ Volver al menú

        Args:
            message: User message (expected: 1, 2, 3, or 4)
            state: Current state

        Returns:
            State updates
        """
        message_clean = message.strip().lower()
        customer_name = state.get("customer_name", "Cliente")
        total_debt = state.get("total_debt", 0)
        payment_options = state.get("payment_options_map", {})
        debt_items = state.get("debt_items", [])
        parser = self._get_parser()

        # Option 1: Pay total (DB-driven pattern matching)
        if await self._match_confirmation_pattern(message_clean, "debt_menu_pay_total", state):
            return self._handle_pay_total(customer_name, payment_options, total_debt)

        # Option 2: Pay partial (DB-driven pattern matching)
        if await self._match_confirmation_pattern(message_clean, "debt_menu_pay_partial", state):
            return await self._handle_pay_partial(
                customer_name, total_debt, payment_options, state
            )

        # Option 3: View invoice details (DB-driven pattern matching)
        if await self._match_confirmation_pattern(message_clean, "debt_menu_view_details", state):
            return self._handle_view_details(debt_items, total_debt)

        # Option 4: Return to main menu (DB-driven pattern matching)
        if await self._match_confirmation_pattern(message_clean, "debt_menu_return", state):
            return self._handle_return_to_menu(total_debt)

        # Check if user entered a specific amount directly
        amount = parser.extract_amount(message)
        if amount:
            from app.domains.pharmacy.agents.nodes.handlers.payment_amount_handler import (
                PaymentAmountHandler,
            )
            amount_handler = PaymentAmountHandler()
            return await amount_handler.validate_and_set_amount(amount, state)

        # Check for affirmative (YES) - proceed with full payment
        if parser.is_affirmative(message_clean):
            return self._handle_pay_total(customer_name, payment_options, total_debt)

        # Check for negative (NO) - return to menu
        if parser.is_negative(message_clean):
            return self._handle_declined(customer_name, total_debt)

        # Unclear response - show options again
        return await self._handle_unclear_response(customer_name, payment_options, state)

    def _handle_pay_total(
        self,
        customer_name: str,
        payment_options: dict[str, float],
        total_debt: float,
    ) -> dict[str, Any]:
        """Handle full payment selection."""
        amount = payment_options.get("full", total_debt)
        logger.info(f"User selected full payment: ${amount:,.2f}")
        return {
            "messages": [{"role": "assistant", "content": (
                f"Perfecto {customer_name}, generando link de pago por el total: *${amount:,.2f}*"
            )}],
            "current_agent": "debt_check_node",
            "awaiting_debt_action": False,
            "selected_payment_option": "full",
            "payment_amount": amount,
            "is_partial_payment": False,
            "confirmation_received": True,
            "debt_status": "confirmed",
            "next_agent": "payment_link_node",
        }

    async def _handle_pay_partial(
        self,
        customer_name: str,
        total_debt: float,
        payment_options: dict[str, float],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle partial payment selection."""
        # Get half or minimum amount
        if "half" in payment_options:
            amount = payment_options["half"]
        elif "minimum" in payment_options:
            amount = payment_options["minimum"]
        else:
            # No preset partial, ask for custom amount
            min_payment = state.get("minimum_payment_amount", DEFAULT_MINIMUM_PAYMENT)
            return {
                "messages": [{"role": "assistant", "content": (
                    f"¿Cuánto deseas pagar?\n\n"
                    f"Tu deuda total: *${total_debt:,.2f}*\n"
                    f"Monto mínimo: *${min_payment:,.2f}*\n\n"
                    f"_Escribe el monto que deseas abonar (ej: 5000)_"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_debt_action": False,
                "awaiting_payment_amount_input": True,
                "selected_payment_option": "custom",
            }

        remaining = total_debt - amount
        logger.info(f"User selected partial payment: ${amount:,.2f}")
        return {
            "messages": [{"role": "assistant", "content": (
                f"Perfecto {customer_name}, generando link de pago parcial: *${amount:,.2f}*\n"
                f"Saldo restante después del pago: *${remaining:,.2f}*"
            )}],
            "current_agent": "debt_check_node",
            "awaiting_debt_action": False,
            "selected_payment_option": "partial",
            "payment_amount": amount,
            "is_partial_payment": True,
            "remaining_balance": remaining,
            "confirmation_received": True,
            "debt_status": "confirmed",
            "next_agent": "payment_link_node",
        }

    def _handle_view_details(
        self,
        debt_items: list[dict[str, Any]],
        total_debt: float,
    ) -> dict[str, Any]:
        """Handle view invoice details selection."""
        logger.info("User requested invoice details")
        # Convert stored items back to DebtItem objects for formatting
        items = PlexDebtMapper.reconstruct_items(debt_items)
        details_text = DebtFormatterService.format_invoice_details(items)

        return {
            "messages": [{"role": "assistant", "content": (
                f"📋 *Detalle de tu cuenta*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{details_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *Total: ${total_debt:,.2f}*\n\n"
                f"¿Qué deseas hacer?\n"
                f"1️⃣ Pagar  |  4️⃣ Volver al Menú"
            )}],
            "current_agent": "debt_check_node",
            # Keep awaiting_debt_action True to handle follow-up
            "awaiting_debt_action": True,
        }

    def _handle_return_to_menu(self, total_debt: float) -> dict[str, Any]:
        """Handle return to main menu selection."""
        logger.info("User requested return to main menu")
        return {
            "messages": [{"role": "assistant", "content": (
                f"Tu deuda de *${total_debt:,.2f}* queda pendiente.\n\n"
                "¿En qué más puedo ayudarte?"
            )}],
            "current_agent": "debt_check_node",
            "awaiting_debt_action": False,
            "next_agent": "main_menu_node",
            "current_menu": "main",
        }

    def _handle_declined(
        self,
        customer_name: str,
        total_debt: float,
    ) -> dict[str, Any]:
        """Handle user declining payment."""
        logger.info("User declined payment")
        return {
            "messages": [{"role": "assistant", "content": (
                f"Entendido {customer_name}. Tu deuda de *${total_debt:,.2f}* queda pendiente.\n\n"
                "¿En qué más puedo ayudarte?"
            )}],
            "current_agent": "debt_check_node",
            "awaiting_debt_action": False,
            "next_agent": "main_menu_node",
            "current_menu": "main",
        }

    async def _handle_unclear_response(
        self,
        customer_name: str,
        payment_options: dict[str, float],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle unclear user response."""
        # Get pharmacy config for formatting
        pharmacy_config = await self._load_pharmacy_config(state)
        options_text = DebtFormatterService.format_debt_action_menu(
            payment_options, pharmacy_config
        )
        return {
            "messages": [{"role": "assistant", "content": (
                f"Disculpa {customer_name}, no entendí tu selección.\n\n"
                f"Por favor, responde con el *número* de la opción:\n\n{options_text}"
            )}],
            "current_agent": "debt_check_node",
        }

    async def _load_pharmacy_config(
        self,
        state: dict[str, Any],
    ) -> PharmacyConfig | None:
        """
        Load pharmacy config from database.

        Prefers pharmacy_id (specific pharmacy) over organization_id (may have multiple).
        """
        if self._pharmacy_config is not None:
            return self._pharmacy_config

        from uuid import UUID

        from app.core.tenancy.pharmacy_config_service import PharmacyConfigService

        # Prefer pharmacy_id if available (more specific, avoids multiple rows issue)
        pharmacy_id_str = state.get("pharmacy_id")
        org_id_str = state.get("organization_id")

        if not pharmacy_id_str and not org_id_str:
            return None

        try:
            async with await self._get_db_session() as db:
                config_service = PharmacyConfigService(db)

                # Try pharmacy_id first (specific pharmacy)
                if pharmacy_id_str:
                    pharmacy_id = (
                        UUID(str(pharmacy_id_str))
                        if not isinstance(pharmacy_id_str, UUID)
                        else pharmacy_id_str
                    )
                    self._pharmacy_config = await config_service.get_config_by_id(pharmacy_id)
                    return self._pharmacy_config

                # Fall back to organization_id
                org_id = (
                    UUID(str(org_id_str))
                    if not isinstance(org_id_str, UUID)
                    else org_id_str
                )
                self._pharmacy_config = await config_service.get_config(org_id)
                return self._pharmacy_config
        except Exception as e:
            logger.error(f"Failed to load pharmacy config: {e}")
            return None
