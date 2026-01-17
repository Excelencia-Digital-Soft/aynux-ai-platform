"""
Amount Normalizer Service

Normalizes monetary amounts from various user input formats.
Implements CASO 4.2 from docs/pharmacy_flujo_mejorado_v2.md.

Supported formats:
- Plain numbers: "5000", "15000"
- Thousands separator (Argentina): "5.000", "15.000"
- Thousands separator (other): "5,000", "15,000"
- Shorthand: "5k", "15K"
- Text (Spanish): "cinco mil", "quince mil"
- With currency: "$5000", "$ 5.000"
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

# Invisible Unicode characters that WhatsApp may inject
_INVISIBLE_CHARS: frozenset[str] = frozenset(
    {
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\u2060",  # Word joiner
        "\ufeff",  # BOM / Zero-width no-break space
    }
)

# Space-like characters to normalize to regular space
_SPACE_CHARS: frozenset[str] = frozenset(
    {
        "\u00a0",  # Non-breaking space
        "\u2002",  # En space
        "\u2003",  # Em space
        "\u2009",  # Thin space
        "\u202f",  # Narrow no-break space
    }
)


def _sanitize_input(text: str) -> str:
    """
    Sanitize input removing invisible Unicode characters.

    WhatsApp messages often contain invisible formatting characters
    that break amount parsing.

    Args:
        text: Raw user input

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Remove invisible characters
    for char in _INVISIBLE_CHARS:
        text = text.replace(char, "")

    # Normalize space-like characters
    for char in _SPACE_CHARS:
        text = text.replace(char, " ")

    return " ".join(text.split())


# Spanish number words
SPANISH_NUMBERS = {
    "cero": 0,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "veinte": 20,
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
    "cien": 100,
    "ciento": 100,
    "doscientos": 200,
    "trescientos": 300,
    "cuatrocientos": 400,
    "quinientos": 500,
    "seiscientos": 600,
    "setecientos": 700,
    "ochocientos": 800,
    "novecientos": 900,
    "mil": 1000,
    "millon": 1000000,
    "millones": 1000000,
}


@dataclass
class NormalizationResult:
    """Result of amount normalization."""

    success: bool
    amount: Decimal | None = None
    original_input: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "amount": float(self.amount) if self.amount else None,
            "original_input": self.original_input,
            "error": self.error,
        }


@dataclass
class ValidationResult:
    """Result of amount validation."""

    valid: bool
    amount: Decimal | None = None
    error: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None


