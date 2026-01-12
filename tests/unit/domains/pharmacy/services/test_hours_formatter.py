"""Tests for PharmacyHoursFormatter service."""

import pytest

from app.domains.pharmacy.services.hours_formatter import PharmacyHoursFormatter


class TestPharmacyHoursFormatter:
    """Test suite for PharmacyHoursFormatter."""

    @pytest.fixture
    def formatter(self) -> PharmacyHoursFormatter:
        """Create formatter instance for testing."""
        return PharmacyHoursFormatter()

    class TestFormat:
        """Tests for format method."""

        @pytest.fixture
        def formatter(self) -> PharmacyHoursFormatter:
            return PharmacyHoursFormatter()

        def test_formats_24h_pharmacy(self, formatter: PharmacyHoursFormatter):
            """Test formatting for 24-hour pharmacy."""
            info = {"is_24h": True}
            result = formatter.format(info)
            assert result == "Abierto 24 horas, todos los días"

        def test_formats_regular_hours(self, formatter: PharmacyHoursFormatter):
            """Test formatting regular hours dictionary.

            The formatter groups consecutive days with the same hours for better UX.
            """
            info = {
                "hours": {
                    "Lunes": "08:00 - 20:00",
                    "Martes": "08:00 - 20:00",
                    "Miércoles": "08:00 - 20:00",
                }
            }
            result = formatter.format(info)

            # Formatter groups consecutive days with same hours
            assert "Lunes a Miércoles" in result
            assert "08:00" in result
            assert "20:00" in result

        def test_returns_not_available_for_none(self, formatter: PharmacyHoursFormatter):
            """Test returning 'No disponible' for None input."""
            assert formatter.format(None) == "No disponible"

        def test_returns_not_available_for_empty_hours(self, formatter: PharmacyHoursFormatter):
            """Test returning 'No disponible' for empty hours."""
            assert formatter.format({}) == "No disponible"
            assert formatter.format({"hours": None}) == "No disponible"
            assert formatter.format({"hours": {}}) == "No disponible"

        def test_returns_not_available_for_invalid_hours_type(
            self, formatter: PharmacyHoursFormatter
        ):
            """Test returning 'No disponible' for invalid hours type."""
            assert formatter.format({"hours": "invalid"}) == "No disponible"
            assert formatter.format({"hours": ["list", "of", "items"]}) == "No disponible"

    class TestFormatCompact:
        """Tests for format_compact method."""

        @pytest.fixture
        def formatter(self) -> PharmacyHoursFormatter:
            return PharmacyHoursFormatter()

        def test_formats_24h_compact(self, formatter: PharmacyHoursFormatter):
            """Test compact format for 24-hour pharmacy."""
            info = {"is_24h": True}
            result = formatter.format_compact(info)
            assert result == "24 horas"

        def test_formats_same_hours_all_days(self, formatter: PharmacyHoursFormatter):
            """Test compact format when all days have same hours."""
            info = {
                "hours": {
                    "Lunes": "09:00 - 18:00",
                    "Martes": "09:00 - 18:00",
                    "Miércoles": "09:00 - 18:00",
                }
            }
            result = formatter.format_compact(info)
            assert "Todos los días: 09:00 - 18:00" in result

        def test_returns_detailed_for_different_hours(self, formatter: PharmacyHoursFormatter):
            """Test returning detailed format when hours differ."""
            info = {
                "hours": {
                    "Lunes": "09:00 - 18:00",
                    "Sábado": "10:00 - 14:00",
                }
            }
            result = formatter.format_compact(info)
            # Should return detailed format since hours are different
            assert "Lunes" in result
            assert "Sábado" in result

        def test_returns_not_available_for_empty(self, formatter: PharmacyHoursFormatter):
            """Test returning 'No disponible' for empty input."""
            assert formatter.format_compact(None) == "No disponible"
            assert formatter.format_compact({}) == "No disponible"

    class TestIsOpen24h:
        """Tests for is_open_24h method."""

        @pytest.fixture
        def formatter(self) -> PharmacyHoursFormatter:
            return PharmacyHoursFormatter()

        def test_returns_true_for_24h_pharmacy(self, formatter: PharmacyHoursFormatter):
            """Test returning True for 24-hour pharmacy."""
            assert formatter.is_open_24h({"is_24h": True}) is True

        def test_returns_false_for_regular_pharmacy(self, formatter: PharmacyHoursFormatter):
            """Test returning False for regular pharmacy."""
            assert formatter.is_open_24h({"is_24h": False}) is False
            assert formatter.is_open_24h({}) is False

        def test_returns_false_for_none(self, formatter: PharmacyHoursFormatter):
            """Test returning False for None input."""
            assert formatter.is_open_24h(None) is False
