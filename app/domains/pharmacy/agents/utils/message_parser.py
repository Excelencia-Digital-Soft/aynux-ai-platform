"""
Message Parser

Utility for parsing user messages in the pharmacy domain.
Handles affirmative/negative detection and amount extraction.
Uses AmountNormalizer for monetary amount parsing.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.domains.pharmacy.services.amount_normalizer import (
    AmountNormalizer,
    NormalizationResult,
    get_amount_normalizer,
)


class MessageParser:
    """
    Parses user messages for common patterns.

    Handles:
    - Affirmative/negative response detection
    - Payment amount extraction (delegates to AmountNormalizer)
    - Menu option detection (1, 2, 3, 4)

    Single Responsibility: Parse user messages into structured data.
    """

    # Affirmative responses in Spanish
    AFFIRMATIVE: frozenset[str] = frozenset({
        "si", "sí", "yes", "ok", "dale", "confirmo", "confirmar",
        "acepto", "aceptar", "seguro", "claro", "listo", "bueno",
    })

    # Negative responses in Spanish
    NEGATIVE: frozenset[str] = frozenset({
        "no", "nop", "nope", "cancelar", "cancelo", "no quiero",
        "negar", "rechazar", "rechazo",
    })

    # Menu option patterns
    MENU_OPTIONS: dict[str, set[str]] = {
        "1": {"1", "1️⃣", "total", "pagar todo", "pagar total", "uno"},
        "2": {"2", "2️⃣", "parcial", "pagar parcial", "mitad", "medio", "dos"},
        "3": {"3", "3️⃣", "detalle", "detalles", "facturas", "ver detalle", "tres"},
        "4": {"4", "4️⃣", "menu", "menú", "volver", "salir", "cuatro"},
    }

    def __init__(self, amount_normalizer: AmountNormalizer | None = None) -> None:
        """
        Initialize parser.

        Args:
            amount_normalizer: AmountNormalizer instance (creates one if not provided)
        """
        self._normalizer = amount_normalizer or get_amount_normalizer()

    @classmethod
    def is_affirmative(cls, text: str) -> bool:
        """
        Check if text is an affirmative response.

        Args:
            text: User message text

        Returns:
            True if affirmative
        """
        text_lower = text.strip().lower()

        # Direct match
        if text_lower in cls.AFFIRMATIVE:
            return True

        # Prefix match (e.g., "si quiero", "sí por favor")
        return text_lower.startswith("si ") or text_lower.startswith("sí ")

    @classmethod
    def is_negative(cls, text: str) -> bool:
        """
        Check if text is a negative response.

        Args:
            text: User message text

        Returns:
            True if negative
        """
        text_lower = text.strip().lower()

        # Direct match
        if text_lower in cls.NEGATIVE:
            return True

        # Prefix match (e.g., "no gracias", "no quiero")
        return text_lower.startswith("no ")

    @classmethod
    def detect_menu_option(cls, text: str) -> str | None:
        """
        Detect which menu option user selected.

        Args:
            text: User message text

        Returns:
            Option number ("1", "2", "3", "4") or None
        """
        text_lower = text.strip().lower()

        for option, patterns in cls.MENU_OPTIONS.items():
            if text_lower in patterns:
                return option

        return None

    def extract_amount(self, message: str) -> float | None:
        """
        Extract payment amount from user message.

        Handles formats like:
        - "5000"
        - "pagar 5000"
        - "quiero pagar $5000"
        - "5000.50"
        - "5,000"
        - "cinco mil"

        Args:
            message: User message

        Returns:
            Extracted amount or None
        """
        # First try with AmountNormalizer (handles complex formats)
        result = self._normalizer.normalize(message)
        if result.success and result.amount is not None:
            return float(result.amount)

        # Fallback: try simple regex extraction
        return self._extract_amount_simple(message)

    def _extract_amount_simple(self, message: str) -> float | None:
        """
        Simple regex-based amount extraction as fallback.

        Args:
            message: User message

        Returns:
            Extracted amount or None
        """
        # Remove currency symbols and common words
        cleaned = message.lower()
        cleaned = re.sub(r"[,$]", "", cleaned)
        cleaned = re.sub(r"(pagar|pago|abonar|quiero|deseo)", "", cleaned)
        cleaned = cleaned.strip()

        # Try to extract number
        match = re.search(r"(\d+(?:\.\d{1,2})?)", cleaned)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None

        return None

    def normalize_and_validate_amount(
        self,
        message: str,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
    ) -> tuple[NormalizationResult, Any | None]:
        """
        Normalize and validate amount from message.

        Args:
            message: User message
            min_amount: Minimum allowed amount
            max_amount: Maximum allowed amount (usually total debt)

        Returns:
            Tuple of (NormalizationResult, ValidationResult or None)
        """
        return self._normalizer.normalize_and_validate(
            message,
            min_amount=min_amount,
            max_amount=max_amount,
        )


# Singleton instance
_parser: MessageParser | None = None


def get_message_parser() -> MessageParser:
    """
    Get singleton parser instance.

    Returns:
        MessageParser instance
    """
    global _parser
    if _parser is None:
        _parser = MessageParser()
    return _parser


__all__ = [
    "MessageParser",
    "get_message_parser",
]
