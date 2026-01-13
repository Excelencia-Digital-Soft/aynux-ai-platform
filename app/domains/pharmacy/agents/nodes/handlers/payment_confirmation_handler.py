"""
Payment Confirmation Handler

Handler for processing payment confirmations (YES/NO) and partial payment questions.
Handles the legacy confirmation flow for debt payment.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.message_parser import MessageParser, get_message_parser

logger = logging.getLogger(__name__)

# Default minimum payment amount
DEFAULT_MINIMUM_PAYMENT = 1000.0


class PaymentConfirmationHandler(BasePharmacyHandler):
    """
    Handler for payment confirmation responses.

    Handles:
    - YES/NO response to debt confirmation
    - Partial payment question responses

    Single Responsibility: Process payment confirmation user responses.
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

    async def handle_confirmation(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user response to debt confirmation (YES/NO).

        Args:
            message: User message
            state: Current state

        Returns:
            State updates
        """
        # Debug logging for WhatsApp message diagnosis
        logger.debug(f"handle_confirmation - Raw message repr: {repr(message)}")
        logger.debug(f"handle_confirmation - Message bytes: {message.encode('unicode_escape')}")

        message_lower = message.strip().lower()
        customer_name = state.get("customer_name", "Cliente")
        total_debt = state.get("total_debt", 0)
        parser = self._get_parser()

        # Check for YES response
        if parser.is_affirmative(message_lower):
            # User confirmed → proceed to payment link
            logger.info("User confirmed debt, proceeding to payment link")
            return {
                "messages": [{"role": "assistant", "content": "Perfecto, generando tu link de pago..."}],
                "current_agent": "debt_check_node",
                "awaiting_confirmation": False,
                "confirmation_received": True,
                "debt_status": "confirmed",
                "payment_amount": total_debt,
                "is_partial_payment": False,
                "next_agent": "payment_link_node",
            }

        # Check for NO response
        if parser.is_negative(message_lower):
            # User declined → offer partial payment option
            logger.info("User declined full payment, offering partial payment")
            min_payment = state.get("minimum_payment_amount", DEFAULT_MINIMUM_PAYMENT)

            response = f"""Entendido. ¿Te gustaría hacer un **pago parcial** de tu deuda?

Tu deuda total es **${total_debt:,.2f}**.
Puedes pagar cualquier monto desde **${min_payment:,.2f}**.

¿Querés realizar un pago parcial? Responde *SI* o *NO*."""

            return {
                "messages": [{"role": "assistant", "content": response}],
                "current_agent": "debt_check_node",
                "awaiting_confirmation": False,
                "awaiting_partial_payment_question": True,
            }

        # Check if user provided an amount directly (e.g., "pagar 5000")
        amount = parser.extract_amount(message)
        if amount:
            # Import here to avoid circular imports
            from app.domains.pharmacy.agents.nodes.handlers.payment_amount_handler import (
                PaymentAmountHandler,
            )
            amount_handler = PaymentAmountHandler()
            return await amount_handler.validate_and_set_amount(amount, state)

        # Unclear response → ask again
        return {
            "messages": [{"role": "assistant", "content": (
                f"Disculpa {customer_name}, no entendí tu respuesta. "
                "¿Deseas confirmar el pago? Responde *SI* o *NO*."
            )}],
            "current_agent": "debt_check_node",
        }

    async def handle_partial_payment(
        self,
        message: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle user response to partial payment question.

        Args:
            message: User message
            state: Current state

        Returns:
            State updates
        """
        # Debug logging for WhatsApp message diagnosis
        logger.debug(f"handle_partial_payment - Raw message repr: {repr(message)}")
        logger.debug(f"handle_partial_payment - Message bytes: {message.encode('unicode_escape')}")

        message_lower = message.strip().lower()
        customer_name = state.get("customer_name", "Cliente")
        total_debt = state.get("total_debt", 0)
        min_payment = state.get("minimum_payment_amount", DEFAULT_MINIMUM_PAYMENT)
        parser = self._get_parser()

        # Check for YES → ask for amount
        if parser.is_affirmative(message_lower):
            logger.info("User wants partial payment, asking for amount")
            response = f"""Perfecto. ¿Cuánto deseas pagar?

Tu deuda total: **${total_debt:,.2f}**
Monto mínimo: **${min_payment:,.2f}**

Escribe el monto que deseas abonar (ej: *5000* o *pagar 5000*)."""

            return {
                "messages": [{"role": "assistant", "content": response}],
                "current_agent": "debt_check_node",
                "awaiting_partial_payment_question": False,
                "awaiting_payment_amount_input": True,
            }

        # Check for NO → ask if needs other help
        if parser.is_negative(message_lower):
            logger.info("User declined partial payment")
            return {
                "messages": [{"role": "assistant", "content": (
                    f"Entendido {customer_name}. Tu deuda de **${total_debt:,.2f}** "
                    "queda pendiente.\n\n"
                    "¿Hay algo más en que pueda ayudarte?"
                )}],
                "current_agent": "debt_check_node",
                "awaiting_partial_payment_question": False,
                "partial_payment_declined": True,
                "is_complete": True,
            }

        # Check if user provided an amount directly
        amount = parser.extract_amount(message)
        if amount:
            from app.domains.pharmacy.agents.nodes.handlers.payment_amount_handler import (
                PaymentAmountHandler,
            )
            amount_handler = PaymentAmountHandler()
            return await amount_handler.validate_and_set_amount(amount, state)

        # Unclear response
        return {
            "messages": [{"role": "assistant", "content": (
                "Disculpa, no entendí. "
                "¿Deseas realizar un pago parcial? Responde *SI* o *NO*."
            )}],
            "current_agent": "debt_check_node",
        }
