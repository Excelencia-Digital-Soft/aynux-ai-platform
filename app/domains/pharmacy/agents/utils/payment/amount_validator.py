# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Payment amount parsing and validation.
#              Extracted from payment_processor_node.py for SRP compliance.
# Tenant-Aware: No - pure validation logic.
# ============================================================================
"""
Payment amount parsing and validation.

Single Responsibility: Extract and validate payment amounts from messages.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from app.domains.pharmacy.services.amount_normalizer import get_amount_normalizer

logger = logging.getLogger(__name__)


class AmountErrorType(str, Enum):
    """Types of amount validation errors."""

    INVALID = "invalid"  # Cannot parse amount from message
    ZERO = "zero"  # Amount is zero or negative
    EXCEEDS_DEBT = "exceeds_debt"  # Amount exceeds total debt


@dataclass(frozen=True)
class AmountValidationResult:
    """
    Result of amount validation.

    Attributes:
        is_valid: Whether the amount is valid
        amount: Extracted amount (if valid)
        error_type: Type of error (if invalid)
        error_message: Human-readable error message (if invalid)
    """

    is_valid: bool
    amount: float | None = None
    error_type: AmountErrorType | None = None
    error_message: str | None = None


class AmountValidator:
    """
    Validates payment amounts from user messages.

    Single Responsibility: Parse and validate payment amounts.

    Handles:
    - Amount extraction from various formats ($1000, 1000, 1,000, 1.000)
    - Range validation (>0, <=total_debt)
    - Error message generation
    """

    @staticmethod
    def extract_amount(message: str) -> float | None:
        """
        Extract numeric amount from user message.

        Uses AmountNormalizer for full Spanish support:
        - "15 mil" → 15000.0
        - "$15,000" → 15000.0
        - "quince mil pesos" → 15000.0
        - "5k" → 5000.0
        - "$1000", "1,000", "1.000" → 1000.0

        Args:
            message: User message potentially containing an amount

        Returns:
            Extracted amount as float, or None if no valid amount found
        """
        # Use AmountNormalizer for comprehensive Spanish amount parsing
        normalizer = get_amount_normalizer()
        result = normalizer.normalize(message)

        if result.success and result.amount is not None:
            logger.debug(
                f"[AMOUNT_VALIDATOR] Extracted amount from '{message}': {result.amount}"
            )
            return float(result.amount)

        # Fallback: extract number with optional decimal
        # Preserves decimal point for amounts like "1500.50"
        cleaned = message.replace("$", "").strip()
        # Remove thousand separators but keep decimal point
        # Try to detect format: if has both . and , the last one is decimal
        if "." in cleaned and "," in cleaned:
            # Determine which is decimal (usually the last one)
            last_dot = cleaned.rfind(".")
            last_comma = cleaned.rfind(",")
            if last_comma > last_dot:
                # Comma is decimal: 1.000,50 → remove dots, replace comma
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Dot is decimal: 1,000.50 → remove commas
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Only commas - could be thousand sep or decimal
            # If single comma with 1-2 digits after, it's decimal
            if re.search(r",\d{1,2}$", cleaned):
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        # If only dots, assume Argentina format (thousand sep) unless decimal pattern
        elif "." in cleaned and not re.search(r"\.\d{1,2}$", cleaned):
            cleaned = cleaned.replace(".", "")

        match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if match:
            amount = float(match.group(1))
            logger.debug(
                f"[AMOUNT_VALIDATOR] Fallback extraction from '{message}': {amount}"
            )
            return amount

        return None

    @classmethod
    def validate(
        cls,
        message: str,
        total_debt: float,
    ) -> AmountValidationResult:
        """
        Extract and validate payment amount from message.

        Args:
            message: User message containing payment amount
            total_debt: Total debt amount for upper bound validation

        Returns:
            AmountValidationResult with validation outcome
        """
        amount = cls.extract_amount(message)

        # Check if amount was extracted
        if amount is None:
            return AmountValidationResult(
                is_valid=False,
                error_type=AmountErrorType.INVALID,
                error_message="No pude entender el monto. Por favor ingresa un número válido.",
            )

        # Check if amount is positive
        if amount <= 0:
            return AmountValidationResult(
                is_valid=False,
                amount=amount,
                error_type=AmountErrorType.ZERO,
                error_message="El monto debe ser mayor a $0.",
            )

        # Check if amount exceeds debt
        if amount > total_debt:
            return AmountValidationResult(
                is_valid=False,
                amount=amount,
                error_type=AmountErrorType.EXCEEDS_DEBT,
                error_message=f"El monto (${amount:,.2f}) es mayor que tu deuda (${total_debt:,.2f}).",
            )

        # Valid amount
        return AmountValidationResult(
            is_valid=True,
            amount=amount,
        )

    @staticmethod
    def is_partial_payment(amount: float, total_debt: float) -> bool:
        """
        Determine if payment is partial.

        Args:
            amount: Payment amount
            total_debt: Total debt amount

        Returns:
            True if payment is less than total debt
        """
        return amount < total_debt

    @staticmethod
    def calculate_remaining(amount: float, total_debt: float) -> float:
        """
        Calculate remaining balance after payment.

        Args:
            amount: Payment amount
            total_debt: Total debt amount

        Returns:
            Remaining balance
        """
        return max(0.0, total_debt - amount)
