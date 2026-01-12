"""Payment context state model."""

from __future__ import annotations

from pydantic import Field

from app.domains.pharmacy.agents.models.base import PharmacyStateModel


class PaymentContext(PharmacyStateModel):
    """
    Payment context fields.

    These fields track payment-related state including amounts,
    partial payment info, and Mercado Pago integration status.
    """

    # Payment amounts
    payment_amount: float | None = Field(
        default=None,
        description="Amount customer wants to pay (can be partial)"
    )
    is_partial_payment: bool = Field(
        default=False,
        description="True if payment_amount < total_debt"
    )
    remaining_balance: float | None = Field(
        default=None,
        description="Balance after payment"
    )
    minimum_payment_amount: float | None = Field(
        default=None,
        description="Minimum allowed partial payment (from config)"
    )

    # Payment options (smart negotiation)
    selected_payment_option: str | None = Field(
        default=None,
        description="Selected option: 'full', 'half', 'minimum', 'custom'"
    )
    payment_options_map: dict[str, float] | None = Field(
        default=None,
        description="Pre-calculated options {'full': 15000, 'half': 7500, ...}"
    )
    awaiting_payment_option_selection: bool = Field(
        default=False,
        description="Waiting for user to select 1/2/3/4"
    )

    # Partial payment flow
    awaiting_partial_payment_question: bool = Field(
        default=False,
        description="Asked if user wants partial payment (after NO)"
    )
    awaiting_payment_amount_input: bool = Field(
        default=False,
        description="Waiting for user to enter amount"
    )
    partial_payment_declined: bool = Field(
        default=False,
        description="User said NO to partial payment too"
    )

    # Payment confirmation
    awaiting_payment_confirmation: bool = Field(
        default=False,
        description="Waiting for SI/NO before generating link"
    )
    payment_confirmation_shown: bool = Field(
        default=False,
        description="True if confirmation message was shown"
    )

    # Mercado Pago integration
    mp_preference_id: str | None = Field(
        default=None,
        description="Mercado Pago preference ID"
    )
    mp_payment_id: str | None = Field(
        default=None,
        description="MP payment ID (after payment completes)"
    )
    mp_init_point: str | None = Field(
        default=None,
        description="Payment link URL"
    )
    mp_payment_status: str | None = Field(
        default=None,
        description="pending, approved, rejected, cancelled"
    )
    mp_external_reference: str | None = Field(
        default=None,
        description="Reference for webhook correlation (customer_id:debt_id:uuid)"
    )
    awaiting_payment: bool = Field(
        default=False,
        description="True when payment link sent, waiting for payment"
    )

    # Plex integration after payment
    plex_receipt_number: str | None = Field(
        default=None,
        description="PLEX receipt after REGISTRAR_PAGO_CLIENTE"
    )
    plex_new_balance: float | None = Field(
        default=None,
        description="Customer's new balance after payment"
    )

    def has_payment_intent(self) -> bool:
        """Check if there's a payment intent (amount or option selected)."""
        return self.payment_amount is not None or self.selected_payment_option is not None

    def is_payment_complete(self) -> bool:
        """Check if payment was completed successfully."""
        return self.mp_payment_status == "approved"


__all__ = ["PaymentContext"]
