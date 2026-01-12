"""
Payment amount extraction and validation service.

Extracts and validates payment amounts from user messages,
filtering out DNI-like values and handling identification flow state.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domains.pharmacy.agents.entity_extractor import PharmacyEntityExtractor
from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
    STEP_AWAITING_ACCOUNT_SELECTION,
    STEP_AWAITING_IDENTIFIER,
    STEP_NAME,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PaymentAmountExtractor:
    """
    Service for extracting and validating payment amounts from messages.

    Responsibilities:
    - Extract payment amount using entity extractor
    - Filter out DNI-like values (6+ digit pure numbers >= 1,000,000)
    - Validate amount > 0
    - Determine if extraction should be skipped during identification flow

    This service ensures that payment amounts like "pagar 3000" are captured
    from initial messages while preventing DNI numbers from being misidentified
    as payment amounts.
    """

    def extract_if_valid(self, message: str, state_dict: dict[str, Any]) -> float | None:
        """
        Extract payment amount from message if valid and appropriate.

        Args:
            message: User message to extract from
            state_dict: Current state dictionary

        Returns:
            Extracted amount if valid and appropriate, None otherwise
        """
        # Skip extraction during identification flow to avoid treating DNI as amount
        if self.should_skip_extraction(state_dict):
            return None

        if not message or state_dict.get("payment_amount"):
            return None

        extractor = PharmacyEntityExtractor()
        entities = extractor.extract(None, message.lower())
        extracted_amount = entities.get("amount")

        # SAFETY: Reject amounts that look like DNI (6+ digit pure numbers)
        # DNI range: 1,000,000 to 99,999,999
        # Valid payment amounts typically < 1,000,000
        if self.is_dni_like(extracted_amount, message):
            logger.debug(f"[EXTRACT] Skipped DNI-like value: {extracted_amount}")
            return None

        if extracted_amount and extracted_amount > 0:
            logger.info(
                f"[EXTRACT] payment_amount={extracted_amount} from initial message: "
                f"'{message[:50]}...'"
            )
            return extracted_amount

        return None

    def should_skip_extraction(self, state_dict: dict[str, Any]) -> bool:
        """
        Determine if payment amount extraction should be skipped.

        Args:
            state_dict: Current state dictionary

        Returns:
            True if extraction should be skipped
        """
        # Skip during specific identification steps
        identification_step = state_dict.get("identification_step")
        if identification_step in (
            STEP_AWAITING_IDENTIFIER,
            STEP_AWAITING_ACCOUNT_SELECTION,
            STEP_NAME,
        ):
            return True

        # SAFETY: Also skip if customer not yet identified
        if not state_dict.get("customer_identified"):
            return True

        return False

    def is_dni_like(self, amount: float | None, message: str) -> bool:
        """
        Check if extracted amount looks like a DNI number.

        DNI range: 1,000,000 to 99,999,999
        Valid payment amounts typically < 1,000,000

        Args:
            amount: Extracted amount to check
            message: Original message for verification

        Returns:
            True if amount looks like DNI
        """
        if not amount:
            return False

        return (
            amount >= 1_000_000
            and message.strip().isdigit()
        )


__all__ = ["PaymentAmountExtractor"]
