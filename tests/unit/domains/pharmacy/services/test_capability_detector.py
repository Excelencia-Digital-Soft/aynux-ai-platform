"""Tests for CapabilityQuestionDetector service."""

import pytest

from app.domains.pharmacy.services.capability_detector import CapabilityQuestionDetector


class TestCapabilityQuestionDetector:
    """Test suite for CapabilityQuestionDetector."""

    @pytest.fixture
    def detector(self) -> CapabilityQuestionDetector:
        """Create detector instance for testing."""
        return CapabilityQuestionDetector()

    class TestIsCapabilityQuestion:
        """Tests for is_capability_question method."""

        @pytest.fixture
        def detector(self) -> CapabilityQuestionDetector:
            return CapabilityQuestionDetector()

        @pytest.mark.parametrize(
            "message,expected",
            [
                # Direct capability questions - should return True
                ("que puedes hacer", True),
                ("qué puedes hacer", True),
                ("que puedes hacer?", True),
                ("Que puedes hacer", True),  # Case insensitive
                ("QUE PUEDES HACER", True),  # Uppercase
                ("que haces", True),
                ("qué haces", True),
                ("que sabes hacer", True),
                # Purpose questions - should return True
                ("para que sirves", True),
                ("para qué sirves", True),
                # Service questions - should return True
                ("que servicios ofreces", True),
                ("qué ofreces", True),
                # Help questions - should return True
                ("en que me ayudas", True),
                ("como puedes ayudar", True),
                ("cómo puedes ayudar", True),
                # Function questions - should return True
                ("como funciona", True),
                ("cómo funcionas", True),
                # Messages with capability phrases embedded
                ("hola, que puedes hacer por mi", True),
                ("buenas, que servicios ofreces?", True),
                # Non-capability questions - should return False
                ("cual es mi deuda", False),
                ("quiero pagar", False),
                ("cual es el horario", False),
                ("donde queda la farmacia", False),
                ("hola", False),
                ("buenas tardes", False),
                # Edge cases
                (None, False),
                ("", False),
                ("   ", False),
            ],
        )
        def test_various_messages(
            self, detector: CapabilityQuestionDetector, message: str | None, expected: bool
        ):
            """Test various message types for capability detection."""
            result = detector.is_capability_question(message) if message else detector.is_capability_question("")
            if message is None:
                result = detector.is_capability_question(message)
            assert result is expected

    class TestExtractCapabilityIntent:
        """Tests for extract_capability_intent method."""

        @pytest.fixture
        def detector(self) -> CapabilityQuestionDetector:
            return CapabilityQuestionDetector()

        def test_extracts_capability_phrase(self, detector: CapabilityQuestionDetector):
            """Test extracting capability phrase from message."""
            result = detector.extract_capability_intent("que puedes hacer?")
            # Should match one of the capability phrases containing "puedes hacer"
            assert result is not None
            assert "puedes" in result

        def test_extracts_from_longer_message(self, detector: CapabilityQuestionDetector):
            """Test extracting capability phrase from longer message."""
            result = detector.extract_capability_intent("hola, que servicios ofreces?")
            # Should match one of the capability phrases
            assert result is not None
            assert "servicios" in result or "ofreces" in result

        def test_returns_none_for_non_capability(self, detector: CapabilityQuestionDetector):
            """Test returning None for non-capability messages."""
            assert detector.extract_capability_intent("cual es mi deuda") is None
            assert detector.extract_capability_intent("quiero pagar") is None

        def test_returns_none_for_empty(self, detector: CapabilityQuestionDetector):
            """Test returning None for empty input."""
            assert detector.extract_capability_intent(None) is None
            assert detector.extract_capability_intent("") is None
