# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API de admin para farmacias - listar, testing de agente.
# Tenant-Aware: Yes - lista farmacias de pharmacy_merchant_configs.
# ============================================================================
"""
Pharmacy Admin API - Endpoints for pharmacy testing and management.

Provides endpoints for the Vue.js pharmacy testing interface.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.admin.pharmacy_helpers import (
    build_session_graph_state,
    extract_interactive_data,
    get_pharmacy_graph_data,
    update_session_from_result,
)
from app.api.routes.admin.pharmacy_models import (
    InteractiveButton,
    InteractiveListItem,
    PharmacyResponse,
    PharmacySessionState,
    PharmacyTestRequest,
    PharmacyTestResponse,
)
from app.api.routes.admin.pharmacy_service import (
    get_session_repository,
)
from app.config.settings import get_settings
from app.core.tenancy.pharmacy_config_service import PharmacyConfigService
from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases.process_webhook_use_case import (
    ProcessWebhookUseCase,
)
from app.models.message import (
    ButtonReply,
    Contact,
    InteractiveContent,
    ListReply,
    TextMessage,
    WhatsAppMessage,
)
from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pharmacy", tags=["Pharmacy Admin"])


async def _get_langgraph_service() -> LangGraphChatbotService:
    """Get or create LangGraph service instance."""
    service = LangGraphChatbotService()
    await service.initialize()
    return service



@router.get("/list", response_model=list[PharmacyResponse])
async def list_pharmacies(
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> list[PharmacyResponse]:
    """
    List all available pharmacies for testing.

    Returns pharmacy configurations from the database.
    """
    try:
        service = PharmacyConfigService(db)
        pharmacies = await service.list_all_pharmacies()

        return [
            PharmacyResponse(
                id=p["id"],  # Use pharmacy config ID, not organization_id
                name=p["pharmacy_name"],
                code=p["whatsapp_phone_number"] or "",
                address=None,
                phone=None,
                active=p["mp_enabled"],
            )
            for p in pharmacies
        ]
    except Exception as e:
        logger.error(f"Error listing pharmacies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading pharmacies: {e}",
        ) from e


@router.post("/test", response_model=PharmacyTestResponse)
async def send_test_message(
    request: PharmacyTestRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    settings=Depends(get_settings),  # noqa: B008
) -> PharmacyTestResponse:
    """
    Send a test message to the pharmacy agent.

    This endpoint mirrors the EXACT behavior of the original webhook:
    1. Uses whatsapp_phone_number_id (DID) for bypass routing
    2. Bypass routing determines organization_id, pharmacy_id, domain, target_agent
    3. ProcessWebhookUseCase handles all business logic identically to production

    Args:
        request: PharmacyTestRequest with:
            - whatsapp_phone_number_id: Business phone (DID) - REQUIRED
            - phone_number: Customer phone - REQUIRED
            - message or interactive_response: Content to send
            - session_id: Optional existing session
            - pharmacy_id: Optional override (normally determined via bypass)
    """
    try:
        # 1. Construct WhatsApp Message (same as webhook_processor.py)
        customer_phone = request.phone_number
        timestamp = str(int(time.time()))
        message_id = str(uuid.uuid4())

        wa_message: WhatsAppMessage
        if request.interactive_response:
            ir = request.interactive_response
            interactive = InteractiveContent(
                type=ir.type,
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
            wa_message = WhatsAppMessage(
                from_=customer_phone,
                id=message_id,
                timestamp=timestamp,
                type="interactive",
                interactive=interactive,
            )
        elif request.message:
            wa_message = WhatsAppMessage(
                from_=customer_phone,
                id=message_id,
                timestamp=timestamp,
                type="text",
                text=TextMessage(body=request.message),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either 'message' or 'interactive_response' must be provided",
            )

        contact = Contact(wa_id=customer_phone, profile={"name": "Test User"})

        # 2. Execute Use Case - IDENTICAL to original webhook
        # The DID triggers bypass routing which determines organization/pharmacy
        langgraph_service = await _get_langgraph_service()
        use_case = ProcessWebhookUseCase(db, settings, langgraph_service)

        logger.info(
            f"[TEST_WEBHOOK] Processing test message: did={request.whatsapp_phone_number_id}, "
            f"phone={customer_phone}"
        )

        result = await use_case.execute(
            message=wa_message,
            contact=contact,
            whatsapp_phone_number_id=request.whatsapp_phone_number_id,
        )

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing webhook: {result.error_message}",
            )

        # 3. Extract Response Data
        bot_response = result.result
        response_text = bot_response.message if bot_response else ""
        metadata = bot_response.metadata if bot_response else {}

        # The graph result contains the full execution state
        graph_result = metadata.get("graph_result", {})

        # Determine the actual session ID used (handles isolation logic)
        real_session_id = metadata.get(
            "conversation_id", request.session_id or f"whatsapp_{customer_phone}"
        )

        # Extract pharmacy info from graph result (set by bypass routing)
        pharmacy_id_from_result = metadata.get("pharmacy_id") or request.pharmacy_id
        organization_id_from_result = metadata.get("organization_id")
        pharmacy_name_from_result = graph_result.get("pharmacy_name", "Unknown Pharmacy")

        # 4. Create session state for response and legacy compatibility
        session = PharmacySessionState(
            session_id=real_session_id,
            organization_id=str(organization_id_from_result) if organization_id_from_result else "",
            pharmacy_id=str(pharmacy_id_from_result) if pharmacy_id_from_result else "",
            customer_id=customer_phone,
            pharmacy_name=pharmacy_name_from_result,
            pharmacy_phone=request.whatsapp_phone_number_id,
        )

        # Populate session from graph result
        update_session_from_result(session, graph_result)

        # 5. Save session for legacy compatibility
        session_repo = get_session_repository()
        await session_repo.save(session)

        # Extract interactive data using helper
        interactive_data = extract_interactive_data(graph_result)

        # Convert interactive data to Pydantic models
        response_buttons = None
        response_list_items = None

        if interactive_data.get("response_buttons"):
            response_buttons = [
                InteractiveButton(id=btn["id"], titulo=btn["titulo"])
                for btn in interactive_data["response_buttons"]
            ]

        if interactive_data.get("response_list_items"):
            response_list_items = [
                InteractiveListItem(
                    id=item["id"],
                    titulo=item["titulo"],
                    descripcion=item.get("descripcion"),
                )
                for item in interactive_data["response_list_items"]
            ]

        return PharmacyTestResponse(
            session_id=real_session_id,
            response=response_text,
            response_type=interactive_data.get("response_type", "text"),
            response_buttons=response_buttons,
            response_list_items=response_list_items,
            execution_steps=[
                {
                    "workflow_step": graph_result.get("workflow_step"),
                    "next_agent": graph_result.get("next_agent"),
                    "customer_identified": graph_result.get("customer_identified", False),
                }
            ],
            graph_state={
                "customer_identified": graph_result.get("customer_identified", False),
                "has_debt": graph_result.get("has_debt", False),
                "total_debt": graph_result.get("total_debt"),
                "debt_status": graph_result.get("debt_status"),
                "workflow_step": graph_result.get("workflow_step"),
                "awaiting_confirmation": graph_result.get("awaiting_confirmation", False),
                "is_complete": graph_result.get("is_complete", False),
                "awaiting_payment": graph_result.get("awaiting_payment", False),
                "mp_init_point": graph_result.get("mp_init_point"),
            },
            metadata={
                "whatsapp_phone_number_id": request.whatsapp_phone_number_id,
                "pharmacy_id": pharmacy_id_from_result,
                "organization_id": str(organization_id_from_result) if organization_id_from_result else None,
                "pharmacy_name": pharmacy_name_from_result,
                "message_count": len(session.messages),
                "processing_mode": result.mode,
                "domain": result.domain,
                "bypass_matched": result.domain != ProcessWebhookUseCase.DEFAULT_DOMAIN,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in pharmacy test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing test message: {e}",
        ) from e



@router.get("/session/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """
    Get test session history.

    Returns the conversation history and state for a given session.
    """
    session_repo = get_session_repository()
    session = await session_repo.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    return {
        "session_id": session.session_id,
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in session.messages
        ],
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "execution_steps": [],
        "graph_state": build_session_graph_state(session),
    }


@router.delete("/session/{session_id}")
async def clear_session(session_id: str) -> dict[str, bool]:
    """
    Clear a test session.

    Removes session data from Redis cache.
    """
    session_repo = get_session_repository()
    exists = await session_repo.exists(session_id)

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    success = await session_repo.delete(session_id)
    return {"success": success}


@router.get("/graph/{session_id}")
async def get_graph_data(session_id: str) -> dict[str, Any]:
    """
    Get pharmacy graph visualization data.

    Returns data for visualizing the agent graph execution.
    """
    session_repo = get_session_repository()
    session = await session_repo.get(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    graph_data = get_pharmacy_graph_data(session)
    return graph_data.model_dump()
