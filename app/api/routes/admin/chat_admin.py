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
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.models.chat import (
    ChatAgentConfigResponse,
    ChatGraphResponse,
    ChatMetricsResponse,
    ChatTestRequest,
    ChatTestResponse,
    ExecutionStepModel,
)
from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================
# SERVICE SINGLETON
# ============================================================

_chat_service: LangGraphChatbotService | None = None


async def _get_chat_service() -> LangGraphChatbotService:
    """Get or initialize the chat service singleton."""
    global _chat_service

    if _chat_service is None:
        try:
            _chat_service = LangGraphChatbotService()
            await _chat_service.initialize()
            logger.info("Chat service initialized for admin endpoints")
        except Exception as e:
            logger.error(f"Failed to initialize chat service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chat service temporarily unavailable",
            ) from e

    return _chat_service


# ============================================================
# IN-MEMORY METRICS STORAGE (simple implementation)
# ============================================================

_metrics_store: dict[str, Any] = {
    "total_messages": 0,
    "total_sessions": 0,
    "response_times": [],
    "errors": 0,
    "agents_used": {},
    "last_reset": datetime.now(UTC).isoformat(),
}


def _update_metrics(
    response_time_ms: float,
    agent_used: str,
    is_error: bool = False,
) -> None:
    """Update in-memory metrics after a test."""
    _metrics_store["total_messages"] += 1
    _metrics_store["response_times"].append(response_time_ms)

    # Keep only last 1000 response times
    if len(_metrics_store["response_times"]) > 1000:
        _metrics_store["response_times"] = _metrics_store["response_times"][-1000:]

    if is_error:
        _metrics_store["errors"] += 1

    if agent_used not in _metrics_store["agents_used"]:
        _metrics_store["agents_used"][agent_used] = 0
    _metrics_store["agents_used"][agent_used] += 1


