# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Streaming endpoint for Pharmacy Testing - SSE with bypass routing.
# ============================================================================
"""
Pharmacy Streaming API - SSE streaming endpoint for pharmacy testing.

Provides streaming response for the Vue.js pharmacy testing interface,
compatible with Vercel AI SDK. Supports bypass routing for multi-tenant.
"""

from __future__ import annotations

import json
import logging
import time
import uuid as uuid_module
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.admin.pharmacy_models import PharmacyTestRequest
from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.models.chat import ChatStreamEvent, StreamEventType
from app.models.message import (
    ButtonReply,
    Contact,
    InteractiveContent,
    ListReply,
    WhatsAppMessage,
)
from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pharmacy", tags=["Pharmacy Admin Streaming"])


async def _get_langgraph_service() -> LangGraphChatbotService:
    """Get or create LangGraph service instance."""
    service = LangGraphChatbotService()
    await service.initialize()
    return service


@router.post("/test/stream")
async def send_test_message_stream(
    request: PharmacyTestRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings=Depends(get_settings),  # noqa: B008
) -> StreamingResponse:
    """
    Streaming version of /admin/pharmacy/test with bypass routing support.

    Uses Server-Sent Events (SSE) to stream real-time progress updates.
    Evaluates bypass rules to route to the correct agent/domain.

    Args:
        request: PharmacyTestRequest with message and phone details
        db: Database session for bypass rule evaluation
        settings: Application settings

    Returns:
        StreamingResponse with SSE events
    """

    async def generate_sse_stream():
        """Generate SSE events with bypass routing support."""
        start_time = time.time()

        try:
            service = await _get_langgraph_service()

            # Build WhatsApp message (same as non-streaming endpoint)
            customer_phone = request.phone_number
            timestamp = str(int(time.time()))
            message_id = str(uuid_module.uuid4())

            wa_message: WhatsAppMessage
            if request.interactive_response:
                ir = request.interactive_response
                ir_type: Literal["button_reply", "list_reply"] = (
                    "button_reply" if ir.type == "button_reply" else "list_reply"
                )
                interactive = InteractiveContent(
                    type=ir_type,
                    button_reply=(
                        ButtonReply(id=ir.id, title=ir.title)
                        if ir.type == "button_reply"
                        else None
                    ),
                    list_reply=(
                        ListReply(id=ir.id, title=ir.title)
                        if ir.type == "list_reply"
                        else None
                    ),
                )
                wa_message = WhatsAppMessage.model_validate({
                    "from": customer_phone,
                    "id": message_id,
                    "timestamp": timestamp,
                    "type": "interactive",
                    "interactive": interactive.model_dump(),
                })
            elif request.message:
                wa_message = WhatsAppMessage.model_validate({
                    "from": customer_phone,
                    "id": message_id,
                    "timestamp": timestamp,
                    "type": "text",
                    "text": {"body": request.message},
                })
            else:
                error_event = _create_error_event("Se requiere 'message' o 'interactive_response'")
                yield f"data: {json.dumps(error_event)}\n\n"
                return

            contact = Contact(wa_id=customer_phone, profile={"name": "Test User"})

            # Evaluate bypass routing
            bypass_result = await _evaluate_bypass_routing(
                db, settings, customer_phone, request.whatsapp_phone_number_id
            )

            # Determine domain and organization
            domain = bypass_result.get("domain", "pharmacy")
            organization_id = bypass_result.get("organization_id")
            pharmacy_id_raw = bypass_result.get("pharmacy_id") or request.pharmacy_id
            pharmacy_id: UUID | None = (
                UUID(pharmacy_id_raw) if isinstance(pharmacy_id_raw, str) else pharmacy_id_raw
            )
            target_agent = bypass_result.get("target_agent")

            logger.info(
                f"[STREAM] Bypass result: domain={domain}, org={organization_id}, "
                f"pharmacy={pharmacy_id}, target_agent={target_agent}"
            )

            # Send initial thinking event
            yield _format_sse_event(ChatStreamEvent(
                event_type=StreamEventType.THINKING,
                message="Analizando tu consulta...",
                agent_current="orchestrator",
                progress=0.1,
                metadata={"bypass_matched": bypass_result.get("matched", False)},
                timestamp=_get_timestamp(),
            ))

            # Process message with streaming
            # Use process_webhook_message for full bypass support
            result = await service.process_webhook_message(
                message=wa_message,
                contact=contact,
                business_domain=domain,
                db_session=db,
                organization_id=organization_id,
                pharmacy_id=pharmacy_id,
                bypass_target_agent=target_agent,
                isolated_history=bypass_result.get("isolated_history", False),
                bypass_rule_id=bypass_result.get("rule_id"),
            )

            processing_time = int((time.time() - start_time) * 1000)

            # Send processing event
            yield _format_sse_event(ChatStreamEvent(
                event_type=StreamEventType.PROCESSING,
                message="Procesando respuesta...",
                agent_current=target_agent or "pharmacy_operations_agent",
                progress=0.7,
                metadata={"domain": domain},
                timestamp=_get_timestamp(),
            ))

            # Extract response and interactive data
            response_text = result.message if result else ""
            result_metadata: dict[str, Any] = result.metadata if result and result.metadata else {}
            graph_result: dict[str, Any] = result_metadata.get("graph_result", {})

            # Extract interactive elements
            interactive_data = _extract_interactive_data(graph_result)

            # Send complete event with full response
            complete_metadata: dict[str, Any] = {
                "processing_time_ms": processing_time,
                "domain": domain,
                "organization_id": str(organization_id) if organization_id else None,
                "pharmacy_id": str(pharmacy_id) if pharmacy_id else None,
                "bypass_matched": bypass_result.get("matched", False),
                "session_id": result_metadata.get("conversation_id", f"pharmacy_{customer_phone}"),
                # Interactive data for frontend
                "response_type": interactive_data.get("response_type", "text"),
                "response_buttons": interactive_data.get("response_buttons"),
                "response_list_items": interactive_data.get("response_list_items"),
                # Graph state for debugging
                "graph_state": {
                    "workflow_step": graph_result.get("workflow_step"),
                    "customer_identified": graph_result.get("customer_identified", False),
                    "awaiting_confirmation": graph_result.get("awaiting_confirmation", False),
                },
            }

            yield _format_sse_event(ChatStreamEvent(
                event_type=StreamEventType.COMPLETE,
                message=response_text,
                agent_current=target_agent or graph_result.get("next_agent", "unknown"),
                progress=1.0,
                metadata=complete_metadata,
                timestamp=_get_timestamp(),
            ))

        except Exception as e:
            logger.error(f"[STREAM] Error: {e}", exc_info=True)
            yield f"data: {json.dumps(_create_error_event(str(e)))}\n\n"

    return StreamingResponse(
        generate_sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _evaluate_bypass_routing(
    db: AsyncSession,
    settings,
    wa_id: str,
    whatsapp_phone_number_id: str | None,
) -> dict[str, Any]:
    """Evaluate bypass routing rules."""
    result: dict[str, Any] = {"matched": False, "domain": "pharmacy"}

    if not settings.MULTI_TENANT_MODE:
        return result

    try:
        from app.services.bypass_routing_service import BypassRoutingService

        bypass_service = BypassRoutingService(db)
        match = await bypass_service.evaluate_bypass_rules(wa_id, whatsapp_phone_number_id)

        if match:
            result = {
                "matched": True,
                "organization_id": match.organization_id,
                "domain": match.domain or "pharmacy",
                "target_agent": match.target_agent,
                "pharmacy_id": match.pharmacy_id,
                "isolated_history": match.isolated_history,
                "rule_id": match.rule_id,
            }
            logger.info(f"[STREAM] Bypass matched: {result}")

    except Exception as e:
        logger.error(f"[STREAM] Bypass evaluation error: {e}")

    return result


def _extract_interactive_data(graph_result: dict) -> dict[str, Any]:
    """Extract interactive message data from graph result.

    Uses the EXPLICIT response_type from graph_result (set by template_formatter)
    rather than inferring from presence of buttons/list_items.
    This prevents issues when both fields exist due to checkpoint state.
    """
    # Use explicit response_type from graph_result (set by template_formatter)
    # Fallback to "text" if not set
    response_type = graph_result.get("response_type", "text")
    data: dict[str, Any] = {"response_type": response_type}

    # Extract based on response_type (mutually exclusive)
    if response_type == "buttons":
        buttons = graph_result.get("response_buttons") or graph_result.get("buttons")
        if buttons:
            data["response_buttons"] = [
                {"id": btn.get("id", ""), "titulo": btn.get("titulo", btn.get("title", ""))}
                for btn in buttons
            ]
    elif response_type == "list":
        list_items = graph_result.get("response_list_items") or graph_result.get("list_items")
        if list_items:
            data["response_list_items"] = [
                {
                    "id": item.get("id", ""),
                    "titulo": item.get("titulo", item.get("title", "")),
                    "descripcion": item.get("descripcion", item.get("description")),
                }
                for item in list_items
            ]

    return data


def _format_sse_event(event: ChatStreamEvent) -> str:
    """Format event as SSE data line."""
    event_data = event.model_dump()
    if hasattr(event.event_type, "value"):
        event_data["event_type"] = event.event_type.value
    return f"data: {json.dumps(event_data)}\n\n"


def _create_error_event(message: str) -> dict[str, Any]:
    """Create error event dict."""
    return {
        "event_type": "error",
        "message": f"Error: {message}",
        "agent_current": "fallback",
        "progress": 0.0,
        "metadata": {"error": message},
        "timestamp": _get_timestamp(),
    }


def _get_timestamp() -> str:
    """Get current ISO timestamp."""
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