class AmountNormalizer:
    """
    Normalizes monetary amounts from user input.

    Handles various input formats common in Argentina:
    - "5000", "5.000", "5,000" -> 5000
    - "5k", "5K" -> 5000
    - "cinco mil" -> 5000
    - "$5000", "$ 5.000" -> 5000
    """

    def __init__(self, default_min: Decimal = Decimal("1000")) -> None:
        """
        Initialize normalizer.

        Args:
            default_min: Default minimum amount if not specified
        """
        self.default_min = default_min

    def normalize(self, input_value: str) -> NormalizationResult:
        """
        Normalize a monetary amount from user input.

        Sanitizes input to handle WhatsApp invisible characters.

        Args:
            input_value: User's input string

        Returns:
            NormalizationResult with parsed amount or error
        """
        original = input_value
        # Sanitize to remove WhatsApp invisible characters
        input_value = _sanitize_input(input_value)

        if not input_value:
            return NormalizationResult(
                success=False,
                original_input=original,
                error="No se proporcionó un monto.",
            )

        # Try different parsing strategies
        parsers = [
            self._parse_plain_number,
            self._parse_with_thousand_separator,
            self._parse_shorthand,
            self._parse_spanish_text,
        ]

        for parser in parsers:
            try:
                result = parser(input_value)
                if result is not None:
                    return NormalizationResult(
                        success=True,
                        amount=result,
                        original_input=original,
                    )
            except Exception as e:
                logger.debug(f"Parser {parser.__name__} failed: {e}")
                continue

        return NormalizationResult(
            success=False,
            original_input=original,
            error="No pude entender el monto. Por favor escribí solo el número, por ejemplo: 5000",
        )

    def _parse_plain_number(self, value: str) -> Decimal | None:
        """Parse plain numbers like '5000' or '$5000'."""
        # Remove currency symbol and whitespace
        cleaned = re.sub(r"[$\s]", "", value)

        # Try to parse as decimal
        try:
            amount = Decimal(cleaned)
            if amount > 0:
                return amount
        except InvalidOperation:
            pass

        return None

    def _parse_with_thousand_separator(self, value: str) -> Decimal | None:
        """Parse numbers with thousand separators like '5.000' or '5,000'.

        Uses re.search to find amounts embedded in sentences:
        - "Pagar $17,005,699.20" → 17005699.20
        - "quiero 5.000 pesos" → 5000
        """
        # Remove currency symbol only (keep text for pattern matching)
        cleaned = re.sub(r"[$]", "", value)

        # Argentina format: 5.000 or 5.000,00 (. as thousand separator, , as decimal)
        # Uses re.search to find pattern anywhere in string
        arg_match = re.search(r"\b(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?)\b", cleaned)
        if arg_match:
            num_str = arg_match.group(1)
            # Remove thousand separators (.)
            num_str = num_str.replace(".", "")
            # Replace decimal separator (,) with (.)
            num_str = num_str.replace(",", ".")
            try:
                amount = Decimal(num_str)
                if amount > 0:
                    return amount
            except InvalidOperation:
                pass

        # US/International format: 5,000 or 5,000.00 (, as thousand separator, . as decimal)
        us_match = re.search(r"\b(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?)\b", cleaned)
        if us_match:
            num_str = us_match.group(1)
            # Remove thousand separators (,)
            num_str = num_str.replace(",", "")
            try:
                amount = Decimal(num_str)
                if amount > 0:
                    return amount
            except InvalidOperation:
                pass

        return None

    def _parse_shorthand(self, value: str) -> Decimal | None:
        """Parse shorthand like '5k' or '15K'.

        Uses re.search to find patterns anywhere in string:
        - "quiero pagar 5k" → 5000
        - "20k pesos" → 20000
        """
        cleaned = value.lower()

        # Match patterns like 5k, 5.5k, 15k anywhere in string
        match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*k\b", cleaned)
        if match:
            num = match.group(1).replace(",", ".")
            try:
                amount = Decimal(num) * 1000
                if amount > 0:
                    return amount
            except InvalidOperation:
                pass

        return None

    def _parse_spanish_text(self, value: str) -> Decimal | None:
        """Parse Spanish text like 'cinco mil', 'quince mil', or '15 mil'.

        Handles both exact matches and embedded amounts in sentences:
        - "15 mil" → 15000
        - "quiero pagar 15 mil" → 15000
        - "quince mil pesos" → 15000
        """
        cleaned = value.lower().strip()

        # Remove common words
        cleaned = re.sub(r"\bpesos?\b", "", cleaned)
        cleaned = re.sub(r"\bargentinos?\b", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Pattern 1: "<digit> mil" (e.g., "15 mil", "quiero pagar 15 mil" → 15000)
        # Uses search to find pattern anywhere in the string
        digit_mil_match = re.search(r"(\d+(?:[.,]\d+)?)\s+mil\b", cleaned)
        if digit_mil_match:
            num_str = digit_mil_match.group(1).replace(",", ".")
            try:
                amount = Decimal(num_str) * 1000
                if amount > 0:
                    return amount
            except InvalidOperation:
                pass

        # Pattern 2: "<word> mil" (e.g., "quince mil" → 15000)
        # Uses search to find pattern anywhere in the string
        word_mil_match = re.search(r"\b(\w+)\s+mil\b", cleaned)
        if word_mil_match:
            word = word_mil_match.group(1)
            if word in SPANISH_NUMBERS:
                amount = Decimal(SPANISH_NUMBERS[word] * 1000)
                if amount > 0:
                    return amount

        # Direct word match (exact)
        if cleaned in SPANISH_NUMBERS:
            amount = Decimal(SPANISH_NUMBERS[cleaned])
            if amount > 0:
                return amount

        return None

    def validate_range(
        self,
        amount: Decimal,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
    ) -> ValidationResult:
        """
        Validate that amount is within allowed range.

        Args:
            amount: Amount to validate
            min_amount: Minimum allowed (uses default_min if None)
            max_amount: Maximum allowed (usually total debt)

        Returns:
            ValidationResult with validation status
        """
        min_amt = min_amount or self.default_min
        max_amt = max_amount

        if amount < min_amt:
            return ValidationResult(
                valid=False,
                amount=amount,
                error=f"El monto mínimo es ${min_amt:,.0f}".replace(",", "."),
                min_amount=min_amt,
                max_amount=max_amt,
            )

        if max_amt and amount > max_amt:
            return ValidationResult(
                valid=False,
                amount=amount,
                error=f"El monto supera tu deuda de ${max_amt:,.0f}".replace(",", "."),
                min_amount=min_amt,
                max_amount=max_amt,
            )

        return ValidationResult(
            valid=True,
            amount=amount,
            min_amount=min_amt,
            max_amount=max_amt,
        )

    def normalize_and_validate(
        self,
        input_value: str,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
    ) -> tuple[NormalizationResult, ValidationResult | None]:
        """
        Normalize and validate amount in one call.

        Args:
            input_value: User's input string
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount

        Returns:
            Tuple of (NormalizationResult, ValidationResult or None)
        """
        norm_result = self.normalize(input_value)

        if not norm_result.success or norm_result.amount is None:
            return (norm_result, None)

        val_result = self.validate_range(norm_result.amount, min_amount, max_amount)
        return (norm_result, val_result)


def format_currency(amount: Decimal | float, include_symbol: bool = True) -> str:
    """
    Format amount as Argentine currency.

    Args:
        amount: Amount to format
        include_symbol: Whether to include $ symbol

    Returns:
        Formatted string like "$15.000" or "15.000"
    """
    if isinstance(amount, float):
        amount = Decimal(str(amount))

    # Format with thousand separator (Argentina uses .)
    formatted = f"{amount:,.0f}".replace(",", ".")

    if include_symbol:
        return f"${formatted}"
    return formatted


# Singleton instance
_normalizer: AmountNormalizer | None = None


def get_amount_normalizer() -> AmountNormalizer:
    """
    Get singleton normalizer instance.

    Returns:
        AmountNormalizer instance
    """
    global _normalizer
    if _normalizer is None:
        _normalizer = AmountNormalizer()
    return _normalizer


__all__ = [
    "AmountNormalizer",
    "NormalizationResult",
    "ValidationResult",
    "format_currency",
    "get_amount_normalizer",
]
