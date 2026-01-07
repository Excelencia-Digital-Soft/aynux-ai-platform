"""
Process Webhook Use Case.

Orchestrates WhatsApp webhook message processing.
Single Responsibility: Coordinate domain detection, bypass routing, and message processing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings
from app.core.container import DependencyContainer
from app.models.message import BotResponse, Contact, WhatsAppMessage

if TYPE_CHECKING:
    from app.core.schemas.tenant_agent_config import TenantAgentRegistry
    from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)


@dataclass
class WebhookProcessingResult:
    """
    Result of webhook message processing.

    Attributes:
        status: Processing status ("ok" or "error")
        result: Bot response if successful
        domain: Domain used for processing
        mode: Processing mode ("global" or "multi_tenant")
        method: Processing method (None or "fallback")
        error_message: Error message if failed
        fallback_error: Fallback error message if fallback also failed
    """

    status: str
    result: BotResponse | None = None
    domain: str | None = None
    mode: str = "global"
    method: str | None = None
    error_message: str | None = None
    fallback_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        response: dict[str, Any] = {
            "status": self.status,
            "domain": self.domain,
            "mode": self.mode,
        }

        if self.result:
            response["result"] = self.result

        if self.method:
            response["method"] = self.method

        if self.error_message:
            response["message"] = self.error_message

        if self.fallback_error:
            response["fallback_error"] = self.fallback_error

        return response


@dataclass
class BypassResult:
    """Result of bypass routing evaluation."""

    organization_id: UUID | None = None
    domain: str | None = None
    target_agent: str | None = None
    pharmacy_id: UUID | None = None
    isolated_history: bool = False
    rule_id: UUID | None = None

    @property
    def matched(self) -> bool:
        """Check if bypass routing matched."""
        return self.organization_id is not None


class ProcessWebhookUseCase:
    """
    Use Case: Process incoming WhatsApp webhook message.

    Orchestrates:
    1. Bypass routing evaluation
    2. Contact domain detection
    3. Tenant registry loading
    4. Message processing via LangGraph
    5. Fallback handling

    This use case encapsulates all business logic previously in
    the process_webhook endpoint, following Clean Architecture.
    """

    DEFAULT_DOMAIN = "excelencia"

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        langgraph_service: "LangGraphChatbotService",
    ):
        """
        Initialize use case.

        Args:
            db: Async database session
            settings: Application settings
            langgraph_service: LangGraph processing service
        """
        self._db = db
        self._settings = settings
        self._service = langgraph_service
        self._container = DependencyContainer()

    async def execute(
        self,
        message: WhatsAppMessage,
        contact: Contact,
        whatsapp_phone_number_id: str | None = None,
        chattigo_context: dict | None = None,
    ) -> WebhookProcessingResult:
        """
        Execute webhook message processing.

        Args:
            message: WhatsApp message
            contact: WhatsApp contact
            whatsapp_phone_number_id: WhatsApp Business phone ID
            chattigo_context: Chattigo-specific context (did, idChat, channelId, idCampaign)
                            Used when message comes from Chattigo webhook.

        Returns:
            WebhookProcessingResult with status and response
        """
        # Store Chattigo context for use in message sending
        self._chattigo_context = chattigo_context
        wa_id = contact.wa_id
        logger.info(f"Processing message from WhatsApp ID: {wa_id}")

        # Step 1: Evaluate bypass routing and detect domain
        bypass_result = await self._evaluate_bypass_routing(wa_id, whatsapp_phone_number_id)

        if bypass_result.matched:
            domain = bypass_result.domain or self.DEFAULT_DOMAIN
            logger.info(
                f"[BYPASS] Using bypass routing: {wa_id} -> org={bypass_result.organization_id}, domain={domain}"
            )
        else:
            domain = await self._detect_contact_domain(wa_id)
            logger.info(f"Contact domain detected: {wa_id} -> {domain}")

        # Step 2: Load tenant registry if multi-tenant mode
        _, mode = await self._load_tenant_registry(bypass_result.organization_id, bypass_result.target_agent)

        # Step 3: Process message (pass organization_id, pharmacy_id, bypass_target_agent, and isolation params)
        try:
            result = await self._process_message(
                message,
                contact,
                domain,
                organization_id=bypass_result.organization_id,
                pharmacy_id=bypass_result.pharmacy_id,
                bypass_target_agent=bypass_result.target_agent,
                isolated_history=bypass_result.isolated_history,
                bypass_rule_id=bypass_result.rule_id,
            )

            logger.info(f"Message processed successfully: {result.status}")

            return WebhookProcessingResult(
                status="ok",
                result=result,
                domain=domain,
                mode=mode,
            )

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

            # Attempt fallback
            fallback_result = await self._attempt_fallback(message, contact, mode)

            if fallback_result:
                return fallback_result

            return WebhookProcessingResult(
                status="error",
                error_message=str(e),
                mode=mode,
            )

        finally:
            # Cleanup tenant config
            if mode == "multi_tenant":
                self._service.reset_tenant_config()

    async def _evaluate_bypass_routing(
        self,
        wa_id: str,
        whatsapp_phone_number_id: str | None,
    ) -> BypassResult:
        """
        Evaluate bypass routing rules.

        Args:
            wa_id: WhatsApp ID
            whatsapp_phone_number_id: WhatsApp Business phone ID

        Returns:
            BypassResult with matched org/domain/agent or empty result
        """
        if not self._settings.MULTI_TENANT_MODE:
            return BypassResult()

        from app.services.bypass_routing_service import BypassRoutingService

        bypass_service = BypassRoutingService(self._db)
        match = await bypass_service.evaluate_bypass_rules(wa_id, whatsapp_phone_number_id)

        if match:
            return BypassResult(
                organization_id=match.organization_id,
                domain=match.domain,
                target_agent=match.target_agent,
                pharmacy_id=match.pharmacy_id,
                isolated_history=match.isolated_history,
                rule_id=match.rule_id,
            )

        return BypassResult()

    async def _detect_contact_domain(self, wa_id: str) -> str:
        """
        Detect domain for contact using Use Case.

        Args:
            wa_id: WhatsApp ID

        Returns:
            Domain name (e.g., "ecommerce", "healthcare", "excelencia")
        """
        try:
            use_case = self._container.create_get_contact_domain_use_case(self._db)
            result = await use_case.execute(wa_id=wa_id)

            if result["status"] == "assigned":
                domain = result["domain_info"]["domain"]
                logger.info(f"Found existing domain assignment: {wa_id} -> {domain}")
                return domain

            logger.info(f"No domain assignment for {wa_id}, using default: {self.DEFAULT_DOMAIN}")
            return self.DEFAULT_DOMAIN

        except Exception as e:
            logger.error(f"Error detecting contact domain: {e}", exc_info=True)
            return self.DEFAULT_DOMAIN

    async def _load_tenant_registry(
        self,
        bypass_org_id: UUID | None,
        bypass_target_agent: str | None,
    ) -> tuple["TenantAgentRegistry | None", str]:
        """
        Load tenant registry and configure service.

        Args:
            bypass_org_id: Organization ID from bypass routing
            bypass_target_agent: Target agent from bypass routing

        Returns:
            Tuple of (TenantAgentRegistry or None, mode string)
        """
        if not self._settings.MULTI_TENANT_MODE:
            return None, "global"

        from app.core.tenancy.registry_loader import TenantRegistryLoader

        loader = TenantRegistryLoader(self._db)

        if bypass_org_id:
            registry = await loader.load_for_organization(bypass_org_id)
        else:
            registry = await loader.load_from_context()

        if registry:
            if bypass_target_agent:
                registry.bypass_target_agent = bypass_target_agent
            self._service.set_tenant_registry_for_request(registry)
            logger.info(f"Processing in multi-tenant mode for org: {registry.organization_id}")
            return registry, "multi_tenant"

        logger.info("No tenant context found, processing in global mode")
        return None, "global"

    async def _process_message(
        self,
        message: WhatsAppMessage,
        contact: Contact,
        domain: str,
        organization_id: UUID | None = None,
        pharmacy_id: UUID | None = None,
        bypass_target_agent: str | None = None,
        isolated_history: bool = False,
        bypass_rule_id: UUID | None = None,
    ) -> BotResponse:
        """
        Process message via LangGraph service.

        Args:
            message: WhatsApp message
            contact: WhatsApp contact
            domain: Business domain
            organization_id: Organization UUID (from bypass routing)
            pharmacy_id: Pharmacy UUID (from bypass routing, for config lookup)
            bypass_target_agent: Target agent from bypass routing (for direct routing)
            isolated_history: When true, creates isolated conversation history
            bypass_rule_id: UUID of the bypass rule (for generating isolated history suffix)

        Returns:
            BotResponse from LangGraph
        """
        return await self._service.process_webhook_message(
            message=message,
            contact=contact,
            business_domain=domain,
            db_session=self._db,
            organization_id=organization_id,
            pharmacy_id=pharmacy_id,
            chattigo_context=self._chattigo_context,
            bypass_target_agent=bypass_target_agent,
            isolated_history=isolated_history,
            bypass_rule_id=bypass_rule_id,
        )

    async def _attempt_fallback(
        self,
        message: WhatsAppMessage,
        contact: Contact,
        mode: str,
    ) -> WebhookProcessingResult | None:
        """
        Attempt fallback to default domain.

        Args:
            message: WhatsApp message
            contact: WhatsApp contact
            mode: Current processing mode

        Returns:
            WebhookProcessingResult if fallback successful, None otherwise
        """
        try:
            logger.info(f"Attempting fallback to default domain ({self.DEFAULT_DOMAIN})")
            result = await self._process_message(message, contact, self.DEFAULT_DOMAIN)

            return WebhookProcessingResult(
                status="ok",
                result=result,
                domain=self.DEFAULT_DOMAIN,
                mode=mode,
                method="fallback",
            )

        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {fallback_error}", exc_info=True)
            return None
