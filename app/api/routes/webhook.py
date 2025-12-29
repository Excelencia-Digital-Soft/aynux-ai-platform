# ============================================================================
# SCOPE: GLOBAL (Chattigo mode)
# Description: Webhook endpoint for Chattigo WhatsApp integration.
#              Supports both WhatsApp standard format and Chattigo ISV format.
# ============================================================================
"""
WhatsApp Webhook Endpoints (via Chattigo).

Chattigo is a WhatsApp Business API intermediary that:
- Handles Meta webhook verification
- Forwards messages to this application (in WhatsApp standard format)
- Provides API for sending messages

ENDPOINTS:
  - POST /webhook → Message processing from Chattigo
  - GET /webhook/health → LangGraph health check
  - GET /webhook/conversation/{user_number} → Conversation history
"""

import json
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
from app.models.message import ChattigoToWhatsAppAdapter, WhatsAppWebhookRequest
from app.models.parsers.whatsapp_webhook_parser import (
    extract_phone_number_id,
    is_status_update,
)
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

    Supports two payload formats:
    1. WhatsApp Standard Format (object: "whatsapp_business_account")
    2. Chattigo ISV Format (msisdn, content, etc.)

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

    # 1. Parse raw body
    raw_body = await request.body()
    try:
        raw_json = json.loads(raw_body)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        return {"status": "error", "message": "Invalid JSON"}

    # 2. Detect payload format and process accordingly
    if raw_json.get("object") == "whatsapp_business_account":
        # WhatsApp Standard Format (from Meta via Chattigo)
        return await _process_whatsapp_format(raw_json, db_session, settings)
    else:
        # Chattigo ISV Format
        return await _process_chattigo_format(raw_json, db_session, settings)


async def _process_whatsapp_format(
    raw_json: dict,
    db_session: AsyncSession,
    settings: Settings,
) -> dict:
    """Process WhatsApp standard webhook format."""
    try:
        wa_request = WhatsAppWebhookRequest.model_validate(raw_json)
    except Exception as e:
        logger.error(f"Failed to parse WhatsApp format: {e}")
        return {"status": "error", "message": "Invalid WhatsApp format"}

    # Skip status updates (delivery receipts, read receipts, etc.)
    if is_status_update(wa_request):
        logger.debug("Ignoring WhatsApp status update")
        return {"status": "ok", "type": "status_update"}

    # Extract message and contact
    message = wa_request.get_message()
    contact = wa_request.get_contact()

    if not message:
        logger.debug("No message in WhatsApp webhook")
        return {"status": "ok", "type": "no_message"}

    if not contact:
        logger.warning("No contact in WhatsApp webhook")
        return {"status": "error", "message": "Missing contact"}

    # Extract phone number ID for routing
    phone_number_id = extract_phone_number_id(wa_request)

    logger.info(
        f"Received WhatsApp webhook: from={message.from_}, "
        f"type={message.type}, content={_get_message_preview(message)}"
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
            whatsapp_phone_number_id=phone_number_id,
            chattigo_context=None,  # No Chattigo context in standard format
        )

        return result.to_dict()

    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def _process_chattigo_format(
    raw_json: dict,
    db_session: AsyncSession,
    settings: Settings,
) -> dict:
    """Process Chattigo ISV webhook format."""
    payload = ChattigoWebhookPayload(**raw_json)

    logger.info(
        f"Received Chattigo webhook: msisdn={payload.msisdn}, "
        f"type={payload.type}, content={payload.content[:50] if payload.content else 'empty'}..."
    )

    # Skip status updates (no content)
    if not payload.content and not payload.is_attachment():
        logger.info("Received Chattigo status update, ignoring")
        return {"status": "ok", "type": "status_update"}

    # Skip OUTBOUND (message sent by bot, not user)
    if payload.chatType == "OUTBOUND":
        logger.debug("Ignoring OUTBOUND message (sent by bot)")
        return {"status": "ok", "type": "outbound_ignored"}

    # Validate required fields
    if not payload.msisdn:
        logger.warning("Missing msisdn in Chattigo payload")
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
        logger.error(f"Error processing Chattigo webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


def _get_message_preview(message) -> str:
    """Get a preview of message content for logging."""
    if message.text and message.text.body:
        body = message.text.body
        return f"{body[:50]}..." if len(body) > 50 else body
    return f"[{message.type}]"


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
