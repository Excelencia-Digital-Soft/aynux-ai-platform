"""Tests for GreetingDetector utility."""

import pytest

from app.domains.pharmacy.agents.utils.greeting_detector import GreetingDetector


class TestGreetingDetector:
    """Test suite for GreetingDetector."""

    @pytest.fixture
    def detector(self) -> GreetingDetector:
        """Create detector instance for testing."""
        return GreetingDetector()

    class TestHasContentBeyondGreeting:
        """Tests for has_content_beyond_greeting method."""

        @pytest.fixture
        def detector(self) -> GreetingDetector:
            return GreetingDetector()

        @pytest.mark.parametrize(
            "message,expected",
            [
                # Pure greetings - should return False
                ("hola", False),
                ("Hola", False),
                ("HOLA", False),
                ("buenas", False),
                ("buenos dias", False),
                ("buen día", False),
                ("buenas tardes", False),
                ("buenas noches", False),
                ("saludos", False),
                ("que tal", False),
                ("qué tal", False),
                ("hi", False),
                ("hello", False),
                # Greetings with content - should return True
                ("hola quiero ver mi deuda", True),
                ("buenas cual es mi saldo", True),
                ("buenos dias necesito ayuda", True),
                # Long messages - should return True
                ("hola como estan espero que bien quiero saber mi deuda", True),
                # Non-greetings - should return True
                ("quiero ver mi deuda", True),
                ("cual es mi saldo", True),
                # Edge cases
                (None, False),
                ("", False),
                ("   ", False),
            ],
        )
        def test_various_messages(
            self, detector: GreetingDetector, message: str | None, expected: bool
        ):
            """Test various message types for content detection."""
            assert detector.has_content_beyond_greeting(message) is expected

        def test_greeting_with_whitespace(self, detector: GreetingDetector):
            """Test that whitespace is properly stripped."""
            assert detector.has_content_beyond_greeting("  hola  ") is False
            assert detector.has_content_beyond_greeting("  hola que tal  ") is True

    class TestIsPureGreeting:
        """Tests for is_pure_greeting method."""

        @pytest.fixture
        def detector(self) -> GreetingDetector:
            return GreetingDetector()

        def test_pure_greetings_return_true(self, detector: GreetingDetector):
            """Test that pure greetings are correctly identified."""
            pure_greetings = ["hola", "buenas", "buenos dias", "hi", "hello"]
            for greeting in pure_greetings:
                assert detector.is_pure_greeting(greeting) is True

        def test_greetings_with_content_return_false(self, detector: GreetingDetector):
            """Test that greetings with content return False."""
            assert detector.is_pure_greeting("hola quiero pagar") is False
            assert detector.is_pure_greeting("buenas necesito ayuda") is False

    class TestExtractGreetingPrefix:
        """Tests for extract_greeting_prefix method."""

        @pytest.fixture
        def detector(self) -> GreetingDetector:
            return GreetingDetector()

        def test_extracts_pure_greeting(self, detector: GreetingDetector):
            """Test extraction of pure greetings."""
            assert detector.extract_greeting_prefix("hola") == "hola"
            assert detector.extract_greeting_prefix("buenas") == "buenas"

        def test_extracts_greeting_prefix_from_message(self, detector: GreetingDetector):
            """Test extraction of greeting prefix from longer message."""
            assert detector.extract_greeting_prefix("hola como estas") == "hola"
            assert detector.extract_greeting_prefix("buenas tardes") == "buenas tardes"

        def test_returns_none_for_no_greeting(self, detector: GreetingDetector):
            """Test that non-greetings return None."""
            assert detector.extract_greeting_prefix("quiero pagar") is None
            assert detector.extract_greeting_prefix(None) is None
            assert detector.extract_greeting_prefix("") is None
