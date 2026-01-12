"""
Payment Amount Handler

Handler for processing custom payment amount input from users.
Validates amounts against minimum and maximum constraints.
"""

from __future__ import annotations

import logging
from typing import Any

from app.domains.pharmacy.agents.nodes.handlers.base_handler import BasePharmacyHandler
from app.domains.pharmacy.agents.utils.message_parser import MessageParser, get_message_parser
from app.domains.pharmacy.domain.services.payment_options_service import (
    PaymentOptionsService,
)

logger = logging.getLogger(__name__)

# Default minimum payment amount
DEFAULT_MINIMUM_PAYMENT = 1000.0


class PaymentAmountHandler(BasePharmacyHandler):
    """
    Handler for custom payment amount input.

    Handles the flow when user enters a specific payment amount.
    Validates the amount and proceeds to payment link generation.

    Single Responsibility: Process and validate payment amount input.
    """

    def __init__(
        self,
        message_parser: MessageParser | None = None,
    ) -> None:
        """
        Initialize handler.

        Args:
            message_parser: MessageParser instance for amount extraction
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
        Handle user input for payment amount.

        Args:
            message: User message with amount
            state: Current state

        Returns:
            State updates
        """
        min_payment = state.get("minimum_payment_amount", DEFAULT_MINIMUM_PAYMENT)
        parser = self._get_parser()

        # Extract amount from message
        amount = parser.extract_amount(message)

        if not amount:
            return {
                "messages": [{"role": "assistant", "content": (
                    "No pude identificar el monto. "
                    f"Por favor escribe la cantidad que deseas pagar (ej: *5000*).\n\n"
                    f"Monto mínimo: **${min_payment:,.2f}**"
                )}],
                "current_agent": "debt_check_node",
            }

        return await self.validate_and_set_amount(amount, state)

    async def validate_and_set_amount(
        self,
        amount: float,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate payment amount and proceed to payment link.

        Args:
            amount: Payment amount entered by user
            state: Current state

        Returns:
            State updates
        """
        customer_name = state.get("customer_name", "Cliente")
        total_debt = state.get("total_debt", 0)
        min_payment = state.get("minimum_payment_amount", DEFAULT_MINIMUM_PAYMENT)

        # Validate amount
        validation = PaymentOptionsService.validate_amount(
            amount=amount,
            total_debt=total_debt,
            min_payment=min_payment,
        )

        if not validation.is_valid:
            error_msg = validation.error_message or "Monto inválido"

            if validation.error_type == "below_minimum":
                return {
                    "messages": [{"role": "assistant", "content": (
                        f"{error_msg}\n\n"
                        f"Por favor ingresa un monto igual o mayor."
                    )}],
                    "current_agent": "debt_check_node",
                    "awaiting_payment_amount_input": True,
                }

            if validation.error_type == "above_total":
                return {
                    "messages": [{"role": "assistant", "content": (
                        f"{error_msg}\n\n"
                        f"Por favor ingresa un monto igual o menor a tu deuda."
                    )}],
                    "current_agent": "debt_check_node",
                    "awaiting_payment_amount_input": True,
                }

        # Valid amount → proceed to payment
        is_partial = PaymentOptionsService.is_partial_payment(amount, total_debt)
        remaining = PaymentOptionsService.calculate_remaining(amount, total_debt)

        if is_partial:
            response = (
                f"Perfecto {customer_name}, generando link de pago por **${amount:,.2f}**.\n\n"
                f"Saldo restante después del pago: **${remaining:,.2f}**"
            )
        else:
            response = (
                f"Perfecto {customer_name}, generando link de pago por el total de tu deuda: "
                f"**${amount:,.2f}**"
            )

        logger.info(f"User set payment amount: ${amount:,.2f} (partial: {is_partial})")

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": "debt_check_node",
            "awaiting_confirmation": False,
            "awaiting_partial_payment_question": False,
            "awaiting_payment_amount_input": False,
            "confirmation_received": True,
            "debt_status": "confirmed",
            "payment_amount": amount,
            "is_partial_payment": is_partial,
            "remaining_balance": remaining if is_partial else None,
            "next_agent": "payment_link_node",
        }
