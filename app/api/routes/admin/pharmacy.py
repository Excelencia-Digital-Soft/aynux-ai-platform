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
import uuid
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.admin.pharmacy_helpers import (
    build_graph_state,
    build_session_graph_state,
    deserialize_messages,
    extract_bot_response,
    get_pharmacy_graph_data,
    update_session_from_result,
)
from app.api.routes.admin.pharmacy_models import (
    PharmacyResponse,
    PharmacySessionState,
    PharmacyTestRequest,
    PharmacyTestResponse,
)
from app.api.routes.admin.pharmacy_service import (
    get_session_repository,
    invoke_pharmacy_graph,
)
from app.core.tenancy.pharmacy_config_service import PharmacyConfigService
from app.database.async_db import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/pharmacy", tags=["Pharmacy Admin"])


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
) -> PharmacyTestResponse:
    """
    Send a test message to the pharmacy agent.

    This endpoint simulates a WhatsApp conversation for testing purposes.
    Supports multi-turn conversations via session_id.
    """
    try:
        # 1. Load pharmacy config by pharmacy ID (not organization_id)
        service = PharmacyConfigService(db)
        try:
            pharmacy_id = UUID(request.pharmacy_id)
            config = await service.get_config_by_id(pharmacy_id)
            org_id = config.organization_id
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pharmacy_id format: {e}",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pharmacy not found: {e}",
            ) from e

        # 2. Get or create session
        session_repo = get_session_repository()
        session_id = request.session_id or str(uuid.uuid4())
        existing_session = await session_repo.get(session_id)

        if existing_session:
            session = existing_session
            previous_messages = deserialize_messages(session.messages)

            # SAFETY: Validate session state consistency
            # If identification_step is set, customer SHOULD NOT be identified yet
            if session.identification_step is not None and session.customer_identified:
                logger.warning(
                    f"[SESSION] Inconsistent state in session {session_id}: "
                    f"identification_step={session.identification_step} but "
                    f"customer_identified={session.customer_identified}. "
                    f"Resetting identification state."
                )
                session.customer_identified = False
                session.plex_customer_id = None
                session.plex_customer = None
        else:
            session = PharmacySessionState(
                session_id=session_id,
                organization_id=str(org_id),
                pharmacy_id=str(config.pharmacy_id),
                customer_id=request.phone_number or "5491122334455",
                # Pharmacy configuration (CRITICAL for multi-turn)
                pharmacy_name=config.pharmacy_name,
                pharmacy_phone=config.pharmacy_phone,
            )
            previous_messages = []

        # 3. Build graph state and invoke
        new_message = HumanMessage(content=request.message)
        graph_state = build_graph_state(
            session=session,
            organization_id=str(org_id),
            pharmacy_id=str(config.pharmacy_id),
            previous_messages=previous_messages,
            new_message=new_message,
        )

        result = await invoke_pharmacy_graph(graph_state, conversation_id=session_id)

        # 4. Extract response and update session
        response_text = extract_bot_response(result)
        update_session_from_result(session, result)

        # 5. Save session
        await session_repo.save(session)

        # 6. Build response
        return PharmacyTestResponse(
            session_id=session_id,
            response=response_text,
            execution_steps=[
                {
                    "workflow_step": result.get("workflow_step"),
                    "next_agent": result.get("next_agent"),
                    "customer_identified": result.get("customer_identified", False),
                }
            ],
            graph_state={
                "customer_identified": result.get("customer_identified", False),
                "has_debt": result.get("has_debt", False),
                "total_debt": result.get("total_debt"),
                "debt_status": result.get("debt_status"),
                "workflow_step": result.get("workflow_step"),
                "awaiting_confirmation": result.get("awaiting_confirmation", False),
                "is_complete": result.get("is_complete", False),
                "awaiting_payment": result.get("awaiting_payment", False),
                "mp_init_point": result.get("mp_init_point"),
            },
            metadata={
                "pharmacy_id": request.pharmacy_id,
                "pharmacy_name": config.pharmacy_name,
                "message_count": len(session.messages),
                "is_new_session": request.session_id is None,
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