# ============================================================
# ENDPOINTS
# ============================================================


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
        service = await _get_chat_service()

        # Generate session_id if not provided
        session_id = request.session_id or str(uuid.uuid4())

        logger.info(f"Chat admin test: user={request.user_id}, session={session_id}")

        # Process the message
        result = await service.process_chat_message(
            message=request.message,
            user_id=request.user_id,
            session_id=session_id,
            metadata=request.context or {},
            db_session=db_session,
        )

        response_time_ms = (time.time() - start_time) * 1000
        agent_used = result.get("agent_used", "unknown")

        # Update metrics
        _update_metrics(response_time_ms, agent_used, is_error=False)

        # Build execution steps if debug mode - dynamically from agent_history
        execution_steps: list[ExecutionStepModel] | None = None
        graph_result = result.get("graph_result", {})

        if request.debug:
            agent_history = graph_result.get("agent_history", [])
            routing_decision = graph_result.get("routing_decision", {})

            execution_steps = []
            step_number = 1

            # Step 1: Message received
            execution_steps.append(
                ExecutionStepModel(
                    id=str(uuid.uuid4()),
                    step_number=step_number,
                    node_type="start",
                    name="message_received",
                    description="User message received",
                    input={"message": request.message},
                    output=None,
                    duration_ms=10,
                    status="completed",
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )
            step_number += 1

            # Steps 2+: Each agent in history
            for agent_name in agent_history:
                node_type = (
                    "orchestrator"
                    if agent_name == "orchestrator"
                    else ("supervisor" if agent_name == "supervisor" else "agent")
                )
                execution_steps.append(
                    ExecutionStepModel(
                        id=str(uuid.uuid4()),
                        step_number=step_number,
                        node_type=node_type,
                        name=agent_name,
                        description=f"Executed by {agent_name}",
                        input=routing_decision if agent_name == "orchestrator" else None,
                        output=None,
                        duration_ms=int(response_time_ms / max(len(agent_history), 1)),
                        status="completed",
                        timestamp=datetime.now(UTC).isoformat(),
                    )
                )
                step_number += 1

            # Final step: Response sent
            execution_steps.append(
                ExecutionStepModel(
                    id=str(uuid.uuid4()),
                    step_number=step_number,
                    node_type="end",
                    name="response_sent",
                    description="Response generated",
                    input=None,
                    output={"response_preview": result.get("response", "")[:100]},
                    duration_ms=5,
                    status="completed",
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )

        return ChatTestResponse(
            session_id=session_id,
            response=result.get("response", ""),
            agent_used=agent_used,
            execution_steps=execution_steps,
            debug_info={
                "response_time_ms": response_time_ms,
                "requires_human": result.get("requires_human", False),
                "is_complete": result.get("is_complete", False),
                # Graph execution details
                "agent_history": graph_result.get("agent_history", []),
                "routing_decision": graph_result.get("routing_decision", {}),
                "orchestrator_analysis": graph_result.get("orchestrator_analysis", {}),
                "routing_attempts": graph_result.get("routing_attempts", 0),
            }
            if request.debug
            else None,
            metadata={
                "user_id": request.user_id,
                "processing_time_ms": response_time_ms,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        response_time_ms = (time.time() - start_time) * 1000
        _update_metrics(response_time_ms, "error", is_error=True)

        logger.error(f"Error in chat admin test: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing test message: {e}",
        ) from e


@router.get("/metrics", response_model=ChatMetricsResponse)
async def get_chat_metrics(days: int = 7) -> ChatMetricsResponse:
    """
    Get chat metrics for the Chat Visualizer.

    Returns aggregated metrics about chat usage.
    """
    try:
        response_times = _metrics_store["response_times"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        total_messages = _metrics_store["total_messages"]
        errors = _metrics_store["errors"]
        error_rate = (errors / total_messages * 100) if total_messages > 0 else 0.0

        return ChatMetricsResponse(
            total_messages=total_messages,
            total_sessions=_metrics_store["total_sessions"],
            total_tokens=0,  # Would need to track this in real implementation
            avg_response_time_ms=round(avg_response_time, 2),
            tool_calls_count=0,  # Would need to track this in real implementation
            error_count=errors,
            error_rate=round(error_rate, 2),
            agents_used=_metrics_store["agents_used"],
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
    # For now, return mock data - would need to implement execution tracing
    steps = [
        ExecutionStepModel(
            id=str(uuid.uuid4()),
            step_number=1,
            node_type="start",
            name="orchestrator",
            description="SuperOrchestrator routing",
            input=None,
            output=None,
            duration_ms=50,
            status="completed",
            timestamp=datetime.now(UTC).isoformat(),
        ),
        ExecutionStepModel(
            id=str(uuid.uuid4()),
            step_number=2,
            node_type="decision",
            name="intent_classification",
            description="Classifying user intent",
            input=None,
            output=None,
            duration_ms=100,
            status="completed",
            timestamp=datetime.now(UTC).isoformat(),
        ),
        ExecutionStepModel(
            id=str(uuid.uuid4()),
            step_number=3,
            node_type="llm_call",
            name="agent_response",
            description="Generating response",
            input=None,
            output=None,
            duration_ms=500,
            status="completed",
            timestamp=datetime.now(UTC).isoformat(),
        ),
    ]

    return {"steps": steps}


@router.get("/execution/{message_id}/graph", response_model=ChatGraphResponse)
async def get_execution_graph(message_id: str) -> ChatGraphResponse:
    """
    Get graph visualization data for a message execution.

    Returns nodes and edges for the execution flow visualization.
    """
    # Define the SuperOrchestrator graph structure
    nodes = [
        {"id": "start", "type": "entry", "label": "Start", "data": None},
        {"id": "orchestrator", "type": "router", "label": "SuperOrchestrator", "data": None},
        {"id": "intent", "type": "decision", "label": "Intent Classification", "data": None},
        {"id": "greeting_agent", "type": "agent", "label": "Greeting", "data": None},
        {"id": "excelencia_agent", "type": "agent", "label": "Excelencia", "data": None},
        {"id": "support_agent", "type": "agent", "label": "Support", "data": None},
        {"id": "fallback_agent", "type": "agent", "label": "Fallback", "data": None},
        {"id": "farewell_agent", "type": "agent", "label": "Farewell", "data": None},
        {"id": "response", "type": "end", "label": "Response", "data": None},
    ]

    edges = [
        {"id": "e1", "source": "start", "target": "orchestrator"},
        {"id": "e2", "source": "orchestrator", "target": "intent"},
        {"id": "e3", "source": "intent", "target": "greeting_agent"},
        {"id": "e4", "source": "intent", "target": "excelencia_agent"},
        {"id": "e5", "source": "intent", "target": "support_agent"},
        {"id": "e6", "source": "intent", "target": "fallback_agent"},
        {"id": "e7", "source": "intent", "target": "farewell_agent"},
        {"id": "e8", "source": "greeting_agent", "target": "response"},
        {"id": "e9", "source": "excelencia_agent", "target": "response"},
        {"id": "e10", "source": "support_agent", "target": "response"},
        {"id": "e11", "source": "fallback_agent", "target": "response"},
        {"id": "e12", "source": "farewell_agent", "target": "response"},
    ]

    return ChatGraphResponse(
        nodes=[
            {"id": n["id"], "type": n["type"], "label": n["label"], "data": n["data"]}
            for n in nodes
        ],
        edges=[
            {"id": e["id"], "source": e["source"], "target": e["target"]}
            for e in edges
        ],
        current_node="response",
        visited_nodes=["start", "orchestrator", "intent", "response"],
    )


@router.get("/config", response_model=ChatAgentConfigResponse)
async def get_agent_config() -> ChatAgentConfigResponse:
    """
    Get current agent configuration.

    Returns the configuration being used by the chat agent.
    """
    try:
        # Get configuration from settings
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
