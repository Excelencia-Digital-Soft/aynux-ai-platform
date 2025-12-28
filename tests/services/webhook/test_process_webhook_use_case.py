"""
Tests for Process Webhook Use Case.

Tests the orchestration of WhatsApp webhook message processing.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.domains.shared.application.use_cases.process_webhook_use_case import (
    BypassResult,
    ProcessWebhookUseCase,
    WebhookProcessingResult,
)
from app.models.message import BotResponse, Contact, WhatsAppMessage


class TestWebhookProcessingResult:
    """Tests for WebhookProcessingResult dataclass."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        bot_response = BotResponse(status="success", message="Hello")
        result = WebhookProcessingResult(
            status="ok",
            result=bot_response,
            domain="excelencia",
            mode="global",
        )

        assert result.status == "ok"
        assert result.result == bot_response
        assert result.domain == "excelencia"
        assert result.mode == "global"
        assert result.method is None
        assert result.error_message is None

    def test_create_error_result(self):
        """Test creating an error result."""
        result = WebhookProcessingResult(
            status="error",
            error_message="Something went wrong",
            mode="multi_tenant",
        )

        assert result.status == "error"
        assert result.result is None
        assert result.error_message == "Something went wrong"

    def test_to_dict_success(self):
        """Test converting successful result to dict."""
        bot_response = BotResponse(status="success", message="Hello")
        result = WebhookProcessingResult(
            status="ok",
            result=bot_response,
            domain="excelencia",
            mode="global",
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "ok"
        assert result_dict["domain"] == "excelencia"
        assert result_dict["mode"] == "global"
        assert result_dict["result"] == bot_response
        assert "method" not in result_dict
        assert "message" not in result_dict

    def test_to_dict_with_fallback(self):
        """Test converting fallback result to dict."""
        bot_response = BotResponse(status="success", message="Hello")
        result = WebhookProcessingResult(
            status="ok",
            result=bot_response,
            domain="ecommerce",
            mode="global",
            method="fallback",
        )

        result_dict = result.to_dict()

        assert result_dict["method"] == "fallback"

    def test_to_dict_error(self):
        """Test converting error result to dict."""
        result = WebhookProcessingResult(
            status="error",
            error_message="Processing failed",
            fallback_error="Fallback also failed",
            mode="global",
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "error"
        assert result_dict["message"] == "Processing failed"
        assert result_dict["fallback_error"] == "Fallback also failed"


class TestBypassResult:
    """Tests for BypassResult dataclass."""

    def test_matched_when_org_id_present(self):
        """Test that matched is True when organization_id is set."""
        result = BypassResult(
            organization_id=uuid.uuid4(),
            domain="pharmacy",
            target_agent="pharmacy_agent",
        )

        assert result.matched is True

    def test_not_matched_when_org_id_none(self):
        """Test that matched is False when organization_id is None."""
        result = BypassResult()

        assert result.matched is False


class TestProcessWebhookUseCase:
    """Tests for ProcessWebhookUseCase."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.MULTI_TENANT_MODE = False
        return settings

    @pytest.fixture
    def mock_langgraph_service(self):
        """Create mock LangGraph service."""
        service = MagicMock()
        service.process_webhook_message = AsyncMock(
            return_value=BotResponse(status="success", message="Response")
        )
        service.set_tenant_registry_for_request = MagicMock()
        service.reset_tenant_config = MagicMock()
        return service

    @pytest.fixture
    def mock_message(self):
        """Create mock WhatsApp message."""
        return MagicMock(spec=WhatsAppMessage)

    @pytest.fixture
    def mock_contact(self):
        """Create mock WhatsApp contact."""
        contact = MagicMock(spec=Contact)
        contact.wa_id = "5491155001234"
        return contact

    @pytest.fixture
    def use_case(self, mock_db, mock_settings, mock_langgraph_service):
        """Create use case with mocked dependencies."""
        return ProcessWebhookUseCase(
            db=mock_db,
            settings=mock_settings,
            langgraph_service=mock_langgraph_service,
        )

    @pytest.mark.asyncio
    async def test_execute_global_mode_success(
        self, use_case, mock_message, mock_contact, mock_langgraph_service
    ):
        """Test successful execution in global mode."""
        # Mock domain detection
        mock_domain_uc = MagicMock()
        mock_domain_uc.execute = AsyncMock(
            return_value={"status": "assigned", "domain_info": {"domain": "excelencia"}}
        )

        with patch.object(
            use_case._container,
            "create_get_contact_domain_use_case",
            return_value=mock_domain_uc,
        ):
            result = await use_case.execute(mock_message, mock_contact)

        assert result.status == "ok"
        assert result.domain == "excelencia"
        assert result.mode == "global"
        mock_langgraph_service.process_webhook_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_uses_default_domain_when_not_assigned(
        self, use_case, mock_message, mock_contact
    ):
        """Test that default domain is used when contact has no assignment."""
        mock_domain_uc = MagicMock()
        mock_domain_uc.execute = AsyncMock(return_value={"status": "not_assigned"})

        with patch.object(
            use_case._container,
            "create_get_contact_domain_use_case",
            return_value=mock_domain_uc,
        ):
            result = await use_case.execute(mock_message, mock_contact)

        assert result.domain == "excelencia"  # DEFAULT_DOMAIN

    @pytest.mark.asyncio
    async def test_execute_multi_tenant_mode_with_bypass(
        self, mock_db, mock_langgraph_service, mock_message, mock_contact
    ):
        """Test execution in multi-tenant mode with bypass routing."""
        settings = MagicMock(spec=Settings)
        settings.MULTI_TENANT_MODE = True

        use_case = ProcessWebhookUseCase(
            db=mock_db,
            settings=settings,
            langgraph_service=mock_langgraph_service,
        )

        org_id = uuid.uuid4()
        mock_bypass_match = MagicMock()
        mock_bypass_match.organization_id = org_id
        mock_bypass_match.domain = "pharmacy"
        mock_bypass_match.target_agent = "pharmacy_agent"

        mock_registry = MagicMock()
        mock_registry.organization_id = org_id

        with patch(
            "app.services.bypass_routing_service.BypassRoutingService"
        ) as MockBypassService:
            mock_service = MagicMock()
            mock_service.evaluate_bypass_rules = AsyncMock(return_value=mock_bypass_match)
            MockBypassService.return_value = mock_service

            with patch(
                "app.core.tenancy.registry_loader.TenantRegistryLoader"
            ) as MockLoader:
                mock_loader = MagicMock()
                mock_loader.load_for_organization = AsyncMock(return_value=mock_registry)
                MockLoader.return_value = mock_loader

                result = await use_case.execute(
                    mock_message, mock_contact, "123456789"
                )

        assert result.status == "ok"
        assert result.domain == "pharmacy"
        assert result.mode == "multi_tenant"
        mock_langgraph_service.set_tenant_registry_for_request.assert_called_once_with(
            mock_registry
        )

    @pytest.mark.asyncio
    async def test_execute_handles_processing_error_with_fallback(
        self, use_case, mock_message, mock_contact, mock_langgraph_service
    ):
        """Test that processing errors trigger fallback."""
        # First call fails, second (fallback) succeeds
        mock_langgraph_service.process_webhook_message = AsyncMock(
            side_effect=[
                Exception("Processing error"),
                BotResponse(status="success", message="Fallback response"),
            ]
        )

        mock_domain_uc = MagicMock()
        mock_domain_uc.execute = AsyncMock(
            return_value={"status": "assigned", "domain_info": {"domain": "excelencia"}}
        )

        with patch.object(
            use_case._container,
            "create_get_contact_domain_use_case",
            return_value=mock_domain_uc,
        ):
            result = await use_case.execute(mock_message, mock_contact)

        assert result.status == "ok"
        assert result.method == "fallback"
        assert result.domain == "excelencia"  # DEFAULT_DOMAIN for fallback
        assert mock_langgraph_service.process_webhook_message.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_returns_error_when_fallback_fails(
        self, use_case, mock_message, mock_contact, mock_langgraph_service
    ):
        """Test that error is returned when both processing and fallback fail."""
        mock_langgraph_service.process_webhook_message = AsyncMock(
            side_effect=Exception("Processing error")
        )

        mock_domain_uc = MagicMock()
        mock_domain_uc.execute = AsyncMock(
            return_value={"status": "assigned", "domain_info": {"domain": "excelencia"}}
        )

        with patch.object(
            use_case._container,
            "create_get_contact_domain_use_case",
            return_value=mock_domain_uc,
        ):
            result = await use_case.execute(mock_message, mock_contact)

        assert result.status == "error"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_execute_resets_tenant_config_in_multi_tenant_mode(
        self, mock_db, mock_langgraph_service, mock_message, mock_contact
    ):
        """Test that tenant config is reset after processing in multi-tenant mode."""
        settings = MagicMock(spec=Settings)
        settings.MULTI_TENANT_MODE = True

        use_case = ProcessWebhookUseCase(
            db=mock_db,
            settings=settings,
            langgraph_service=mock_langgraph_service,
        )

        mock_registry = MagicMock()
        mock_registry.organization_id = uuid.uuid4()

        with patch(
            "app.services.bypass_routing_service.BypassRoutingService"
        ) as MockBypassService:
            mock_service = MagicMock()
            mock_service.evaluate_bypass_rules = AsyncMock(return_value=None)
            MockBypassService.return_value = mock_service

            with patch(
                "app.core.tenancy.registry_loader.TenantRegistryLoader"
            ) as MockLoader:
                mock_loader = MagicMock()
                mock_loader.load_from_context = AsyncMock(return_value=mock_registry)
                MockLoader.return_value = mock_loader

                mock_domain_uc = MagicMock()
                mock_domain_uc.execute = AsyncMock(
                    return_value={"status": "assigned", "domain_info": {"domain": "excelencia"}}
                )

                with patch.object(
                    use_case._container,
                    "create_get_contact_domain_use_case",
                    return_value=mock_domain_uc,
                ):
                    await use_case.execute(mock_message, mock_contact)

        mock_langgraph_service.reset_tenant_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_handles_domain_detection_error(
        self, use_case, mock_message, mock_contact
    ):
        """Test that domain detection errors fall back to default domain."""
        mock_domain_uc = MagicMock()
        mock_domain_uc.execute = AsyncMock(side_effect=Exception("Domain detection failed"))

        with patch.object(
            use_case._container,
            "create_get_contact_domain_use_case",
            return_value=mock_domain_uc,
        ):
            result = await use_case.execute(mock_message, mock_contact)

        # Should still succeed with default domain
        assert result.status == "ok"
        assert result.domain == "excelencia"  # DEFAULT_DOMAIN
