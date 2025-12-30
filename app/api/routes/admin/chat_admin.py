# ============================================================================
# SCOPE: GLOBAL
# Description: Chat Admin API for Chat Visualizer - test agent, metrics, config.
# Tenant-Aware: No - uses global SuperOrchestrator.
# ============================================================================
"""
Chat Admin API - Endpoints for the Chat Visualizer testing interface.

Provides endpoints for testing the chat agent, viewing metrics,
and visualizing agent execution graphs.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.admin.chat_admin_helpers import (
    build_debug_execution_steps,
    build_webhook_execution_steps,
    get_default_graph,
    get_mock_execution_steps,
)
from app.api.routes.admin.chat_admin_service import (
    get_chat_service,
    get_metrics_summary,
    update_metrics,
)
from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.models.chat import (
    ChatAgentConfigResponse,
    ChatGraphResponse,
    ChatMetricsResponse,
    ChatTestRequest,
    ChatTestResponse,
    ExecutionStepModel,
    WebhookSimulationRequest,
)
from app.models.message import Contact, WhatsAppMessage

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/test", response_model=ChatTestResponse)
async def test_chat_agent(
    request: ChatTestRequest,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> ChatTestResponse:
    """
    Test the chat agent with a message.

    This endpoint is designed for the Chat Visualizer to test
    agent responses with optional debug information.
    """
    start_time = time.time()

    try:
        service = await get_chat_service()
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"Chat admin test: user={request.user_id}, session={session_id}")

        result = await service.process_chat_message(
            message=request.message,
            user_id=request.user_id,
            session_id=session_id,
            metadata=request.context or {},
            db_session=db_session,
        )

        response_time_ms = (time.time() - start_time) * 1000
        agent_used = result.get("agent_used", "unknown")
        graph_result = result.get("graph_result", {})

        update_metrics(response_time_ms, agent_used, is_error=False)

        execution_steps: list[ExecutionStepModel] | None = None
        if request.debug:
            execution_steps = build_debug_execution_steps(
                message=request.message,
                response=result.get("response", ""),
                agent_history=graph_result.get("agent_history", []),
                routing_decision=graph_result.get("routing_decision", {}),
                response_time_ms=response_time_ms,
            )

        return ChatTestResponse(
            session_id=session_id,
            response=result.get("response", ""),
            agent_used=agent_used,
            execution_steps=execution_steps,
            debug_info=(
                {
                    "response_time_ms": response_time_ms,
                    "requires_human": result.get("requires_human", False),
                    "is_complete": result.get("is_complete", False),
                    "agent_history": graph_result.get("agent_history", []),
                    "routing_decision": graph_result.get("routing_decision", {}),
                    "orchestrator_analysis": graph_result.get("orchestrator_analysis", {}),
                    "routing_attempts": graph_result.get("routing_attempts", 0),
                }
                if request.debug
                else None
            ),
            metadata={
                "user_id": request.user_id,
                "processing_time_ms": response_time_ms,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        update_metrics(response_time_ms, "error", is_error=True)
        logger.error(f"Error in chat admin test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing test message: {e}",
        ) from e


@router.post("/test-webhook", response_model=ChatTestResponse)
async def test_webhook_simulation(
    request: WebhookSimulationRequest,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> ChatTestResponse:
    """
    Simulate WhatsApp webhook using the exact same flow as production.

    Uses process_webhook_message() instead of process_chat_message() to test
    the full webhook processing pipeline from the Chat Visualizer UI.
    """
    start_time = time.time()

    try:
        service = await get_chat_service()
        session_id = request.session_id or f"web_{request.phone_number}"

        logger.info(
            f"Webhook simulation: phone={request.phone_number}, "
            f"domain={request.business_domain}, session={session_id}"
        )

        message = WhatsAppMessage.model_validate(
            {
                "from": request.phone_number,
                "id": str(uuid.uuid4()),
                "timestamp": str(int(time.time())),
                "type": "text",
                "text": {"body": request.message},
            }
        )

        contact = Contact(
            wa_id=request.phone_number,
            profile={"name": request.user_name},
        )

        result = await service.process_webhook_message(
            message=message,
            contact=contact,
            business_domain=request.business_domain,
            db_session=db_session,
        )

        response_time_ms = (time.time() - start_time) * 1000

        # Extract full agent history from graph_result (not just agent_used)
        graph_result = result.metadata.get("graph_result", {}) if result.metadata else {}
        agent_history = graph_result.get("agent_history", [])
        agent_used = result.metadata.get("agent_used", "unknown") if result.metadata else "unknown"

        update_metrics(response_time_ms, agent_used, is_error=result.status != "success")

        execution_steps: list[ExecutionStepModel] | None = None
        if request.debug:
            execution_steps = build_webhook_execution_steps(
                message=request.message,
                response=result.message or "",
                phone_number=request.phone_number,
                user_name=request.user_name,
                business_domain=request.business_domain,
                agent_history=agent_history,
                response_time_ms=response_time_ms,
            )

        return ChatTestResponse(
            session_id=session_id,
            response=result.message,
            agent_used=agent_used,
            execution_steps=execution_steps,
            debug_info=(
                {
                    "response_time_ms": response_time_ms,
                    "requires_human": result.metadata.get("requires_human", False) if result.metadata else False,
                    "is_complete": True,
                    "webhook_simulation": True,
                    "channel": "WEB_SIMULATOR",
                    "business_domain": request.business_domain,
                }
                if request.debug
                else None
            ),
            metadata={
                "phone_number": request.phone_number,
                "user_name": request.user_name,
                "processing_time_ms": response_time_ms,
                "flow": "process_webhook_message",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        update_metrics(response_time_ms, "error", is_error=True)
        logger.error(f"Error in webhook simulation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook simulation: {e}",
        ) from e


@router.get("/metrics", response_model=ChatMetricsResponse)
async def get_chat_metrics(days: int = 7) -> ChatMetricsResponse:
    """
    Get chat metrics for the Chat Visualizer.

    Returns aggregated metrics about chat usage.
    """
    try:
        summary = get_metrics_summary()
        return ChatMetricsResponse(
            total_messages=summary["total_messages"],
            total_sessions=summary["total_sessions"],
            total_tokens=0,  # Would need to track this in real implementation
            avg_response_time_ms=summary["avg_response_time_ms"],
            tool_calls_count=0,  # Would need to track this in real implementation
            error_count=summary["errors"],
            error_rate=summary["error_rate"],
            agents_used=summary["agents_used"],
            period_days=days,
        )

    except Exception as e:
        logger.error(f"Error getting chat metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching metrics: {e}",
        ) from e


@router.get("/execution/{message_id}/steps")
async def get_execution_steps(message_id: str) -> dict[str, list[ExecutionStepModel]]:
    """
    Get execution steps for a specific message.

    Returns the execution trace for visualization.
    """
    _ = message_id  # Unused but part of API contract
    return {"steps": get_mock_execution_steps()}


@router.get("/execution/{message_id}/graph", response_model=ChatGraphResponse)
async def get_execution_graph(message_id: str) -> ChatGraphResponse:
    """
    Get graph visualization data for a message execution.

    Returns nodes and edges for the execution flow visualization.
    """
    _ = message_id  # Unused but part of API contract
    return get_default_graph()


@router.get("/config", response_model=ChatAgentConfigResponse)
async def get_agent_config() -> ChatAgentConfigResponse:
    """
    Get current agent configuration.

    Returns the configuration being used by the chat agent.
    """
    try:
        settings = get_settings()
        return ChatAgentConfigResponse(
            model=getattr(settings, "OLLAMA_API_MODEL_COMPLEX", "gemma2"),
            temperature=getattr(settings, "LLM_TEMPERATURE", 0.7),
            max_tokens=getattr(settings, "LLM_MAX_TOKENS", 2048),
            tools=["search_products", "get_knowledge", "check_order_status"],
            system_prompt="[System prompt configured in agent]",
            rag_enabled=getattr(settings, "RAG_ENABLED", True),
            rag_max_results=getattr(settings, "RAG_MAX_RESULTS", 5),
        )

    except Exception as e:
        logger.error(f"Error getting agent config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching config: {e}",
        ) from e
