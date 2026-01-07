"""Tests for PharmacyInfoService."""

from unittest.mock import MagicMock

import pytest

from app.domains.pharmacy.services.pharmacy_info_service import PharmacyInfoService


class TestPharmacyInfoService:
    """Test suite for PharmacyInfoService."""

    @pytest.fixture
    def service(self) -> PharmacyInfoService:
        """Create service instance for testing."""
        return PharmacyInfoService()

    class TestTransformConfigToDict:
        """Tests for _transform_config_to_dict static method."""

        def test_transforms_config_correctly(self):
            """Test transforming pharmacy config to dict."""
            # Create a mock config object
            mock_config = MagicMock()
            mock_config.pharmacy_name = "Farmacia Central"
            mock_config.pharmacy_address = "Calle Principal 123"
            mock_config.pharmacy_phone = "+54 11 1234-5678"
            mock_config.pharmacy_email = "info@farmacia.com"
            mock_config.pharmacy_website = "www.farmacia.com"
            mock_config.pharmacy_hours = {"Lunes": "08:00 - 20:00"}
            mock_config.pharmacy_is_24h = False

            result = PharmacyInfoService._transform_config_to_dict(mock_config)

            assert result["name"] == "Farmacia Central"
            assert result["address"] == "Calle Principal 123"
            assert result["phone"] == "+54 11 1234-5678"
            assert result["email"] == "info@farmacia.com"
            assert result["website"] == "www.farmacia.com"
            assert result["hours"] == {"Lunes": "08:00 - 20:00"}
            assert result["is_24h"] is False

        def test_handles_24h_pharmacy(self):
            """Test handling 24-hour pharmacy config."""
            mock_config = MagicMock()
            mock_config.pharmacy_name = "Farmacia 24h"
            mock_config.pharmacy_address = "Avenida 456"
            mock_config.pharmacy_phone = None
            mock_config.pharmacy_email = None
            mock_config.pharmacy_website = None
            mock_config.pharmacy_hours = None
            mock_config.pharmacy_is_24h = True

            result = PharmacyInfoService._transform_config_to_dict(mock_config)

            assert result["name"] == "Farmacia 24h"
            assert result["is_24h"] is True
            assert result["hours"] is None

    class TestGetPharmacyInfo:
        """Tests for get_pharmacy_info method - validation logic only."""

        @pytest.fixture
        def service(self) -> PharmacyInfoService:
            return PharmacyInfoService()

        @pytest.mark.asyncio
        async def test_returns_none_for_empty_pharmacy_id(
            self, service: PharmacyInfoService
        ):
            """Test returning None when pharmacy_id is empty."""
            result = await service.get_pharmacy_info(None)
            assert result is None

            result = await service.get_pharmacy_info("")
            assert result is None

        @pytest.mark.asyncio
        async def test_returns_none_for_invalid_uuid(self, service: PharmacyInfoService):
            """Test returning None for invalid UUID format."""
            result = await service.get_pharmacy_info("not-a-uuid")
            assert result is None

            result = await service.get_pharmacy_info("12345")
            assert result is None

    class TestGetPharmacyName:
        """Tests for get_pharmacy_name method."""

        @pytest.fixture
        def service(self) -> PharmacyInfoService:
            return PharmacyInfoService()

        @pytest.mark.asyncio
        async def test_returns_default_for_empty_id(self, service: PharmacyInfoService):
            """Test returning default name for empty pharmacy_id."""
            result = await service.get_pharmacy_name(None)
            assert result == "la farmacia"

            result = await service.get_pharmacy_name("")
            assert result == "la farmacia"

    class TestGetContactInfo:
        """Tests for get_contact_info method."""

        @pytest.fixture
        def service(self) -> PharmacyInfoService:
            return PharmacyInfoService()

        @pytest.mark.asyncio
        async def test_returns_empty_contact_for_invalid_id(
            self, service: PharmacyInfoService
        ):
            """Test returning empty contact info for invalid pharmacy_id."""
            result = await service.get_contact_info(None)

            assert result["phone"] is None
            assert result["email"] is None
            assert result["address"] is None
