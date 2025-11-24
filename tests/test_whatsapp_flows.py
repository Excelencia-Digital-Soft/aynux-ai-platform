"""
Comprehensive tests for WhatsApp Flows functionality
Testing models, services, and flow processing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any

from app.models.whatsapp_advanced import (
    FlowMessage,
    FlowDataResponse,
    MessageFactory,
    WhatsAppApiResponse,
    FlowConfiguration,
)
from app.integrations.whatsapp import (
    WhatsAppFlowsService,
    FlowType,
    InMemoryFlowRepository,
    DefaultOrderFormHandler,
)


class TestFlowModels:
    """Tests for WhatsApp Flow models"""

    def test_flow_message_creation(self):
        """Test creating a flow message"""
        message = MessageFactory.create_flow_message(
            to="5491123456789",
            flow_id="flow_123",
            flow_cta="Complete Form",
            body_text="Please fill out this form",
            header_text="Customer Information"
        )

        assert message.to == "5491123456789"
        assert message.type == "interactive"
        assert message.interactive.type.value == "flow"
        assert message.interactive.action.flow_id == "flow_123"
        assert message.interactive.action.flow_cta == "Complete Form"

    def test_flow_message_validation(self):
        """Test flow message validation"""
        # Test with too long CTA
        with pytest.raises(ValueError):
            MessageFactory.create_flow_message(
                to="5491123456789",
                flow_id="flow_123",
                flow_cta="A" * 21,  # Too long (max 20)
            )

    def test_flow_data_response_model(self):
        """Test flow data response model"""
        flow_data = FlowDataResponse(
            flow_token="test_token_123",
            version="1.0",
            data={
                "customer_name": "John Doe",
                "email": "john@example.com",
                "products": ["prod_1", "prod_2"]
            },
            screen="confirmation",
            action="submit"
        )

        assert flow_data.flow_token == "test_token_123"
        assert flow_data.version == "1.0"
        assert flow_data.data["customer_name"] == "John Doe"
        assert flow_data.screen == "confirmation"
        assert flow_data.action == "submit"

    def test_flow_configuration_model(self):
        """Test flow configuration model"""
        config = FlowConfiguration(
            flow_id="flow_123",
            flow_name="Order Form",
            phone_number_id="103397245943977",
            access_token="test_token"
        )

        assert config.flow_id == "flow_123"
        assert config.flow_name == "Order Form"
        assert config.flow_version == "1.0"  # Default value

        # Test URL generation
        expected_url = "https://graph.facebook.com/v23.0/flow_123"
        assert config.get_flow_url() == expected_url


class TestInMemoryFlowRepository:
    """Tests for in-memory flow repository"""

    @pytest.fixture
    def repository(self):
        return InMemoryFlowRepository()

    async def test_save_and_get_flow_session(self, repository):
        """Test saving and retrieving flow sessions"""
        session_data = {
            "user_context": {"preference": "gaming"},
            "flow_type": FlowType.ORDER_FORM,
            "started_at": datetime.utcnow().isoformat()
        }

        # Save session
        success = await repository.save_flow_session(
            user_phone="5491123456789",
            flow_id="flow_123",
            flow_token="token_123",
            session_data=session_data
        )
        assert success is True

        # Retrieve session
        retrieved = await repository.get_flow_session(
            user_phone="5491123456789",
            flow_token="token_123"
        )
        assert retrieved is not None
        assert retrieved["flow_type"] == FlowType.ORDER_FORM
        assert retrieved["flow_id"] == "flow_123"
        assert retrieved["user_phone"] == "5491123456789"

    async def test_update_flow_session(self, repository):
        """Test updating flow sessions"""
        # First save a session
        await repository.save_flow_session(
            user_phone="5491123456789",
            flow_id="flow_123",
            flow_token="token_123",
            session_data={"status": "started"}
        )

        # Update session
        success = await repository.update_flow_session(
            user_phone="5491123456789",
            flow_token="token_123",
            update_data={"status": "in_progress", "step": 2}
        )
        assert success is True

        # Verify update
        retrieved = await repository.get_flow_session(
            user_phone="5491123456789",
            flow_token="token_123"
        )
        assert retrieved["status"] == "in_progress"
        assert retrieved["step"] == 2

    async def test_complete_flow_session(self, repository):
        """Test completing flow sessions"""
        # First save a session
        await repository.save_flow_session(
            user_phone="5491123456789",
            flow_id="flow_123",
            flow_token="token_123",
            session_data={"status": "started"}
        )

        # Complete session
        success = await repository.complete_flow_session(
            user_phone="5491123456789",
            flow_token="token_123",
            completion_data={"status": "completed", "result": "success"}
        )
        assert success is True

        # Verify completion
        retrieved = await repository.get_flow_session(
            user_phone="5491123456789",
            flow_token="token_123"
        )
        assert retrieved["status"] == "completed"
        assert retrieved["result"] == "success"
        assert "completed_at" in retrieved


class TestDefaultOrderFormHandler:
    """Tests for default order form handler"""

    @pytest.fixture
    def handler(self):
        return DefaultOrderFormHandler()

    async def test_validate_flow_completion_valid(self, handler):
        """Test validation of valid order form"""
        flow_data = FlowDataResponse(
            flow_token="test_token",
            version="1.0",
            data={
                "products": [{"id": "prod_1", "quantity": 2}],
                "customer_name": "John Doe",
                "delivery_address": "123 Main St, City"
            }
        )

        is_valid, errors = await handler.validate_flow_completion("flow_123", flow_data)

        assert is_valid is True
        assert len(errors) == 0

    async def test_validate_flow_completion_invalid(self, handler):
        """Test validation of invalid order form"""
        flow_data = FlowDataResponse(
            flow_token="test_token",
            version="1.0",
            data={
                "customer_name": "John Doe"
                # Missing products and delivery_address
            }
        )

        is_valid, errors = await handler.validate_flow_completion("flow_123", flow_data)

        assert is_valid is False
        assert len(errors) > 0
        assert any("products" in error for error in errors)
        assert any("delivery_address" in error for error in errors)

    async def test_process_flow_data_valid(self, handler):
        """Test processing valid order form data"""
        flow_data = FlowDataResponse(
            flow_token="test_token",
            version="1.0",
            data={
                "products": [{"id": "prod_1", "quantity": 2}],
                "customer_name": "John Doe",
                "delivery_address": "123 Main St, City"
            }
        )

        result = await handler.process_flow_data("flow_123", "5491123456789", flow_data)

        assert result["success"] is True
        assert result["action"] == "order_processed"
        assert "order_id" in result
        assert result["order_id"].startswith("ORD_")

    async def test_process_flow_data_invalid(self, handler):
        """Test processing invalid order form data"""
        flow_data = FlowDataResponse(
            flow_token="test_token",
            version="1.0",
            data={
                "customer_name": "John Doe"
                # Missing required fields
            }
        )

        result = await handler.process_flow_data("flow_123", "5491123456789", flow_data)

        assert result["success"] is False
        assert result["action"] == "validation_failed"
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestWhatsAppFlowsService:
    """Tests for WhatsApp Flows service"""

    @pytest.fixture
    def mock_whatsapp_service(self):
        """Mock WhatsApp service"""
        mock = MagicMock()
        mock.send_flow_message = AsyncMock()
        return mock

    @pytest.fixture
    def mock_repository(self):
        """Mock flow repository"""
        return InMemoryFlowRepository()

    @pytest.fixture
    def flows_service(self, mock_whatsapp_service, mock_repository):
        """Create flows service with mocked dependencies"""
        return WhatsAppFlowsService(
            whatsapp_service=mock_whatsapp_service,
            flow_repository=mock_repository
        )

    def test_flow_token_generation(self, flows_service):
        """Test flow token generation"""
        token = flows_service._generate_flow_token("5491123456789", FlowType.ORDER_FORM)

        assert token.startswith(FlowType.ORDER_FORM)
        assert "6789" in token  # Last 4 digits of phone
        assert "_" in token

    def test_default_body_generation(self, flows_service):
        """Test default body text generation"""
        flow_config = {
            "name": "Formulario de Pedido",
            "timeout_minutes": 30
        }

        body = flows_service._generate_default_body(FlowType.ORDER_FORM, flow_config)

        assert "Formulario de Pedido" in body
        assert "30 minutos" in body
        assert "completar" in body.lower()

    async def test_send_flow_success(self, flows_service):
        """Test successful flow sending"""
        # Mock successful response
        flows_service.whatsapp_service.send_flow_message.return_value = WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_123"}
        )

        response = await flows_service.send_flow(
            user_phone="5491123456789",
            flow_type=FlowType.ORDER_FORM,
            flow_id="flow_123",
            context_data={"product_id": "prod_123"}
        )

        assert response.success is True
        flows_service.whatsapp_service.send_flow_message.assert_called_once()

        # Check repository was called to save session
        sessions = flows_service.flow_repository._sessions
        assert len(sessions) == 1

    async def test_send_flow_validation_error(self, flows_service):
        """Test flow sending with validation errors"""
        response = await flows_service.send_flow(
            user_phone="",  # Empty phone
            flow_type=FlowType.ORDER_FORM,
            flow_id="flow_123"
        )

        assert response.success is False
        assert "requeridos" in response.error

    async def test_send_flow_unknown_type(self, flows_service):
        """Test flow sending with unknown flow type"""
        response = await flows_service.send_flow(
            user_phone="5491123456789",
            flow_type="unknown_flow_type",
            flow_id="flow_123"
        )

        assert response.success is False
        assert "Unknown flow type" in response.error

    async def test_process_flow_response_success(self, flows_service):
        """Test processing flow response successfully"""
        # First create a session
        flow_token = flows_service._generate_flow_token("5491123456789", FlowType.ORDER_FORM)
        await flows_service.flow_repository.save_flow_session(
            user_phone="5491123456789",
            flow_id="flow_123",
            flow_token=flow_token,
            session_data={
                "flow_type": FlowType.ORDER_FORM,
                "started_at": datetime.utcnow().isoformat()
            }
        )

        # Create flow response
        flow_response = FlowDataResponse(
            flow_token=flow_token,
            version="1.0",
            data={
                "products": [{"id": "prod_1", "quantity": 1}],
                "customer_info": {"name": "John Doe", "email": "john@test.com"},
                "delivery_address": {"street": "123 Main St", "city": "City"}
            }
        )

        result = await flows_service.process_flow_response(
            user_phone="5491123456789",
            flow_response=flow_response
        )

        assert result["success"] is True
        assert result["action"] == "order_created"
        assert "order_data" in result

    async def test_process_flow_response_no_session(self, flows_service):
        """Test processing flow response with no session"""
        flow_response = FlowDataResponse(
            flow_token="nonexistent_token",
            version="1.0",
            data={"test": "data"}
        )

        result = await flows_service.process_flow_response(
            user_phone="5491123456789",
            flow_response=flow_response
        )

        assert result["success"] is False
        assert result["error"] == "Session not found or expired"
        assert result["action"] == "restart_flow"

    def test_get_available_flows(self, flows_service):
        """Test getting available flows"""
        flows = flows_service.get_available_flows()

        assert FlowType.ORDER_FORM in flows
        assert FlowType.CUSTOMER_SURVEY in flows
        assert FlowType.PRODUCT_INQUIRY in flows
        assert FlowType.SUPPORT_TICKET in flows
        assert FlowType.FEEDBACK_FORM in flows

        # Check flow configurations
        order_form = flows[FlowType.ORDER_FORM]
        assert "name" in order_form
        assert "cta" in order_form
        assert "timeout_minutes" in order_form

    async def test_process_order_form(self, flows_service):
        """Test processing order form specifically"""
        response_data = {
            "products": [
                {"id": "prod_1", "name": "Laptop", "quantity": 1, "price": 1500}
            ],
            "customer_info": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "5491123456789"
            },
            "delivery_address": {
                "street": "123 Main St",
                "city": "Buenos Aires",
                "postal_code": "1000"
            }
        }

        session_data = {
            "flow_type": FlowType.ORDER_FORM,
            "started_at": datetime.utcnow().isoformat()
        }

        result = await flows_service._process_order_form(
            user_phone="5491123456789",
            response_data=response_data,
            session_data=session_data
        )

        assert result["success"] is True
        assert result["action"] == "order_created"
        assert result["order_data"]["user_phone"] == "5491123456789"
        assert result["order_data"]["products"] == response_data["products"]
        assert result["order_data"]["status"] == "pending_confirmation"
        assert "next_steps" in result

    async def test_process_customer_survey(self, flows_service):
        """Test processing customer survey"""
        response_data = {
            "satisfaction_rating": 4,
            "feedback": "Great service!",
            "would_recommend": True,
            "suggestions": ["Faster delivery", "More product variety"]
        }

        session_data = {
            "flow_type": FlowType.CUSTOMER_SURVEY,
            "session_id": "survey_123"
        }

        result = await flows_service._process_customer_survey(
            user_phone="5491123456789",
            response_data=response_data,
            session_data=session_data
        )

        assert result["success"] is True
        assert result["action"] == "survey_completed"
        assert result["survey_data"]["user_phone"] == "5491123456789"
        assert result["survey_data"]["responses"] == response_data
        assert "Gracias por tu feedback" in result["message"]

    async def test_process_support_ticket(self, flows_service):
        """Test processing support ticket"""
        response_data = {
            "category": "technical_issue",
            "priority": "high",
            "description": "Unable to login to my account",
            "attachments": ["screenshot.png"]
        }

        session_data = {
            "flow_type": FlowType.SUPPORT_TICKET
        }

        result = await flows_service._process_support_ticket(
            user_phone="5491123456789",
            response_data=response_data,
            session_data=session_data
        )

        assert result["success"] is True
        assert result["action"] == "ticket_created"
        assert result["ticket_data"]["user_phone"] == "5491123456789"
        assert result["ticket_data"]["category"] == "technical_issue"
        assert result["ticket_data"]["priority"] == "high"
        assert result["ticket_data"]["status"] == "open"
        assert result["ticket_id"].startswith("TK_")
        assert "next_steps" in result

    async def test_cancel_flow_session(self, flows_service):
        """Test cancelling flow session"""
        # Create a session first
        flow_token = flows_service._generate_flow_token("5491123456789", FlowType.ORDER_FORM)
        await flows_service.flow_repository.save_flow_session(
            user_phone="5491123456789",
            flow_id="flow_123",
            flow_token=flow_token,
            session_data={"status": "active"}
        )

        # Cancel the session
        success = await flows_service.cancel_flow_session(
            user_phone="5491123456789",
            flow_token=flow_token
        )

        assert success is True

        # Verify cancellation
        session = await flows_service.flow_repository.get_flow_session(
            user_phone="5491123456789",
            flow_token=flow_token
        )
        assert session["status"] == "cancelled"


class TestFlowIntegration:
    """Integration tests for flow functionality"""

    @patch('app.services.whatsapp_flows_service.WhatsAppService')
    async def test_end_to_end_flow_process(self, mock_whatsapp_service_class):
        """Test complete flow from sending to processing response"""
        # Setup mocks
        mock_service = MagicMock()
        mock_service.send_flow_message.return_value = WhatsAppApiResponse(
            success=True,
            data={"message_id": "msg_123"}
        )
        mock_whatsapp_service_class.return_value = mock_service

        # Create services
        repository = InMemoryFlowRepository()
        flows_service = WhatsAppFlowsService(
            whatsapp_service=mock_service,
            flow_repository=repository
        )

        # 1. Send flow
        send_response = await flows_service.send_flow(
            user_phone="5491123456789",
            flow_type=FlowType.ORDER_FORM,
            flow_id="flow_123",
            context_data={"product_id": "prod_123"}
        )

        assert send_response.success is True
        mock_service.send_flow_message.assert_called_once()

        # 2. Get flow token from repository (simulate flow completion)
        sessions = repository._sessions
        assert len(sessions) == 1

        session_key = list(sessions.keys())[0]
        session_data = sessions[session_key]
        flow_token = session_data["flow_token"]

        # 3. Process flow response
        flow_response = FlowDataResponse(
            flow_token=flow_token,
            version="1.0",
            data={
                "products": [{"id": "prod_123", "quantity": 2}],
                "customer_info": {"name": "Jane Doe", "email": "jane@test.com"},
                "delivery_address": {"street": "456 Oak St", "city": "Test City"}
            }
        )

        process_response = await flows_service.process_flow_response(
            user_phone="5491123456789",
            flow_response=flow_response
        )

        assert process_response["success"] is True
        assert process_response["action"] == "order_created"
        assert "order_data" in process_response

    async def test_flow_timeout_handling(self):
        """Test flow timeout handling"""
        repository = InMemoryFlowRepository()
        flows_service = WhatsAppFlowsService(flow_repository=repository)

        # Create session with past timeout
        flow_token = flows_service._generate_flow_token("5491123456789", FlowType.ORDER_FORM)
        past_timeout = (datetime.utcnow() - timedelta(hours=1)).isoformat()

        await repository.save_flow_session(
            user_phone="5491123456789",
            flow_id="flow_123",
            flow_token=flow_token,
            session_data={
                "flow_type": FlowType.ORDER_FORM,
                "timeout_at": past_timeout
            }
        )

        # In a real implementation, there would be cleanup logic
        # For now, just verify the session exists
        session = await repository.get_flow_session("5491123456789", flow_token)
        assert session is not None

        # In production, you'd check if datetime.fromisoformat(session["timeout_at"]) < datetime.utcnow()
        # and handle accordingly


if __name__ == "__main__":
    pytest.main([__file__, "-v"])