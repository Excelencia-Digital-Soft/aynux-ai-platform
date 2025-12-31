# ============================================================================
# SCOPE: GLOBAL (Chattigo mode)
# Description: Webhook endpoint for Chattigo WhatsApp integration.
#              Implements idempotency and fast response per Chattigo ISV docs.
# ============================================================================
"""
WhatsApp Webhook Endpoints (via Chattigo).

Chattigo ISV Integration Features:
- Idempotency: Redis SET NX prevents duplicate processing (Section 4.2)
- Fast Response: Returns 200 OK immediately, processes in background (Section 4.2)
- Multi-format: Supports WhatsApp standard and Chattigo ISV formats

ENDPOINTS:
  - POST /webhook → Message processing from Chattigo
  - GET /webhook/health → LangGraph health check
  - GET /webhook/conversation/{user_number} → Conversation history
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app.config.settings import Settings, get_settings
from app.database.async_db import get_async_db
from app.services.langgraph_chatbot_service import LangGraphChatbotService
from app.services.webhook import (
    IdempotencyService,
    ProcessingState,
    WebhookProcessor,
    WebhookTask,
)

router = APIRouter(tags=["webhook"])
logger = logging.getLogger(__name__)

# LangGraph Service (initialized lazily)
_langgraph_service: LangGraphChatbotService | None = None
# Idempotency Service (shared instance)
_idempotency_service: IdempotencyService | None = None


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


def _get_idempotency_service() -> IdempotencyService:
    """Get or create IdempotencyService singleton."""
    global _idempotency_service
    if _idempotency_service is None:
        _idempotency_service = IdempotencyService()
    return _idempotency_service


# ============================================================
# CHATTIGO WEBHOOK ENDPOINT
# ============================================================


@router.post("/webhook/")
@router.post("/webhook")
async def process_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Process incoming messages from Chattigo.

    Implements Chattigo ISV requirements:
    1. Idempotency check (Redis SET NX) - prevents duplicate processing
    2. Fast response (<50ms) - returns 200 OK immediately
    3. Background processing - heavy logic runs async

    Supports two payload formats:
    - WhatsApp Standard Format (object: "whatsapp_business_account")
    - Chattigo ISV Format (msisdn, content, etc.)

    Args:
        request: FastAPI request object
        background_tasks: FastAPI BackgroundTasks for async processing
        settings: Application settings

    Returns:
        Immediate response with message_id for tracking
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

    # 2. Extract message ID for idempotency
    message_id = _extract_message_id(raw_json)

    # 3. Idempotency check (atomic Redis operation)
    idempotency = _get_idempotency_service()
    if message_id:
        result = await idempotency.try_acquire_lock(message_id)

        if result.is_duplicate:
            if result.state == ProcessingState.COMPLETED:
                logger.debug(f"Duplicate message (completed): {message_id}")
                return {
                    "status": "ok",
                    "type": "duplicate",
                    "message_id": message_id,
                }
            elif result.state == ProcessingState.PROCESSING:
                logger.debug(f"Duplicate message (still processing): {message_id}")
                return {
                    "status": "accepted",
                    "type": "processing",
                    "message_id": message_id,
                }
            # FAILED state - proceed with retry

    # 4. Detect payload type
    payload_type = (
        "whatsapp"
        if raw_json.get("object") == "whatsapp_business_account"
        else "chattigo"
    )

    # 5. Quick validation before accepting
    validation_error = _quick_validate(raw_json, payload_type)
    if validation_error:
        if message_id:
            await idempotency.mark_failed(message_id)
        return validation_error

    # 6. Log message receipt
    _log_message_receipt(raw_json, payload_type, message_id)

    # 7. Queue for background processing
    task = WebhookTask(
        message_id=message_id or "no_id",
        payload_type=payload_type,
        raw_json=raw_json,
        settings=settings,
    )

    processor = WebhookProcessor(
        idempotency_service=idempotency,
        langgraph_service_factory=_get_langgraph_service,
        db_session_factory=get_async_db,
    )
    background_tasks.add_task(processor.process_in_background, task)

    # 8. Return immediately per Chattigo ISV requirement
    logger.info(f"Message accepted for processing: {message_id or 'no_id'}")
    return {
        "status": "accepted",
        "message_id": message_id,
        "processing": "background",
    }


def _extract_message_id(raw_json: dict) -> str | None:
    """
    Extract unique message ID from webhook payload.

    Supports both Chattigo ISV format and WhatsApp standard format.

    Args:
        raw_json: Raw webhook payload

    Returns:
        Prefixed message ID or None if not extractable
    """
    # Chattigo ISV format: direct 'id' field
    if raw_json.get("id"):
        return f"chattigo:{raw_json['id']}"

    # WhatsApp standard format: nested in entry/changes/messages
    if raw_json.get("object") == "whatsapp_business_account":
        try:
            entry = raw_json.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            messages = changes.get("value", {}).get("messages", [])
            if messages and messages[0].get("id"):
                return f"whatsapp:{messages[0]['id']}"
        except (IndexError, KeyError, TypeError):
            pass

    return None


def _quick_validate(raw_json: dict, payload_type: str) -> dict | None:
    """
    Quick validation before accepting message.

    Performs lightweight checks that don't require DB access.

    Args:
        raw_json: Raw webhook payload
        payload_type: "whatsapp" or "chattigo"

    Returns:
        Error dict if validation fails, None if valid
    """
    if payload_type == "chattigo":
        # Skip OUTBOUND messages (sent by bot, not user)
        if raw_json.get("chatType") == "OUTBOUND":
            return {"status": "ok", "type": "outbound_ignored"}

        # Skip status updates (no content)
        content = raw_json.get("content")
        is_attachment = raw_json.get("isAttachment", False)
        if not content and not is_attachment:
            return {"status": "ok", "type": "status_update"}

        # Require msisdn
        if not raw_json.get("msisdn"):
            return {"status": "error", "message": "Missing msisdn"}

    elif payload_type == "whatsapp":
        # Check for status updates
        try:
            entry = raw_json.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            # Status updates have 'statuses' instead of 'messages'
            if value.get("statuses") and not value.get("messages"):
                return {"status": "ok", "type": "status_update"}

        except (IndexError, KeyError, TypeError):
            pass

    return None


def _log_message_receipt(raw_json: dict, payload_type: str, message_id: str | None) -> None:
    """Log message receipt for monitoring."""
    if payload_type == "chattigo":
        msisdn = raw_json.get("msisdn", "unknown")
        msg_type = raw_json.get("type", "unknown")
        content = raw_json.get("content", "")
        preview = f"{content[:50]}..." if content and len(content) > 50 else content
        logger.info(
            f"Webhook received [Chattigo]: msisdn={msisdn}, "
            f"type={msg_type}, id={message_id}, content={preview}"
        )
    else:
        try:
            entry = raw_json.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            messages = changes.get("value", {}).get("messages", [])
            if messages:
                msg = messages[0]
                from_num = msg.get("from", "unknown")
                msg_type = msg.get("type", "unknown")
                logger.info(
                    f"Webhook received [WhatsApp]: from={from_num}, "
                    f"type={msg_type}, id={message_id}"
                )
        except (IndexError, KeyError, TypeError):
            logger.info(f"Webhook received [WhatsApp]: id={message_id}")


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
