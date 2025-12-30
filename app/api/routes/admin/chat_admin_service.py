# ============================================================================
# SCOPE: GLOBAL
# Description: Service layer for Chat Admin API - service lifecycle and metrics.
# ============================================================================
"""
Chat Admin Service - Service singleton management and metrics tracking.

Provides centralized chat service initialization and in-memory metrics
storage for the Chat Visualizer testing interface.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from app.services.langgraph_chatbot_service import LangGraphChatbotService

logger = logging.getLogger(__name__)

# ============================================================
# SERVICE SINGLETON
# ============================================================

_chat_service: LangGraphChatbotService | None = None


async def get_chat_service() -> LangGraphChatbotService:
    """
    Get or initialize the chat service singleton.

    Returns:
        Initialized LangGraphChatbotService instance

    Raises:
        HTTPException: If service initialization fails
    """
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
# IN-MEMORY METRICS STORAGE
# ============================================================

_metrics_store: dict[str, Any] = {
    "total_messages": 0,
    "total_sessions": 0,
    "response_times": [],
    "errors": 0,
    "agents_used": {},
    "last_reset": datetime.now(UTC).isoformat(),
}


def update_metrics(
    response_time_ms: float,
    agent_used: str,
    is_error: bool = False,
) -> None:
    """
    Update in-memory metrics after a test.

    Args:
        response_time_ms: Response time in milliseconds
        agent_used: Name of the agent that handled the request
        is_error: Whether the request resulted in an error
    """
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


def get_metrics_summary() -> dict[str, Any]:
    """
    Get a summary of current metrics.

    Returns:
        Dictionary with computed metrics summary
    """
    response_times = _metrics_store["response_times"]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

    total_messages = _metrics_store["total_messages"]
    errors = _metrics_store["errors"]
    error_rate = (errors / total_messages * 100) if total_messages > 0 else 0.0

    return {
        "total_messages": total_messages,
        "total_sessions": _metrics_store["total_sessions"],
        "avg_response_time_ms": round(avg_response_time, 2),
        "errors": errors,
        "error_rate": round(error_rate, 2),
        "agents_used": _metrics_store["agents_used"],
        "last_reset": _metrics_store["last_reset"],
    }


def reset_metrics() -> None:
    """Reset all metrics to initial values."""
    global _metrics_store
    _metrics_store = {
        "total_messages": 0,
        "total_sessions": 0,
        "response_times": [],
        "errors": 0,
        "agents_used": {},
        "last_reset": datetime.now(UTC).isoformat(),
    }
