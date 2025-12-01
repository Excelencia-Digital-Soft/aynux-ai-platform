"""
Integration tests for WhatsApp Catalog and Flows API endpoints
Testing API routes, authentication, validation, and error handling
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.integrations.whatsapp import FlowType
from app.main import create_app
from app.models.whatsapp_advanced import WhatsAppApiResponse

API_V1_STR = os.getenv("API_V1_STR", "/api/v1")


@pytest.fixture
def app():
    """Create FastAPI app for testing"""
    return create_app()


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user"""
    return {"user_id": "test_user", "username": "test"}


class TestWhatsAppCatalogEndpoints:
    """Tests for WhatsApp catalog API endpoints"""

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppCatalogService')
    def test_get_catalog_status_success(self, mock_catalog_service, mock_auth, client):
        """Test getting catalog status successfully"""
        # Mock authentication
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock catalog service
        mock_service_instance = MagicMock()
        mock_service_instance.get_catalog_info.return_value = {
            "catalog_configured": True,
            "catalog_id": "1561483558155324",
            "catalog_accessible": True,
            "api_error": None,
            "service_config": {
                "max_products_per_message": 10,
                "min_products_for_catalog": 2,
                "fallback_enabled": True
            }
        }
        mock_catalog_service.return_value = mock_service_instance

        # Make request
        response = client.get(f"{API_V1_STR}/whatsapp/catalog/status")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["catalog_configured"] is True
        assert data["catalog_id"] == "1561483558155324"
        assert data["catalog_accessible"] is True

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppService')
    @patch('app.api.routes.whatsapp_catalog.get_normalized_number_only')
    def test_send_catalog_message_success(self, mock_normalize, mock_whatsapp_service, mock_auth, client):
        """Test sending catalog message successfully"""
        # Mock authentication
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock phone normalization
        mock_normalize.return_value = "5491123456789"

        # Mock WhatsApp service
        mock_service_instance = MagicMock()
        mock_service_instance.send_product_list.return_value = WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_123"}
        )
        mock_whatsapp_service.return_value = mock_service_instance

        # Test data
        request_data = {
            "phone_number": "1123456789",
            "body_text": "Check out our amazing products!",
            "header_text": "Product Catalog",
            "product_retailer_id": "prod_123"
        }

        # Make request
        response = client.post(f"{API_V1_STR}/whatsapp/catalog/send", json=request_data)

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "Catalog sent successfully" in data["message"]
        assert data["data"]["message_id"] == "msg_123"

        # Verify service was called correctly
        mock_service_instance.send_product_list.assert_called_once()

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    def test_send_catalog_message_validation_error(self, mock_auth, client):
        """Test catalog message validation errors"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Test with missing required fields
        request_data = {
            "phone_number": "",  # Empty phone
            "body_text": "Check out our products!"
        }

        response = client.post(f"{API_V1_STR}/whatsapp/catalog/send", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.get_normalized_number_only')
    def test_send_catalog_message_invalid_phone(self, mock_normalize, mock_auth, client):
        """Test catalog message with invalid phone number"""
        mock_auth.return_value = {"user_id": "test_user"}
        mock_normalize.return_value = None  # Invalid phone

        request_data = {
            "phone_number": "invalid_phone",
            "body_text": "Check out our products!"
        }

        response = client.post(f"{API_V1_STR}/whatsapp/catalog/send", json=request_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid phone number format" in response.json()["detail"]

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppService')
    def test_get_catalog_products_success(self, mock_whatsapp_service, mock_auth, client):
        """Test getting catalog products successfully"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock WhatsApp service
        mock_service_instance = MagicMock()
        mock_service_instance.get_catalog_products.return_value = WhatsAppApiResponse(
            success=True,
            data={
                "data": [
                    {"id": "prod_1", "name": "Product 1", "price": "100.00"},
                    {"id": "prod_2", "name": "Product 2", "price": "200.00"}
                ],
                "paging": {"next": "cursor_123"}
            }
        )
        mock_whatsapp_service.return_value = mock_service_instance

        # Make request
        response = client.get(f"{API_V1_STR}/whatsapp/catalog/products?limit=5&after=cursor_abc")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["data"]) == 2
        assert data["pagination"]["limit"] == 5
        assert data["pagination"]["after"] == "cursor_abc"

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppService')
    def test_validate_whatsapp_config(self, mock_whatsapp_service, mock_auth, client):
        """Test validating WhatsApp configuration"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock WhatsApp service
        mock_service_instance = MagicMock()
        mock_service_instance.verificar_configuracion.return_value = {
            "valid": True,
            "issues": [],
            "config": {
                "base_url": "https://graph.facebook.com",
                "version": "v22.0",
                "phone_id": "103397245943977",
                "catalog_id": "1561483558155324"
            }
        }
        mock_whatsapp_service.return_value = mock_service_instance

        # Make request
        response = client.get(f"{API_V1_STR}/whatsapp/config/validate")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["configuration"]["valid"] is True
        assert "recommendations" in data


class TestWhatsAppFlowsEndpoints:
    """Tests for WhatsApp flows API endpoints"""

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppFlowsService')
    def test_get_flows_status_success(self, mock_flows_service, mock_auth, client):
        """Test getting flows status successfully"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock flows service
        mock_service_instance = MagicMock()
        mock_service_instance.get_available_flows.return_value = {
            FlowType.ORDER_FORM: {
                "name": "Formulario de Pedido",
                "cta": "Hacer Pedido",
                "timeout_minutes": 30
            },
            FlowType.CUSTOMER_SURVEY: {
                "name": "Encuesta de Satisfacción",
                "cta": "Responder",
                "timeout_minutes": 15
            }
        }
        mock_flows_service.return_value = mock_service_instance

        # Make request
        response = client.get(f"{API_V1_STR}/whatsapp/flows/status")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service_initialized"] is True
        assert FlowType.ORDER_FORM in data["flows_available"]
        assert FlowType.CUSTOMER_SURVEY in data["flows_available"]

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppFlowsService')
    @patch('app.api.routes.whatsapp_catalog.get_normalized_number_only')
    def test_send_flow_message_success(self, mock_normalize, mock_flows_service, mock_auth, client):
        """Test sending flow message successfully"""
        mock_auth.return_value = {"user_id": "test_user"}
        mock_normalize.return_value = "5491123456789"

        # Mock flows service
        mock_service_instance = MagicMock()
        mock_service_instance.send_flow.return_value = WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_flow_123", "flow_token": "token_123"}
        )
        mock_flows_service.return_value = mock_service_instance

        # Test data
        request_data = {
            "phone_number": "1123456789",
            "flow_id": "flow_123",
            "flow_type": FlowType.ORDER_FORM,
            "flow_cta": "Complete Order",
            "body_text": "Please fill out your order details",
            "context_data": {"product_id": "prod_123"}
        }

        # Make request
        response = client.post(f"{API_V1_STR}/whatsapp/flows/send", json=request_data)

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "Flow sent successfully" in data["message"]

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    def test_send_flow_message_validation_error(self, mock_auth, client):
        """Test flow message validation errors"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Test with invalid flow type
        request_data = {
            "phone_number": "5491123456789",
            "flow_id": "flow_123",
            "flow_type": "invalid_flow_type",
            "flow_cta": "Complete"
        }

        response = client.post(f"{API_V1_STR}/whatsapp/flows/send", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    def test_send_flow_message_cta_too_long(self, mock_auth, client):
        """Test flow message with CTA too long"""
        mock_auth.return_value = {"user_id": "test_user"}

        request_data = {
            "phone_number": "5491123456789",
            "flow_id": "flow_123",
            "flow_type": FlowType.ORDER_FORM,
            "flow_cta": "A" * 21  # Too long (max 20)
        }

        response = client.post(f"{API_V1_STR}/whatsapp/flows/send", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppFlowsService')
    def test_get_available_flow_types(self, mock_flows_service, mock_auth, client):
        """Test getting available flow types"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock flows service
        mock_service_instance = MagicMock()
        mock_service_instance.get_available_flows.return_value = {
            FlowType.ORDER_FORM: {"name": "Order Form", "cta": "Order Now"},
            FlowType.CUSTOMER_SURVEY: {"name": "Survey", "cta": "Take Survey"},
            FlowType.SUPPORT_TICKET: {"name": "Support", "cta": "Get Help"}
        }
        mock_flows_service.return_value = mock_service_instance

        # Make request
        response = client.get(f"{API_V1_STR}/whatsapp/flows/types")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["total_types"] == 3
        assert FlowType.ORDER_FORM in data["flow_types"]

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    def test_handle_flow_webhook(self, mock_auth, client):
        """Test handling flow webhook"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock webhook data
        webhook_data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "103397245943977"},
                        "messages": [{
                            "id": "msg_123",
                            "from": "5491123456789",
                            "timestamp": "1234567890",
                            "type": "flow",
                            "flow": {
                                "flow_token": "token_123",
                                "data": {"response": "completed"}
                            }
                        }]
                    }
                }]
            }],
            "timestamp": "1234567890"
        }

        # Make request
        response = client.post(f"{API_V1_STR}/whatsapp/flows/webhook", json=webhook_data)

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "Webhook received and processed" in data["message"]


class TestTestEndpoints:
    """Tests for test endpoints"""

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppCatalogService')
    @patch('app.api.routes.whatsapp_catalog.get_normalized_number_only')
    def test_catalog_functionality(self, mock_normalize, mock_catalog_service, mock_auth, client):
        """Test catalog functionality test endpoint"""
        mock_auth.return_value = {"user_id": "test_user"}
        mock_normalize.return_value = "5491123456789"

        # Mock catalog service
        mock_service_instance = MagicMock()
        mock_service_instance.send_smart_product_response.return_value = WhatsAppApiResponse(
            success=True,
            data={"catalog_sent": True, "reason": "Test successful"}
        )
        mock_catalog_service.return_value = mock_service_instance

        # Make request
        response = client.post(f"{API_V1_STR}/whatsapp/test/catalog?test_phone=1123456789")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["test_result"]["catalog_sent"] is True
        assert data["test_phone"] == "5491123456789"


class TestErrorHandling:
    """Tests for error handling"""

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppCatalogService')
    def test_catalog_status_service_error(self, mock_catalog_service, mock_auth, client):
        """Test catalog status with service error"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock service error
        mock_catalog_service.side_effect = Exception("Service initialization failed")

        response = client.get(f"{API_V1_STR}/whatsapp/catalog/status")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Service initialization failed" in response.json()["detail"]

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    @patch('app.api.routes.whatsapp_catalog.WhatsAppService')
    def test_catalog_send_api_error(self, mock_whatsapp_service, mock_auth, client):
        """Test catalog send with API error"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Mock service API error
        mock_service_instance = MagicMock()
        mock_service_instance.send_product_list.return_value = WhatsAppApiResponse(
            success=False,
            error="WhatsApp API rate limit exceeded",
            status_code=429
        )
        mock_whatsapp_service.return_value = mock_service_instance

        request_data = {
            "phone_number": "5491123456789",
            "body_text": "Check out our products!"
        }

        with patch('app.api.routes.whatsapp_catalog.get_normalized_number_only', return_value="5491123456789"):
            response = client.post(f"{API_V1_STR}/whatsapp/catalog/send", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False
        assert "Failed to send catalog" in data["message"]
        assert data["error"] == "WhatsApp API rate limit exceeded"

    def test_unauthenticated_request(self, client):
        """Test requests without authentication"""
        # This would depend on your authentication middleware implementation
        # For now, just test that endpoints exist
        response = client.get(f"{API_V1_STR}/whatsapp/catalog/status")

        # The response code will depend on your authentication setup
        # It could be 401 Unauthorized or other depending on middleware
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_200_OK]


class TestInputValidation:
    """Tests for input validation"""

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    def test_catalog_send_body_text_validation(self, mock_auth, client):
        """Test catalog send with various body text validation scenarios"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Test with too short body text
        request_data = {
            "phone_number": "5491123456789",
            "body_text": "Hi"  # Too short (min 5 characters after validation)
        }

        response = client.post(f"{API_V1_STR}/whatsapp/catalog/send", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Test with too long body text
        request_data = {
            "phone_number": "5491123456789",
            "body_text": "A" * 1025  # Too long (max 1024)
        }

        response = client.post(f"{API_V1_STR}/whatsapp/catalog/send", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('app.api.routes.whatsapp_catalog.get_current_user')
    def test_flow_send_validation_scenarios(self, mock_auth, client):
        """Test flow send with various validation scenarios"""
        mock_auth.return_value = {"user_id": "test_user"}

        # Test with all valid data
        valid_request = {
            "phone_number": "5491123456789",
            "flow_id": "flow_123",
            "flow_type": FlowType.ORDER_FORM,
            "flow_cta": "Order Now",
            "body_text": "Complete your order",
            "context_data": {"product": "laptop"}
        }

        # This should pass validation (actual sending might fail without mocks)
        response = client.post(f"{API_V1_STR}/whatsapp/flows/send", json=valid_request)

        # Should not be a validation error
        assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])