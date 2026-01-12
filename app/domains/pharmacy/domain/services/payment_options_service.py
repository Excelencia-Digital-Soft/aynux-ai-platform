"""
Payment Options Service

Domain service for calculating and validating payment options.
Supports Smart Debt Negotiation with database-driven configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.tenancy.pharmacy_config_service import PharmacyConfig


# Default configuration values (same as DB defaults)
DEFAULT_HALF_PERCENT = 50
DEFAULT_MINIMUM_PERCENT = 30
DEFAULT_MINIMUM_PAYMENT = 1000.0


@dataclass
class PaymentValidationResult:
    """Result of payment amount validation."""

    is_valid: bool
    error_message: str | None = None
    error_type: str | None = None  # "below_minimum" | "above_total"


class PaymentOptionsService:
    """
    Domain service for payment option calculations.

    Calculates pre-defined payment options based on pharmacy configuration.
    Validates user-provided payment amounts against business rules.

    Single Responsibility: Calculate and validate payment options.
    """

    @classmethod
    def calculate_options(
        cls,
        total_debt: float,
        pharmacy_config: PharmacyConfig | None,
    ) -> dict[str, float]:
        """
        Calculate pre-defined payment options based on pharmacy configuration.

        Uses database-driven percentages from PharmacyMerchantConfig.

        Args:
            total_debt: Total debt amount
            pharmacy_config: Pharmacy configuration with payment option settings

        Returns:
            Dictionary with payment options: {"full": amount, "half": amount, ...}
        """
        # Get percentages from config or use defaults
        if pharmacy_config:
            half_percent = pharmacy_config.payment_option_half_percent / 100.0
            minimum_percent = pharmacy_config.payment_option_minimum_percent / 100.0
            min_payment = float(pharmacy_config.payment_minimum_amount)
        else:
            half_percent = DEFAULT_HALF_PERCENT / 100.0
            minimum_percent = DEFAULT_MINIMUM_PERCENT / 100.0
            min_payment = DEFAULT_MINIMUM_PAYMENT

        options: dict[str, float] = {"full": total_debt}

        # Calculate half option (e.g., 50%)
        half_amount = round(total_debt * half_percent, 2)
        if half_amount >= min_payment and half_amount < total_debt:
            options["half"] = half_amount

        # Calculate minimum option (e.g., 30%)
        minimum_amount = round(total_debt * minimum_percent, 2)
        if minimum_amount < min_payment:
            minimum_amount = min_payment

        if minimum_amount < total_debt and minimum_amount != half_amount:
            options["minimum"] = minimum_amount

        return options

    @classmethod
    def validate_amount(
        cls,
        amount: float,
        total_debt: float,
        min_payment: float,
    ) -> PaymentValidationResult:
        """
        Validate payment amount against constraints.

        Args:
            amount: Payment amount entered by user
            total_debt: Total debt amount
            min_payment: Minimum allowed payment

        Returns:
            PaymentValidationResult with validation status
        """
        if amount < min_payment:
            return PaymentValidationResult(
                is_valid=False,
                error_message=f"El monto mínimo de pago es *${min_payment:,.2f}*.",
                error_type="below_minimum",
            )

        if amount > total_debt:
            return PaymentValidationResult(
                is_valid=False,
                error_message=(
                    f"El monto ingresado (${amount:,.2f}) es mayor a tu deuda "
                    f"(${total_debt:,.2f})."
                ),
                error_type="above_total",
            )

        return PaymentValidationResult(is_valid=True)

    @classmethod
    def get_minimum_payment(
        cls,
        pharmacy_config: PharmacyConfig | None,
    ) -> float:
        """
        Get minimum payment amount from config or default.

        Args:
            pharmacy_config: Pharmacy configuration

        Returns:
            Minimum payment amount
        """
        if pharmacy_config:
            return float(pharmacy_config.payment_minimum_amount)
        return DEFAULT_MINIMUM_PAYMENT

    @classmethod
    def get_percentages(
        cls,
        pharmacy_config: PharmacyConfig | None,
    ) -> dict[str, int]:
        """
        Get payment option percentages from config or defaults.

        Args:
            pharmacy_config: Pharmacy configuration

        Returns:
            Dictionary with "half" and "minimum" percentages
        """
        if pharmacy_config:
            return {
                "half": pharmacy_config.payment_option_half_percent,
                "minimum": pharmacy_config.payment_option_minimum_percent,
            }
        return {
            "half": DEFAULT_HALF_PERCENT,
            "minimum": DEFAULT_MINIMUM_PERCENT,
        }

    @classmethod
    def is_partial_payment(cls, amount: float, total_debt: float) -> bool:
        """
        Check if amount constitutes a partial payment.

        Args:
            amount: Payment amount
            total_debt: Total debt amount

        Returns:
            True if payment is partial (less than total)
        """
        return amount < total_debt

    @classmethod
    def calculate_remaining(cls, amount: float, total_debt: float) -> float:
        """
        Calculate remaining balance after payment.

        Args:
            amount: Payment amount
            total_debt: Total debt amount

        Returns:
            Remaining balance
        """
        return max(0, total_debt - amount)
