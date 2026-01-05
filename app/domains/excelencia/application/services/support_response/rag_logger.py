"""
RAG Query Logger Service - Single responsibility for RAG analytics logging.

This module provides:
- SearchMetrics: Dataclass for RAG search metrics
- SearchResult: Dataclass for RAG search results with context and metrics
- RagQueryLogger: Service for logging RAG queries with complete data

Follows SRP: Only responsible for RAG query logging.
Agents call this service after response generation.
"""

import asyncio
import logging
from dataclasses import dataclass

from app.database.async_db import get_async_db_context
from app.repositories.rag_query_log_repository import RagQueryLogRepository

logger = logging.getLogger(__name__)


@dataclass
class SearchMetrics:
    """Metrics from a RAG search operation."""

    latency_ms: float
    relevance_score: float | None
    context_used: list[str]
    result_count: int


@dataclass
class SearchResult:
    """Result from KnowledgeBaseSearch with context and metrics."""

    context: str
    metrics: SearchMetrics

    def has_context(self) -> bool:
        """Check if search returned meaningful context."""
        return bool(self.context and self.context.strip())

    def is_empty(self) -> bool:
        """Check if search returned no results."""
        return self.metrics.result_count == 0


class RagQueryLogger:
    """
    Service for logging RAG queries with complete data.

    Follows SRP: Only responsible for RAG query logging.
    Agents call this service after response generation to ensure
    logs contain the complete query-response pair.

    Usage:
        logger = RagQueryLogger(agent_key="my_agent")

        # After response generation:
        logger.log_async(
            query="user question",
            metrics=search_metrics,
            response="generated response",
        )
    """

    def __init__(self, agent_key: str):
        """
        Initialize logger with agent identifier.

        Args:
            agent_key: Identifier for the agent performing the search
        """
        self._agent_key = agent_key

    async def log(
        self,
        query: str,
        metrics: SearchMetrics | None,
        response: str,
        token_count: int = 0,
    ) -> None:
        """
        Log RAG query with response (awaitable version).

        Args:
            query: User query text
            metrics: Search metrics (latency, relevance, context)
            response: Generated response text
            token_count: Tokens used in generation
        """
        try:
            async with get_async_db_context() as db:
                repo = RagQueryLogRepository(db)
                await repo.create(
                    query=query,
                    context_used=metrics.context_used if metrics else [],
                    response=response,
                    token_count=token_count,
                    latency_ms=metrics.latency_ms if metrics else 0.0,
                    relevance_score=metrics.relevance_score if metrics else None,
                    agent_key=self._agent_key,
                )
                logger.debug(f"RAG query logged for agent={self._agent_key}")
        except Exception as e:
            # Don't fail the main operation if logging fails
            logger.warning(f"Failed to log RAG query: {e}")

    def log_async(
        self,
        query: str,
        metrics: SearchMetrics | None,
        response: str,
        token_count: int = 0,
    ) -> None:
        """
        Fire-and-forget logging (non-blocking).

        Creates a background task to log the query without
        blocking the main response flow.

        Args:
            query: User query text
            metrics: Search metrics (latency, relevance, context)
            response: Generated response text
            token_count: Tokens used in generation
        """
        asyncio.create_task(self.log(query, metrics, response, token_count))


__all__ = ["RagQueryLogger", "SearchMetrics", "SearchResult"]
