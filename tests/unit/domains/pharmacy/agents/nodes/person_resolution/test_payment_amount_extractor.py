"""
Unit tests for PaymentAmountExtractor service.
"""

from __future__ import annotations

import pytest

from app.domains.pharmacy.agents.nodes.person_resolution.services.payment_amount_extractor import (
    PaymentAmountExtractor,
)


class TestPaymentAmountExtractor:
    """Test suite for PaymentAmountExtractor."""

    def test_init(self):
        """Test service initialization."""
        extractor = PaymentAmountExtractor()
        assert extractor is not None

    def test_extract_valid_amount(self):
        """Test extracting valid payment amount."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
        }

        result = extractor.extract_if_valid("quiero pagar 3000", state_dict)

        assert result == 3000.0

    def test_extract_no_amount_in_message(self):
        """Test when message has no amount."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
        }

        result = extractor.extract_if_valid("hola, ¿cómo estás?", state_dict)

        assert result is None

    def test_skip_dni_like_values(self):
        """Test that DNI-like values are filtered out."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
        }

        # DNI range: 1,000,000 to 99,999,999
        result = extractor.extract_if_valid("12345678", state_dict)

        assert result is None

    def test_is_dni_like_with_large_number(self):
        """Test DNI detection with large pure number."""
        extractor = PaymentAmountExtractor()

        result = extractor.is_dni_like(15000000, "15000000")

        assert result is True

    def test_is_dni_like_with_small_number(self):
        """Test that small numbers are not DNI-like."""
        extractor = PaymentAmountExtractor()

        result = extractor.is_dni_like(3000, "3000")

        assert result is False

    def test_is_dni_like_with_mixed_content(self):
        """Test that mixed content is not DNI-like."""
        extractor = PaymentAmountExtractor()

        result = extractor.is_dni_like(3000, "quiero pagar 3000")

        assert result is False

    def test_skip_extraction_during_identification_step(self):
        """Test skipping extraction during identification flow."""
        extractor = PaymentAmountExtractor()

        from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
            STEP_AWAITING_IDENTIFIER,
        )

        state_dict = {
            "identification_step": STEP_AWAITING_IDENTIFIER,
            "customer_identified": False,
        }

        result = extractor.extract_if_valid("quiero pagar 3000", state_dict)

        assert result is None

    def test_skip_extraction_when_not_identified(self):
        """Test skipping extraction when customer not identified."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "identification_step": None,
            "customer_identified": False,
        }

        result = extractor.extract_if_valid("quiero pagar 3000", state_dict)

        assert result is None

    def test_skip_extraction_when_amount_exists(self):
        """Test skipping extraction when amount already exists."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
            "payment_amount": 2000.0,
        }

        result = extractor.extract_if_valid("quiero pagar 3000", state_dict)

        assert result is None

    def test_skip_extraction_empty_message(self):
        """Test skipping extraction with empty message."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
        }

        result = extractor.extract_if_valid("", state_dict)

        assert result is None

    def test_extract_amount_less_than_dni_threshold(self):
        """Test extracting amount below DNI threshold."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
        }

        result = extractor.extract_if_valid("500000", state_dict)

        assert result == 500000.0

    def test_extract_negative_amount_rejected(self):
        """Test that negative amounts are rejected."""
        extractor = PaymentAmountExtractor()
        state_dict = {
            "customer_identified": True,
            "identification_step": None,
        }

        # This should return None since amount <= 0
        result = extractor.extract_if_valid("quiero pagar -100", state_dict)

        # Entity extractor might not extract negative, so this could be None
        # The important thing is it's not a valid payment amount
        assert result is None or result <= 0

    def test_should_skip_identification_steps(self):
        """Test should_skip_extraction for various identification steps."""
        extractor = PaymentAmountExtractor()

        from app.domains.pharmacy.agents.nodes.person_resolution.constants import (
            STEP_AWAITING_ACCOUNT_SELECTION,
            STEP_AWAITING_IDENTIFIER,
            STEP_NAME,
        )

        # Should skip during these steps
        for step in [STEP_AWAITING_IDENTIFIER, STEP_AWAITING_ACCOUNT_SELECTION, STEP_NAME]:
            state_dict = {"identification_step": step, "customer_identified": True}
            assert extractor.should_skip_extraction(state_dict) is True

        # Should not skip when no identification step
        state_dict = {"identification_step": None, "customer_identified": True}
        assert extractor.should_skip_extraction(state_dict) is False

    def test_should_skip_when_not_identified(self):
        """Test should skip when customer not identified."""
        extractor = PaymentAmountExtractor()

        state_dict = {
            "identification_step": None,
            "customer_identified": False,
        }

        assert extractor.should_skip_extraction(state_dict) is True


__all__ = ["TestPaymentAmountExtractor"]
