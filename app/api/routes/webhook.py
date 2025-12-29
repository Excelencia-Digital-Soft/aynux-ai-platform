# ============================================================================
# SCOPE: GLOBAL (Chattigo mode)
# Description: Webhook endpoint for Chattigo WhatsApp integration.
#              Chattigo handles Meta verification, we only receive messages.
# ============================================================================
"""
WhatsApp Webhook Endpoints (via Chattigo).

Chattigo is a WhatsApp Business API intermediary that:
- Handles Meta webhook verification
- Forwards messages to this application
- Provides API for sending messages

ENDPOINTS:
  - POST /webhook → Message processing from Chattigo
  - GET /webhook/health → LangGraph health check
  - GET /webhook/conversation/{user_number} → Conversation history
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases.process_webhook_use_case import (
    ProcessWebhookUseCase,
)
from app.integrations.chattigo import ChattigoWebhookPayload
from app.models.message import ChattigoToWhatsAppAdapter
from app.services.langgraph_chatbot_service import LangGraphChatbotService

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# LangGraph Service (initialized lazily)
_langgraph_service: LangGraphChatbotService | None = None


async def _get_langgraph_service() -> LangGraphChatbotService:
    """Get or create LangGraph service singleton."""
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
# CHATTIGO WEBHOOK ENDPOINT
# ============================================================


@router.post("/webhook/")
@router.post("/webhook")
async def process_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Process incoming messages from Chattigo.

    Chattigo forwards WhatsApp messages to this endpoint.
    No verification needed - Chattigo handles that with Meta.

    Args:
        request: FastAPI request object
        db_session: Database session
        settings: Application settings

    Returns:
        Processing result
    """
    # Validate Chattigo is enabled
    if not settings.CHATTIGO_ENABLED:
        logger.warning("Chattigo webhook called but CHATTIGO_ENABLED=false")
        raise HTTPException(
            status_code=503,
            detail="Chattigo integration is disabled.",
        )

    # 1. Capture raw body BEFORE Pydantic parsing for debugging
    import json

    raw_body = await request.body()
    logger.info(f"Raw webhook body: {raw_body.decode('utf-8')}")

    # 2. Parse to dict for analysis
    try:
        raw_json = json.loads(raw_body)
        logger.info(f"Parsed JSON keys: {list(raw_json.keys())}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        return {"status": "error", "message": "Invalid JSON"}

    # 3. Create Pydantic model
    payload = ChattigoWebhookPayload(**raw_json)

    logger.info(
        f"Received webhook: msisdn={payload.msisdn}, "
        f"type={payload.type}, content={payload.content[:50] if payload.content else 'empty'}..."
    )

    # Skip status updates (no content)
    if not payload.content and not payload.is_attachment():
        logger.info("Received status update, ignoring")
        return {"status": "ok", "type": "status_update"}

    # Skip OUTBOUND (message sent by bot, not user)
    if payload.chatType == "OUTBOUND":
        logger.debug("Ignoring OUTBOUND message (sent by bot)")
        return {"status": "ok", "type": "outbound_ignored"}

    # Validate required fields
    if not payload.msisdn:
        logger.warning("Missing msisdn in payload")
        return {"status": "error", "message": "Missing msisdn"}

    # Store Chattigo context
    chattigo_context = {
        "did": payload.did,
        "idChat": payload.idChat,
        "channelId": payload.channelId,
        "idCampaign": payload.idCampaign,
    }

    # Convert to internal models
    message = ChattigoToWhatsAppAdapter.to_whatsapp_message(
        msisdn=payload.msisdn,
        content=payload.content or "",
        message_id=payload.id or str(int(time.time() * 1000)),
        timestamp=str(int(time.time())),
        message_type=payload.type or "Text",
    )

    contact = ChattigoToWhatsAppAdapter.to_contact(
        msisdn=payload.msisdn,
        name=payload.name,
    )

    # Process via Use Case
    try:
        service = await _get_langgraph_service()
        use_case = ProcessWebhookUseCase(
            db=db_session,
            settings=settings,
            langgraph_service=service,
        )

        result = await use_case.execute(
            message=message,
            contact=contact,
            whatsapp_phone_number_id=payload.did,
            chattigo_context=chattigo_context,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


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
