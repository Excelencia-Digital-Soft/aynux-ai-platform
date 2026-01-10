"""
Payment Option Handler

Handler for processing payment option selection (legacy flow).
Handles the numbered menu selection for payment options.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.debt_formatter_service import DebtFormatterService
from app.domains.pharmacy.agents.utils.message_parser import MessageParser, get_message_parser

logger = logging.getLogger(__name__)

# Default minimum payment amount
DEFAULT_MINIMUM_PAYMENT = 1000.0


class PaymentOptionHandler(BasePharmacyHandler):
    """
    Handler for payment option selection (legacy flow).

    Handles the numbered menu:
    1. Full payment
    2. Half payment (e.g., 50%)
    3. Minimum payment (e.g., 30%)
    4. Custom amount

    Single Responsibility: Process payment option menu selection.
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
        Handle user selection of payment option (1/2/3/4).

        Args:
            message: User message (expected: 1, 2, 3, or 4)
            state: Current state with payment_options_map

        Returns:
            State updates
        """
        message_clean = message.strip().lower()
        customer_name = state.get("customer_name", "Cliente")
        total_debt = state.get("total_debt", 0)
        payment_options = state.get("payment_options_map", {})
        min_payment = state.get("minimum_payment_amount", DEFAULT_MINIMUM_PAYMENT)
        parser = self._get_parser()

        # Option 1: Full payment
        if message_clean in {"1", "total", "completo", "todo", "pagar todo"}:
            amount = payment_options.get("full", total_debt)
            logger.info(f"User selected full payment: ${amount:,.2f}")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"Perfecto {customer_name}, generando link de pago por el total: *${amount:,.2f}*"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_payment_option_selection": False,
                "selected_payment_option": "full",
                "payment_amount": amount,
                "is_partial_payment": False,
                "confirmation_received": True,
                "debt_status": "confirmed",
                "next_agent": "payment_link_node",
            }

        # Option 2: Half payment (e.g., 50%)
        if message_clean in {"2", "mitad", "medio", "50"} and "half" in payment_options:
            amount = payment_options["half"]
            remaining = total_debt - amount
            logger.info(f"User selected half payment: ${amount:,.2f}")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"Perfecto {customer_name}, generando link de pago parcial: *${amount:,.2f}*\n"
                    f"Saldo restante después del pago: *${remaining:,.2f}*"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_payment_option_selection": False,
                "selected_payment_option": "half",
                "payment_amount": amount,
                "is_partial_payment": True,
                "remaining_balance": remaining,
                "confirmation_received": True,
                "debt_status": "confirmed",
                "next_agent": "payment_link_node",
            }

        # Option 3: Minimum payment (e.g., 30%)
        if message_clean in {"3", "minimo", "mínimo", "30"} and "minimum" in payment_options:
            amount = payment_options["minimum"]
            remaining = total_debt - amount
            logger.info(f"User selected minimum payment: ${amount:,.2f}")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"Perfecto {customer_name}, generando link de pago mínimo: *${amount:,.2f}*\n"
                    f"Saldo restante después del pago: *${remaining:,.2f}*"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_payment_option_selection": False,
                "selected_payment_option": "minimum",
                "payment_amount": amount,
                "is_partial_payment": True,
                "remaining_balance": remaining,
                "confirmation_received": True,
                "debt_status": "confirmed",
                "next_agent": "payment_link_node",
            }

        # Option 4: Custom amount
        if message_clean in {"4", "otro", "personalizado", "custom"}:
            logger.info("User selected custom payment amount")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"¿Cuánto deseas pagar?\n\n"
                    f"Tu deuda total: *${total_debt:,.2f}*\n"
                    f"Monto mínimo: *${min_payment:,.2f}*\n\n"
                    f"_Escribe el monto que deseas abonar (ej: 5000)_"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_payment_option_selection": False,
                "awaiting_payment_amount_input": True,
                "selected_payment_option": "custom",
            }

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
            amount = payment_options.get("full", total_debt)
            logger.info(f"User confirmed, proceeding with full payment: ${amount:,.2f}")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"Perfecto {customer_name}, generando link de pago por el total: *${amount:,.2f}*"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_payment_option_selection": False,
                "selected_payment_option": "full",
                "payment_amount": amount,
                "is_partial_payment": False,
                "confirmation_received": True,
                "debt_status": "confirmed",
                "next_agent": "payment_link_node",
            }

        # Check for negative (NO) - ask if needs other help
        if parser.is_negative(message_clean):
            logger.info("User declined payment options")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"Entendido {customer_name}. Tu deuda de *${total_debt:,.2f}* queda pendiente.\n\n"
                    "¿Hay algo más en que pueda ayudarte?"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_payment_option_selection": False,
                "is_complete": True,
            }

        # Unclear response - show options again
        options_text = DebtFormatterService.format_payment_options(payment_options, None)
        return {
            "messages": [{"role": "assistant", "content": (
                f"Disculpa {customer_name}, no entendí tu selección.\n\n"
                f"Por favor, responde con el *número* de la opción:\n\n{options_text}"
            )}],
            "current_agent": "debt_check_node",
        }
