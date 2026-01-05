"""
RAG Query Log Repository Implementation

SQLAlchemy implementation for RAG query logging and analytics operations.
Provides persistent storage for RAG search metrics and user feedback.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.rag_query_log import RagQueryLog

logger = logging.getLogger(__name__)


class RagQueryLogRepository:
    """
    Repository for RAG query log operations.

    Provides:
    - Logging of RAG queries with metrics
    - Pagination and filtering for analytics
    - Aggregated metrics for dashboards
    - User feedback tracking
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(
        self,
        query: str,
        context_used: list[str] | None = None,
        response: str | None = None,
        token_count: int = 0,
        latency_ms: float = 0.0,
        relevance_score: float | None = None,
        agent_key: str | None = None,
    ) -> RagQueryLog:
        """
        Create a new RAG query log entry.

        Args:
            query: User query text
            context_used: List of document titles/IDs used as context
            response: Generated response text
            token_count: Tokens used in generation
            latency_ms: Search latency in milliseconds
            relevance_score: Average relevance score (0-1)
            agent_key: Agent that performed the search

        Returns:
            Created RagQueryLog model
        """
        model = RagQueryLog(
            query=query,
            context_used=context_used or [],
            response=response,
            token_count=token_count,
            latency_ms=latency_ms,
            relevance_score=relevance_score,
            agent_key=agent_key,
        )

        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)

        logger.debug(f"Created RAG query log: {model.id} (agent={agent_key})")
        return model

    async def get_by_id(self, log_id: uuid.UUID | str) -> RagQueryLog | None:
        """
        Get a specific log entry by ID.

        Args:
            log_id: Log UUID

        Returns:
            RagQueryLog model or None if not found
        """
        if isinstance(log_id, str):
            log_id = uuid.UUID(log_id)

        result = await self.session.execute(
            select(RagQueryLog).where(RagQueryLog.id == log_id)
        )
        return result.scalar_one_or_none()

    async def get_paginated(
        self,
        page: int = 1,
        page_size: int = 25,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        agent_key: str | None = None,
        has_feedback: bool | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Get paginated log entries with optional filtering.

        Args:
            page: Page number (1-indexed)
            page_size: Number of entries per page
            start_date: Filter entries after this date
            end_date: Filter entries before this date
            agent_key: Filter by agent
            has_feedback: Filter by feedback presence

        Returns:
            Tuple of (list of log dictionaries, total count)
        """
        # Build base query
        stmt = select(RagQueryLog)
        count_stmt = select(func.count(RagQueryLog.id))

        # Apply filters
        if start_date:
            stmt = stmt.where(RagQueryLog.created_at >= start_date)
            count_stmt = count_stmt.where(RagQueryLog.created_at >= start_date)

        if end_date:
            stmt = stmt.where(RagQueryLog.created_at <= end_date)
            count_stmt = count_stmt.where(RagQueryLog.created_at <= end_date)

        if agent_key:
            stmt = stmt.where(RagQueryLog.agent_key == agent_key)
            count_stmt = count_stmt.where(RagQueryLog.agent_key == agent_key)

        if has_feedback is not None:
            if has_feedback:
                stmt = stmt.where(RagQueryLog.user_feedback.isnot(None))
                count_stmt = count_stmt.where(RagQueryLog.user_feedback.isnot(None))
            else:
                stmt = stmt.where(RagQueryLog.user_feedback.is_(None))
                count_stmt = count_stmt.where(RagQueryLog.user_feedback.is_(None))

        # Get total count
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Apply ordering and pagination
        stmt = stmt.order_by(RagQueryLog.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        # Execute query
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [model.to_dict() for model in models], total

    async def update_feedback(
        self,
        log_id: uuid.UUID | str,
        feedback: str,
    ) -> bool:
        """
        Update user feedback for a query log.

        Args:
            log_id: Log UUID
            feedback: Feedback value ('positive' or 'negative')

        Returns:
            True if updated, False if not found
        """
        if isinstance(log_id, str):
            log_id = uuid.UUID(log_id)

        if feedback not in ("positive", "negative"):
            raise ValueError("Feedback must be 'positive' or 'negative'")

        result = await self.session.execute(
            update(RagQueryLog)
            .where(RagQueryLog.id == log_id)
            .values(user_feedback=feedback, updated_at=datetime.now(UTC))
        )
        await self.session.commit()

        return result.rowcount > 0

    async def get_metrics_aggregated(
        self,
        time_range: str = "24h",
        agent_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregated metrics for analytics dashboard.

        Args:
            time_range: Time range ('1h', '24h', '7d', '30d')
            agent_key: Optional filter by agent

        Returns:
            Dictionary with aggregated metrics
        """
        # Calculate start date based on time range
        now = datetime.now(UTC)
        range_map = {
            "1h": timedelta(hours=1),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(hours=24))
        start_date = now - delta

        # Build base filter
        base_filter = RagQueryLog.created_at >= start_date
        if agent_key:
            base_filter = base_filter & (RagQueryLog.agent_key == agent_key)

        # Total queries
        total_result = await self.session.execute(
            select(func.count(RagQueryLog.id)).where(base_filter)
        )
        total_queries = total_result.scalar() or 0

        if total_queries == 0:
            return {
                "time_range": time_range,
                "agent_key": agent_key,
                "total_queries": 0,
                "avg_latency_ms": 0.0,
                "avg_token_count": 0.0,
                "avg_relevance_score": None,
                "positive_feedback_rate": 0.0,
                "negative_feedback_rate": 0.0,
                "queries_without_feedback": 0,
            }

        # Average metrics
        avg_result = await self.session.execute(
            select(
                func.avg(RagQueryLog.latency_ms).label("avg_latency"),
                func.avg(RagQueryLog.token_count).label("avg_tokens"),
                func.avg(RagQueryLog.relevance_score).label("avg_relevance"),
            ).where(base_filter)
        )
        avg_row = avg_result.one()

        # Feedback stats
        positive_result = await self.session.execute(
            select(func.count(RagQueryLog.id)).where(
                base_filter & (RagQueryLog.user_feedback == "positive")
            )
        )
        positive_count = positive_result.scalar() or 0

        negative_result = await self.session.execute(
            select(func.count(RagQueryLog.id)).where(
                base_filter & (RagQueryLog.user_feedback == "negative")
            )
        )
        negative_count = negative_result.scalar() or 0

        no_feedback_result = await self.session.execute(
            select(func.count(RagQueryLog.id)).where(
                base_filter & (RagQueryLog.user_feedback.is_(None))
            )
        )
        no_feedback_count = no_feedback_result.scalar() or 0

        total_with_feedback = positive_count + negative_count

        return {
            "time_range": time_range,
            "agent_key": agent_key,
            "total_queries": total_queries,
            "avg_latency_ms": float(avg_row.avg_latency or 0),
            "avg_token_count": float(avg_row.avg_tokens or 0),
            "avg_relevance_score": (
                float(avg_row.avg_relevance) if avg_row.avg_relevance else None
            ),
            "positive_feedback_rate": (
                positive_count / total_with_feedback if total_with_feedback > 0 else 0.0
            ),
            "negative_feedback_rate": (
                negative_count / total_with_feedback if total_with_feedback > 0 else 0.0
            ),
            "queries_without_feedback": no_feedback_count,
        }

    async def get_queries_by_time(
        self,
        time_range: str = "24h",
        granularity: str = "hour",
        agent_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get query counts grouped by time for charts.

        Args:
            time_range: Time range ('24h', '7d', '30d')
            granularity: Grouping ('hour', 'day')
            agent_key: Optional filter by agent

        Returns:
            List of {time_bucket, count} dictionaries
        """
        now = datetime.now(UTC)
        range_map = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(hours=24))
        start_date = now - delta

        # Determine truncation
        trunc = "hour" if granularity == "hour" else "day"

        # Build query with date_trunc
        sql = text(
            f"""
            SELECT
                date_trunc(:trunc, created_at) as time_bucket,
                COUNT(*) as count
            FROM core.rag_query_logs
            WHERE created_at >= :start_date
            {"AND agent_key = :agent_key" if agent_key else ""}
            GROUP BY time_bucket
            ORDER BY time_bucket
            """
        )

        params: dict[str, Any] = {
            "trunc": trunc,
            "start_date": start_date,
        }
        if agent_key:
            params["agent_key"] = agent_key

        result = await self.session.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "time_bucket": row.time_bucket.isoformat() if row.time_bucket else None,
                "count": row.count,
            }
            for row in rows
        ]

    async def get_top_agents(
        self,
        time_range: str = "24h",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get top agents by query count.

        Args:
            time_range: Time range ('24h', '7d', '30d')
            limit: Maximum agents to return

        Returns:
            List of {agent_key, count, avg_latency} dictionaries
        """
        now = datetime.now(UTC)
        range_map = {
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
        }
        delta = range_map.get(time_range, timedelta(hours=24))
        start_date = now - delta

        sql = text(
            """
            SELECT
                COALESCE(agent_key, 'unknown') as agent_key,
                COUNT(*) as count,
                AVG(latency_ms) as avg_latency
            FROM core.rag_query_logs
            WHERE created_at >= :start_date
            GROUP BY agent_key
            ORDER BY count DESC
            LIMIT :limit
            """
        )

        result = await self.session.execute(
            sql, {"start_date": start_date, "limit": limit}
        )
        rows = result.fetchall()

        return [
            {
                "agent_key": row.agent_key,
                "count": row.count,
                "avg_latency_ms": float(row.avg_latency or 0),
            }
            for row in rows
        ]


__all__ = ["RagQueryLogRepository"]
