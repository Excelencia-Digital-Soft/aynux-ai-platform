# ============================================================================
# SCOPE: MIXED (Dual-mode: Global + Multi-tenant)
# Description: Webhook de WhatsApp con soporte dual-mode automático.
#              Sin token = modo global. Con token = carga config de DB por tenant.
# Tenant-Aware: Yes - detecta TenantContext y carga TenantAgentRegistry si existe.
# ============================================================================
"""
WhatsApp Webhook Endpoints.

Clean Architecture - Thin API layer delegating to Use Cases and Services.

DUAL-MODE SUPPORT:
  - Global mode (no token): Uses Python default agent configurations
  - Multi-tenant mode (with token): Loads agent config from database per-request

ENDPOINTS:
  - GET /webhook → WhatsApp webhook verification
  - POST /webhook → Message processing using Clean Architecture
  - GET /webhook/health → LangGraph health check
  - GET /webhook/conversation/{user_number} → Conversation history
"""

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.core.tenancy.credential_service import CredentialNotFoundError
from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases.process_webhook_use_case import (
    ProcessWebhookUseCase,
)
from app.models.message import WhatsAppWebhookRequest
from app.models.parsers.whatsapp_webhook_parser import (
    extract_phone_number_id,
    is_status_update,
)
from app.services.langgraph_chatbot_service import LangGraphChatbotService
from app.services.organization_resolver_service import (
    OrganizationResolutionError,
    OrganizationResolverService,
)

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# LangGraph Service (initialized lazily)
_langgraph_service: Optional[LangGraphChatbotService] = None


async def _get_langgraph_service() -> LangGraphChatbotService:
    """
    Get or create LangGraph service singleton.

    Returns:
        LangGraphChatbotService instance
    """
    global _langgraph_service

    if _langgraph_service is None:
        _langgraph_service = LangGraphChatbotService()
        try:
            await _langgraph_service.initialize()
            logger.info("LangGraph service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph service: {e}")
            raise
    return _langgraph_service


# ============================================================
# WEBHOOK VERIFICATION ENDPOINT
# ============================================================


@router.get("/webhook/")
@router.get("/webhook")
async def verify_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Verify webhook for WhatsApp.

    Called by WhatsApp to verify webhook configuration.

    CREDENTIAL RESOLUTION:
    1. If org_id query param provided → load verify_token from DB for that org
    2. If no org_id → load from default organization (slug='excelencia' or 'system')
    3. Compare provided token with stored token

    The webhook URL should include org_id for multi-tenant deployments:
    https://yourdomain.com/webhook?org_id=<organization-uuid>
    """
    query_params = dict(request.query_params)

    # WhatsApp verification parameters
    mode = query_params.get("hub.mode")
    token = query_params.get("hub.verify_token")
    challenge = query_params.get("hub.challenge")

    if not mode or not token:
        logger.warning("MISSING_PARAMETER")
        raise HTTPException(status_code=400, detail="Missing required parameters")

    if mode != "subscribe":
        logger.warning(f"INVALID_MODE: {mode}")
        raise HTTPException(status_code=400, detail="Invalid mode")

    # Resolve organization using service
    resolver = OrganizationResolverService(db)

    try:
        org_id = await resolver.resolve_organization(
            query_params=query_params,
            headers=dict(request.headers),
        )
    except OrganizationResolutionError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    # Get expected verify token
    try:
        expected_token = await resolver.get_verify_token(org_id)
    except CredentialNotFoundError as e:
        logger.error(f"Credentials not found for org {org_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"WhatsApp credentials not configured for organization {org_id}. "
            "Use the Admin API to configure credentials.",
        ) from e
    except ValueError as e:
        logger.error(f"Incomplete credentials for org {org_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Incomplete WhatsApp credentials for organization {org_id}: {e}",
        ) from e

    # Verify token
    if token == expected_token:
        logger.info(f"WEBHOOK_VERIFIED for org {org_id}")
        return PlainTextResponse(content=challenge)
    else:
        logger.warning(f"VERIFICATION_FAILED for org {org_id}")
        raise HTTPException(
            status_code=403, detail="Verification failed: token mismatch"
        )


# ============================================================
# MESSAGE PROCESSING ENDPOINT
# ============================================================


@router.post("/webhook/")
@router.post("/webhook")
async def process_webhook(
    request: WhatsAppWebhookRequest = Body(...),  # noqa: B008
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Process WhatsApp webhook messages.

    DUAL-MODE SUPPORT:
    - Global mode: No tenant context → uses Python default configs
    - Multi-tenant mode: Has tenant context → loads agent config from database

    Uses Clean Architecture with ProcessWebhookUseCase.
    """
    # Check for status updates
    if is_status_update(request):
        logger.info("Received a WhatsApp status update")
        return {"status": "ok", "type": "status_update"}

    # Extract message and contact
    message = request.get_message()
    contact = request.get_contact()

    if not message or not contact:
        logger.warning("Invalid webhook payload: missing message or contact")
        return {"status": "error", "message": "Invalid webhook payload"}

    # Extract phone number ID for bypass routing
    whatsapp_phone_number_id = extract_phone_number_id(request)

    # Process via Use Case
    service = await _get_langgraph_service()
    use_case = ProcessWebhookUseCase(
        db=db_session,
        settings=settings,
        langgraph_service=service,
    )

    result = await use_case.execute(
        message=message,
        contact=contact,
        whatsapp_phone_number_id=whatsapp_phone_number_id,
    )

    return result.to_dict()


# ============================================================
# HEALTH & MONITORING ENDPOINTS
# ============================================================


@router.get("/webhook/health")
async def health_check():
    """
    LangGraph system health check.

    Returns service status and health details.
    """
    try:
        service = await _get_langgraph_service()
        health_status = await service.get_system_health()
        overall_status = (
            health_status.get("overall_status", "unknown")
            if isinstance(health_status, dict)
            else ("healthy" if health_status else "unhealthy")
        )
        return {
            "service_type": "langgraph",
            "status": overall_status,
            "details": health_status,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {"service_type": "langgraph", "status": "unhealthy", "error": str(e)}


@router.get("/webhook/conversation/{user_number}")
async def get_conversation_history(user_number: str, limit: int = 50):
    """
    Get conversation history for a user.

    Args:
        user_number: WhatsApp ID of the user
        limit: Maximum number of messages to return

    Returns:
        Conversation history
    """
    try:
        service = await _get_langgraph_service()
        history = await service.get_conversation_history_langgraph(user_number, limit)
        return history
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return {"error": str(e)}
