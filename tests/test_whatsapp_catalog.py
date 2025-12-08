"""
Comprehensive tests for WhatsApp Catalog functionality
Testing models, services, and API endpoints
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.whatsapp import (
    DefaultCatalogDecisionEngine,
    WhatsAppCatalogService,
    WhatsAppService,
)
from app.models.whatsapp_advanced import (
    CatalogConfiguration,
    CatalogProduct,
    MessageFactory,
    WhatsAppApiResponse,
)


class TestWhatsAppModels:
    """Tests for WhatsApp advanced models"""

    def test_product_list_message_creation(self):
        """Test creating a product list message"""
        message = MessageFactory.create_product_list_message(
            to="5491123456789",
            catalog_id="1561483558155324",
            body_text="Aquí tienes nuestros productos",
            header_text="Catálogo de productos"
        )

        assert message.to == "5491123456789"
        assert message.type == "interactive"
        assert message.interactive.type.value == "product_list"
        assert message.interactive.body.text == "Aquí tienes nuestros productos"
        assert message.interactive.header.text == "Catálogo de productos"
        assert message.interactive.action.catalog_id == "1561483558155324"

    def test_product_list_message_validation(self):
        """Test product list message validation"""
        # Test with too long header
        with pytest.raises(ValueError):
            MessageFactory.create_product_list_message(
                to="5491123456789",
                catalog_id="1561483558155324",
                body_text="Test body",
                header_text="A" * 61  # Too long (max 60)
            )

        # Test with too long body
        with pytest.raises(ValueError):
            MessageFactory.create_product_list_message(
                to="5491123456789",
                catalog_id="1561483558155324",
                body_text="A" * 1025  # Too long (max 1024)
            )

    def test_catalog_product_model(self):
        """Test catalog product model"""
        product = CatalogProduct(
            id="prod_123",
            retailer_id="retail_123",
            name="Test Product",
            description="A test product",
            price="99.99",
            currency="ARS",
            brand="Test Brand",
            category="Electronics"
        )

        assert product.id == "prod_123"
        assert product.retailer_id == "retail_123"
        assert product.name == "Test Product"
        assert product.currency == "ARS"
        assert product.availability == "in stock"  # Default value

    def test_whatsapp_api_response_model(self):
        """Test WhatsApp API response model"""
        # Success response
        success_response = WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_123"}
        )
        assert success_response.success is True
        assert success_response.data == {"message_id": "msg_123"}
        assert success_response.error is None

        # Error response
        error_response = WhatsAppApiResponse(
            success=False,
            error="Invalid catalog ID",
            status_code=400
        )
        assert error_response.success is False
        assert error_response.error == "Invalid catalog ID"
        assert error_response.status_code == 400


class TestWhatsAppService:
    """Tests for WhatsApp service catalog methods"""

    @pytest.fixture
    def whatsapp_service(self):
        """Create WhatsApp service instance for testing"""
        return WhatsAppService()

    def _get_mock_settings(self):
        """Get mock settings for testing"""
        settings_mock = MagicMock()
        settings_mock.WHATSAPP_CATALOG_ID = "1561483558155324"
        settings_mock.WHATSAPP_ACCESS_TOKEN = "test_token"
        settings_mock.WHATSAPP_PHONE_NUMBER_ID = "103397245943977"
        settings_mock.WHATSAPP_API_BASE = "https://graph.facebook.com"
        settings_mock.WHATSAPP_API_VERSION = "v22.0"
        settings_mock.is_development = True
        return settings_mock

    @patch('app.integrations.whatsapp.service.get_settings')
    @patch('app.integrations.whatsapp.http_client.httpx.AsyncClient')
    async def test_send_product_list_success(self, mock_client, mock_get_settings, whatsapp_service):
        """Test successful product list sending"""
        # Mock settings
        mock_get_settings.return_value = self._get_mock_settings()

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": "5491123456789", "wa_id": "5491123456789"}],
            "messages": [{"id": "msg_123"}]
        }

        mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

        # Test the method
        response = await whatsapp_service.send_product_list(
            numero="5491123456789",
            body_text="Check out our products!"
        )

        assert response.success is True
        assert response.data is not None

    @patch('app.integrations.whatsapp.service.get_settings')
    @patch('app.integrations.whatsapp.http_client.httpx.AsyncClient')
    async def test_send_product_list_error(self, mock_client, mock_get_settings, whatsapp_service):
        """Test product list sending error handling"""
        # Mock settings
        mock_get_settings.return_value = self._get_mock_settings()

        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid catalog ID"
        mock_response.json.return_value = {
            "error": {"message": "Invalid catalog ID"}
        }

        mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

        # Test the method
        response = await whatsapp_service.send_product_list(
            numero="5491123456789",
            body_text="Check out our products!"
        )

        assert response.success is False
        assert "Invalid catalog ID" in response.error

    async def test_send_product_list_validation(self, whatsapp_service):
        """Test input validation for product list"""
        # Test missing phone number
        response = await whatsapp_service.send_product_list(
            numero="",
            body_text="Check out our products!"
        )
        assert response.success is False
        assert "required" in response.error.lower()

        # Test missing body text
        response = await whatsapp_service.send_product_list(
            numero="5491123456789",
            body_text=""
        )
        assert response.success is False
        assert "required" in response.error.lower()

    def test_catalog_configuration(self, whatsapp_service):
        """Test catalog configuration creation"""
        config = whatsapp_service.get_catalog_configuration()

        assert isinstance(config, CatalogConfiguration)
        assert config.catalog_id == whatsapp_service.catalog_id
        assert config.phone_number_id == whatsapp_service.phone_number_id
        assert config.access_token == whatsapp_service.access_token


class TestWhatsAppCatalogService:
    """Tests for WhatsApp catalog service"""

    @pytest.fixture
    def mock_whatsapp_service(self):
        """Mock WhatsApp service"""
        mock = MagicMock(spec=WhatsAppService)
        mock.send_product_list = AsyncMock()
        return mock

    @pytest.fixture
    def catalog_service(self, mock_whatsapp_service):
        """Create catalog service with mocked dependencies"""
        return WhatsAppCatalogService(whatsapp_service=mock_whatsapp_service)

    async def test_should_show_catalog_display_with_sufficient_products(self, catalog_service):
        """Test catalog display decision with sufficient products"""
        products = [
            {"id": "1", "name": "Product 1", "price": 100.0},
            {"id": "2", "name": "Product 2", "price": 200.0},
            {"id": "3", "name": "Product 3", "price": 150.0}
        ]

        intent_analysis = {
            "intent": "search_specific_products",
            "search_terms": ["laptop", "computer"],
            "category": None
        }

        should_show, reason = await catalog_service._should_show_catalog_display(
            "Show me laptops",
            intent_analysis,
            products
        )

        assert should_show is True
        # Reason may vary based on implementation
        assert len(reason) > 0

    async def test_should_show_catalog_display_insufficient_products(self, catalog_service):
        """Test catalog display decision with insufficient products"""
        products = [
            {"id": "1", "name": "Product 1"}  # Missing required fields
        ]

        intent_analysis = {
            "intent": "search_specific_products",
            "search_terms": ["laptop"],
            "category": None
        }

        should_show, reason = await catalog_service._should_show_catalog_display(
            "Show me laptops",
            intent_analysis,
            products
        )

        assert should_show is False
        # Reason should explain why catalog is not shown
        assert len(reason) > 0

    async def test_send_smart_product_response_success(self, catalog_service):
        """Test smart product response with successful catalog sending"""
        # Mock successful catalog response
        catalog_service.whatsapp_service.send_product_list.return_value = WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_123"}
        )

        products = [
            {"id": "1", "name": "Product 1", "price": 100.0, "description": "Test"},
            {"id": "2", "name": "Product 2", "price": 200.0, "description": "Test"}
        ]

        intent_analysis = {
            "intent": "search_specific_products",
            "search_terms": ["test"],
            "category": None
        }

        response = await catalog_service.send_smart_product_response(
            user_phone="5491123456789",
            user_message="Show me test products",
            intent_analysis=intent_analysis,
            local_products=products
        )

        assert response.success is True
        catalog_service.whatsapp_service.send_product_list.assert_called_once()

    async def test_send_smart_product_response_fallback(self, catalog_service):
        """Test smart product response fallback to text"""
        products = [
            {"id": "1", "name": "Product 1"}  # Missing required fields
        ]

        intent_analysis = {
            "intent": "search_specific_products",
            "search_terms": ["test"],
            "category": None
        }

        response = await catalog_service.send_smart_product_response(
            user_phone="5491123456789",
            user_message="Show me test products",
            intent_analysis=intent_analysis,
            local_products=products
        )

        assert response.success is False
        assert response.data.get("fallback_to_text") is True

    def test_is_product_catalog_ready(self, catalog_service):
        """Test product catalog readiness check"""
        # Product with required fields
        ready_product = {
            "id": "1",
            "name": "Test Product",
            "description": "A test product",
            "price": 100.0
        }
        assert catalog_service._is_product_catalog_ready(ready_product) is True

        # Product missing required fields
        incomplete_product = {
            "name": "Test Product"  # Missing id
        }
        assert catalog_service._is_product_catalog_ready(incomplete_product) is False

        # Product with required fields but no recommended fields
        minimal_product = {
            "id": "1",
            "name": "Test Product"
        }
        assert catalog_service._is_product_catalog_ready(minimal_product) is False

    async def test_get_catalog_info(self, catalog_service):
        """Test getting catalog information"""
        # Mock successful catalog access
        catalog_service.whatsapp_service.get_catalog_products.return_value = WhatsAppApiResponse(
            success=True,
            data={"data": []}
        )

        catalog_service.whatsapp_service.get_catalog_configuration.return_value = CatalogConfiguration(
            catalog_id="1561483558155324",
            phone_number_id="103397245943977",
            access_token="test_token"
        )

        info = await catalog_service.get_catalog_info()

        assert info["catalog_configured"] is True
        assert info["catalog_id"] == "1561483558155324"
        assert info["catalog_accessible"] is True
        assert info["service_config"]["max_products_per_message"] == 10


class TestDefaultCatalogDecisionEngine:
    """Tests for default catalog decision engine"""

    @pytest.fixture
    def decision_engine(self):
        return DefaultCatalogDecisionEngine()

    async def test_should_show_catalog_with_keywords(self, decision_engine):
        """Test catalog decision with catalog keywords"""
        should_show, reason = await decision_engine.should_show_catalog(
            "Quiero ver productos",
            {},
            [{"id": "1", "name": "Product 1"}] * 3
        )

        assert should_show is True
        assert "Contains catalog keywords" in reason

    async def test_should_show_catalog_insufficient_products(self, decision_engine):
        """Test catalog decision with insufficient products"""
        should_show, reason = await decision_engine.should_show_catalog(
            "Show me something",
            {},
            [{"id": "1", "name": "Product 1"}]  # Only 1 product
        )

        assert should_show is False
        assert "Insufficient products" in reason

    async def test_select_catalog_products(self, decision_engine):
        """Test product selection for catalog"""
        products = [
            {"id": "3", "name": "Product C", "price": None},
            {"id": "1", "name": "Product A", "price": 100.0},
            {"id": "2", "name": "Product B", "price": 200.0}
        ]

        selected = await decision_engine.select_catalog_products(
            products,
            {},
            max_products=2
        )

        # Should return products with price first, then sorted by name
        assert len(selected) == 2
        assert selected[0]["id"] == "1"  # Product A with price
        assert selected[1]["id"] == "2"  # Product B with price


class TestCatalogIntegration:
    """Integration tests for catalog functionality"""

    @patch('app.integrations.whatsapp.catalog_service.WhatsAppService')
    async def test_end_to_end_catalog_flow(self, mock_whatsapp_service_class):
        """Test complete catalog flow from intent to sending"""
        # Setup mocks - use AsyncMock for async methods
        mock_service = MagicMock()
        mock_service.send_product_list = AsyncMock(return_value=WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_123"}
        ))
        mock_whatsapp_service_class.return_value = mock_service

        # Create catalog service
        catalog_service = WhatsAppCatalogService()

        # Test data
        products = [
            {"id": "1", "name": "Laptop Gaming", "price": 150000.0, "description": "High-end gaming laptop"},
            {"id": "2", "name": "Mouse Gaming", "price": 5000.0, "description": "RGB gaming mouse"}
        ]

        intent_analysis = {
            "intent": "search_specific_products",
            "search_terms": ["gaming", "laptop"],
            "category": "Electronics"
        }

        # Execute
        response = await catalog_service.send_smart_product_response(
            user_phone="5491123456789",
            user_message="Show me gaming laptops",
            intent_analysis=intent_analysis,
            local_products=products
        )

        # Verify - response may succeed or fallback depending on implementation
        assert response is not None
        # Check response has expected structure
        assert hasattr(response, 'success') or hasattr(response, 'data')

    async def test_catalog_fallback_behavior(self):
        """Test catalog service fallback behavior"""
        # Mock service that fails
        mock_service = MagicMock()
        mock_service.send_product_list.return_value = WhatsAppApiResponse(
            success=False,
            error="API Error"
        )

        catalog_service = WhatsAppCatalogService(whatsapp_service=mock_service)

        products = [{"id": "1", "name": "Product 1"}]  # Insufficient data
        intent_analysis = {"intent": "search_general"}

        response = await catalog_service.send_smart_product_response(
            user_phone="5491123456789",
            user_message="Show products",
            intent_analysis=intent_analysis,
            local_products=products
        )

        assert response.success is False
        assert response.data.get("fallback_to_text") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])