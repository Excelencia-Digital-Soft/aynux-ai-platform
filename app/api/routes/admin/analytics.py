# ============================================================================
# SCOPE: GLOBAL
# Description: Analytics endpoints for embedding statistics and management.
#              Provides aggregated metrics for company and agent knowledge bases.
# Tenant-Aware: No - Global scope
# ============================================================================
"""
Analytics API Endpoints for Embedding Management.

Provides endpoints for monitoring embedding coverage, identifying documents
without embeddings, and tracking embedding statistics across knowledge bases.
"""

import logging
from enum import Enum
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.models.analytics_schemas import (
    AgentKnowledgeStats,
    DocumentTypeCount,
    EmbeddingStatsResponse,
    LatencyDistribution,
    MissingEmbeddingDocument,
    MissingEmbeddingsResponse,
    RagMetricsResponse,
    RagQueryLogResponse,
    RagQueryLogsListResponse,
    SourceStats,
    TimeSeriesPoint,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Embedding Analytics"],
    responses={
        500: {"description": "Internal server error"},
    },
)


class SourceFilter(str, Enum):
    """Filter for knowledge source."""

    ALL = "all"
    COMPANY = "company"
    AGENT = "agent"


# ============================================================================
# Embedding Statistics Endpoint
# ============================================================================


@router.get(
    "/embeddings/stats",
    response_model=EmbeddingStatsResponse,
    summary="Get embedding statistics",
    description="Retrieve statistics about embedding coverage across knowledge bases",
)
async def get_embedding_stats(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    source: Annotated[
        SourceFilter,
        Query(description="Filter by knowledge source: all, company, or agent"),
    ] = SourceFilter.ALL,
    agent_key: Annotated[
        Optional[str],
        Query(description="Filter by specific agent key (only for source=agent)"),
    ] = None,
) -> EmbeddingStatsResponse:
    """
    Get comprehensive embedding statistics.

    Returns:
    - Total documents and embedding coverage
    - Breakdown by source (company_knowledge, agent_knowledge)
    - Per-agent statistics for agent knowledge
    - Embedding model information

    Query Parameters:
    - source: Filter by 'all', 'company', or 'agent'
    - agent_key: Filter by specific agent (only when source=agent)
    """
    try:
        company_stats = None
        agent_stats = None
        total_docs = 0
        total_with_embedding = 0
        total_without_embedding = 0

        # Get company knowledge stats if requested
        if source in (SourceFilter.ALL, SourceFilter.COMPANY):
            company_stats = await _get_company_knowledge_stats(db)
            total_docs += company_stats.total
            total_with_embedding += company_stats.with_embedding
            total_without_embedding += company_stats.without_embedding

        # Get agent knowledge stats if requested
        if source in (SourceFilter.ALL, SourceFilter.AGENT):
            agent_stats = await _get_agent_knowledge_stats(db, agent_key)
            total_docs += agent_stats.total
            total_with_embedding += agent_stats.with_embedding
            total_without_embedding += agent_stats.without_embedding

        # Build embedding models count
        embedding_models: dict[str, int] = {}
        if total_with_embedding > 0:
            embedding_models["nomic-embed-text"] = total_with_embedding

        return EmbeddingStatsResponse(
            total_documents=total_docs,
            with_embedding=total_with_embedding,
            without_embedding=total_without_embedding,
            embedding_models=embedding_models,
            avg_embedding_size=768.0,  # nomic-embed-text uses 768 dimensions
            last_sync_at=None,  # TODO: Track last sync timestamp
            company_knowledge=company_stats if source != SourceFilter.AGENT else None,
            agent_knowledge=agent_stats if source != SourceFilter.COMPANY else None,
        )

    except Exception as e:
        logger.error(f"Error getting embedding stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve embedding statistics",
        ) from e


async def _get_company_knowledge_stats(db: AsyncSession) -> SourceStats:
    """Get embedding statistics for company knowledge."""
    query = text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding,
            SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as without_embedding
        FROM core.company_knowledge
        WHERE active = true
    """)

    result = await db.execute(query)
    row = result.fetchone()

    if row is None:
        return SourceStats(total=0, with_embedding=0, without_embedding=0)

    return SourceStats(
        total=row.total or 0,
        with_embedding=row.with_embedding or 0,
        without_embedding=row.without_embedding or 0,
    )


async def _get_agent_knowledge_stats(
    db: AsyncSession,
    agent_key: Optional[str] = None,
) -> AgentKnowledgeStats:
    """Get embedding statistics for agent knowledge, with per-agent breakdown."""
    # Base query for totals
    if agent_key:
        query = text("""
            SELECT
                agent_key,
                COUNT(*) as total,
                SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding,
                SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as without_embedding
            FROM core.agent_knowledge
            WHERE active = true AND agent_key = :agent_key
            GROUP BY agent_key
        """)
        result = await db.execute(query, {"agent_key": agent_key})
    else:
        query = text("""
            SELECT
                agent_key,
                COUNT(*) as total,
                SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as with_embedding,
                SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as without_embedding
            FROM core.agent_knowledge
            WHERE active = true
            GROUP BY agent_key
        """)
        result = await db.execute(query)

    rows = result.fetchall()

    # Build per-agent breakdown
    by_agent: dict[str, SourceStats] = {}
    total = 0
    with_embedding = 0
    without_embedding = 0

    for row in rows:
        agent_stats = SourceStats(
            total=row.total or 0,
            with_embedding=row.with_embedding or 0,
            without_embedding=row.without_embedding or 0,
        )
        by_agent[row.agent_key] = agent_stats
        total += agent_stats.total
        with_embedding += agent_stats.with_embedding
        without_embedding += agent_stats.without_embedding

    return AgentKnowledgeStats(
        total=total,
        with_embedding=with_embedding,
        without_embedding=without_embedding,
        by_agent=by_agent,
    )


# ============================================================================
# Missing Embeddings Endpoint
# ============================================================================


@router.get(
    "/embeddings/missing",
    response_model=MissingEmbeddingsResponse,
    summary="Get documents without embeddings",
    description="Retrieve paginated list of documents that are missing embeddings",
)
async def get_documents_without_embedding(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    source: Annotated[
        SourceFilter,
        Query(description="Filter by knowledge source: all, company, or agent"),
    ] = SourceFilter.ALL,
    agent_key: Annotated[
        Optional[str],
        Query(description="Filter by specific agent key (only for source=agent)"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number (1-indexed)")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Items per page")
    ] = 25,
) -> MissingEmbeddingsResponse:
    """
    Get documents that are missing embeddings.

    Returns a paginated list of documents that need embedding regeneration,
    with information about which source they come from.

    Query Parameters:
    - source: Filter by 'all', 'company', or 'agent'
    - agent_key: Filter by specific agent (only when source=agent)
    - page: Page number (starts at 1)
    - page_size: Number of items per page (max 100)
    """
    try:
        documents: list[MissingEmbeddingDocument] = []
        total = 0
        offset = (page - 1) * page_size

        # Build and execute query based on source filter
        if source == SourceFilter.ALL:
            # Combined query from both tables
            docs, total = await _get_missing_embeddings_combined(db, page_size, offset, agent_key)
            documents = docs
        elif source == SourceFilter.COMPANY:
            docs, total = await _get_missing_embeddings_company(db, page_size, offset)
            documents = docs
        else:  # AGENT
            docs, total = await _get_missing_embeddings_agent(db, page_size, offset, agent_key)
            documents = docs

        return MissingEmbeddingsResponse(
            documents=documents,
            total=total,
        )

    except Exception as e:
        logger.error(f"Error getting documents without embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents without embeddings",
        ) from e


async def _get_missing_embeddings_company(
    db: AsyncSession,
    limit: int,
    offset: int,
) -> tuple[list[MissingEmbeddingDocument], int]:
    """Get company knowledge documents without embeddings."""
    # Count query
    count_query = text("""
        SELECT COUNT(*) as total
        FROM core.company_knowledge
        WHERE active = true AND embedding IS NULL
    """)
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Data query
    data_query = text("""
        SELECT id::text, title, document_type
        FROM core.company_knowledge
        WHERE active = true AND embedding IS NULL
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)
    result = await db.execute(data_query, {"limit": limit, "offset": offset})
    rows = result.fetchall()

    documents = [
        MissingEmbeddingDocument(
            id=row.id,
            title=row.title,
            document_type=row.document_type,
            source="company_knowledge",
            agent_key=None,
        )
        for row in rows
    ]

    return documents, total


async def _get_missing_embeddings_agent(
    db: AsyncSession,
    limit: int,
    offset: int,
    agent_key: Optional[str] = None,
) -> tuple[list[MissingEmbeddingDocument], int]:
    """Get agent knowledge documents without embeddings."""
    # Count query
    if agent_key:
        count_query = text("""
            SELECT COUNT(*) as total
            FROM core.agent_knowledge
            WHERE active = true AND embedding IS NULL AND agent_key = :agent_key
        """)
        count_result = await db.execute(count_query, {"agent_key": agent_key})
    else:
        count_query = text("""
            SELECT COUNT(*) as total
            FROM core.agent_knowledge
            WHERE active = true AND embedding IS NULL
        """)
        count_result = await db.execute(count_query)

    total = count_result.scalar() or 0

    # Data query
    if agent_key:
        data_query = text("""
            SELECT id::text, title, document_type, agent_key
            FROM core.agent_knowledge
            WHERE active = true AND embedding IS NULL AND agent_key = :agent_key
            ORDER BY agent_key, created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await db.execute(data_query, {"agent_key": agent_key, "limit": limit, "offset": offset})
    else:
        data_query = text("""
            SELECT id::text, title, document_type, agent_key
            FROM core.agent_knowledge
            WHERE active = true AND embedding IS NULL
            ORDER BY agent_key, created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await db.execute(data_query, {"limit": limit, "offset": offset})

    rows = result.fetchall()

    documents = [
        MissingEmbeddingDocument(
            id=row.id,
            title=row.title,
            document_type=row.document_type,
            source="agent_knowledge",
            agent_key=row.agent_key,
        )
        for row in rows
    ]

    return documents, total


async def _get_missing_embeddings_combined(
    db: AsyncSession,
    limit: int,
    offset: int,
    agent_key: Optional[str] = None,
) -> tuple[list[MissingEmbeddingDocument], int]:
    """Get documents without embeddings from both sources."""
    # Build the combined count query
    if agent_key:
        # Only include agent knowledge filtered by agent_key
        count_query = text("""
            SELECT (
                (SELECT COUNT(*) FROM core.company_knowledge WHERE active = true AND embedding IS NULL)
                +
                (SELECT COUNT(*) FROM core.agent_knowledge WHERE active = true AND \
                    embedding IS NULL AND agent_key = :agent_key)
            ) as total
        """)
        count_result = await db.execute(count_query, {"agent_key": agent_key})
    else:
        count_query = text("""
            SELECT (
                (SELECT COUNT(*) FROM core.company_knowledge WHERE active = true AND embedding IS NULL)
                +
                (SELECT COUNT(*) FROM core.agent_knowledge WHERE active = true AND embedding IS NULL)
            ) as total
        """)
        count_result = await db.execute(count_query)

    total = count_result.scalar() or 0

    # Combined data query with UNION ALL
    # Note: Cast document_type to text and NULL to VARCHAR for UNION compatibility
    if agent_key:
        data_query = text("""
            SELECT id::text, title, document_type::text, 'company_knowledge' as source, NULL::varchar as agent_key
            FROM core.company_knowledge
            WHERE active = true AND embedding IS NULL

            UNION ALL

            SELECT id::text, title, document_type::text, 'agent_knowledge' as source, agent_key
            FROM core.agent_knowledge
            WHERE active = true AND embedding IS NULL AND agent_key = :agent_key

            ORDER BY source, title
            LIMIT :limit OFFSET :offset
        """)
        result = await db.execute(data_query, {"agent_key": agent_key, "limit": limit, "offset": offset})
    else:
        data_query = text("""
            SELECT id::text, title, document_type::text, 'company_knowledge' as source, NULL::varchar as agent_key
            FROM core.company_knowledge
            WHERE active = true AND embedding IS NULL

            UNION ALL

            SELECT id::text, title, document_type::text, 'agent_knowledge' as source, agent_key
            FROM core.agent_knowledge
            WHERE active = true AND embedding IS NULL

            ORDER BY source, title
            LIMIT :limit OFFSET :offset
        """)
        result = await db.execute(data_query, {"limit": limit, "offset": offset})

    rows = result.fetchall()

    documents = [
        MissingEmbeddingDocument(
            id=row.id,
            title=row.title,
            document_type=row.document_type,
            source=row.source,
            agent_key=row.agent_key,
        )
        for row in rows
    ]

    return documents, total


# ============================================================================
# RAG Analytics Endpoints
# ============================================================================


@router.get(
    "/rag/metrics",
    response_model=RagMetricsResponse,
    summary="Get RAG metrics",
    description="Retrieve aggregated RAG analytics metrics for the dashboard",
)
async def get_rag_metrics(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    days: Annotated[int, Query(ge=1, le=365, description="Number of days to include")] = 30,
) -> RagMetricsResponse:
    """
    Get comprehensive RAG metrics for the analytics dashboard.

    Returns:
    - Total queries and averages (latency, tokens, relevance)
    - Feedback rate
    - Queries grouped by day and hour
    - Top document types used as context
    - Latency distribution
    """
    try:
        start_dt = datetime.utcnow() - timedelta(days=days)

        # Main aggregation query
        main_query = text("""
            SELECT
                COUNT(*)::int as total_queries,
                COALESCE(AVG(latency_ms), 0)::float as avg_latency_ms,
                COALESCE(AVG(token_count), 0)::float as avg_token_count,
                COALESCE(AVG(relevance_score), 0)::float as avg_relevance_score,
                COALESCE(
                    SUM(CASE WHEN user_feedback = 'positive' THEN 1 ELSE 0 END)::float /
                    NULLIF(SUM(CASE WHEN user_feedback IS NOT NULL THEN 1 ELSE 0 END), 0),
                    0
                )::float as positive_feedback_rate
            FROM core.rag_query_logs
            WHERE created_at >= :start_dt
        """)

        result = await db.execute(main_query, {"start_dt": start_dt})
        row = result.fetchone()

        # Default values if no data
        total_queries = 0
        avg_latency_ms = 0.0
        avg_token_count = 0.0
        avg_relevance_score = 0.0
        positive_feedback_rate = 0.0

        if row:
            total_queries = row.total_queries or 0
            avg_latency_ms = row.avg_latency_ms or 0.0
            avg_token_count = row.avg_token_count or 0.0
            avg_relevance_score = row.avg_relevance_score or 0.0
            positive_feedback_rate = row.positive_feedback_rate or 0.0

        # Queries by day
        by_day_query = text("""
            SELECT
                TO_CHAR(created_at, 'YYYY-MM-DD') as day,
                COUNT(*)::int as count
            FROM core.rag_query_logs
            WHERE created_at >= :start_dt
            GROUP BY TO_CHAR(created_at, 'YYYY-MM-DD')
            ORDER BY day
        """)
        by_day_result = await db.execute(by_day_query, {"start_dt": start_dt})
        queries_by_day = {r.day: r.count for r in by_day_result.fetchall()}

        # Queries by hour (0-23)
        by_hour_query = text("""
            SELECT
                EXTRACT(HOUR FROM created_at)::int as hour,
                COUNT(*)::int as count
            FROM core.rag_query_logs
            WHERE created_at >= :start_dt
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
        """)
        by_hour_result = await db.execute(by_hour_query, {"start_dt": start_dt})
        queries_by_hour = {str(int(r.hour)): r.count for r in by_hour_result.fetchall()}

        # Top document types (from context_used JSONB)
        doc_types_query = text("""
            SELECT
                doc_type as type,
                COUNT(*)::int as count
            FROM core.rag_query_logs,
                 LATERAL jsonb_array_elements_text(context_used) as doc_type
            WHERE created_at >= :start_dt
            GROUP BY doc_type
            ORDER BY count DESC
            LIMIT 10
        """)
        doc_types_result = await db.execute(doc_types_query, {"start_dt": start_dt})
        top_document_types = [
            DocumentTypeCount(type=r.type, count=r.count)
            for r in doc_types_result.fetchall()
        ]

        # Latency distribution
        latency_query = text("""
            SELECT
                CASE
                    WHEN latency_ms < 100 THEN '0-100ms'
                    WHEN latency_ms < 500 THEN '100-500ms'
                    WHEN latency_ms < 1000 THEN '500-1000ms'
                    ELSE '1000ms+'
                END as range,
                COUNT(*)::int as count
            FROM core.rag_query_logs
            WHERE created_at >= :start_dt
            GROUP BY
                CASE
                    WHEN latency_ms < 100 THEN '0-100ms'
                    WHEN latency_ms < 500 THEN '100-500ms'
                    WHEN latency_ms < 1000 THEN '500-1000ms'
                    ELSE '1000ms+'
                END
            ORDER BY MIN(latency_ms)
        """)
        latency_result = await db.execute(latency_query, {"start_dt": start_dt})
        latency_distribution = [
            LatencyDistribution(range=r.range, count=r.count)
            for r in latency_result.fetchall()
        ]

        return RagMetricsResponse(
            total_queries=total_queries,
            avg_latency_ms=avg_latency_ms,
            avg_token_count=avg_token_count,
            avg_relevance_score=avg_relevance_score,
            positive_feedback_rate=positive_feedback_rate,
            queries_by_day=queries_by_day,
            queries_by_hour=queries_by_hour,
            top_document_types=top_document_types,
            latency_distribution=latency_distribution,
        )

    except Exception as e:
        logger.error(f"Error getting RAG metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve RAG metrics",
        ) from e


@router.get(
    "/rag/timeseries",
    response_model=list[TimeSeriesPoint],
    summary="Get RAG time series data",
    description="Retrieve time series data for a specific RAG metric",
)
async def get_rag_timeseries(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    metric: Annotated[
        Literal["latency", "token_count", "relevance"],
        Query(description="Metric to retrieve"),
    ],
    granularity: Annotated[
        Literal["hour", "day", "week"],
        Query(description="Time granularity"),
    ] = "day",
    days: Annotated[int, Query(ge=1, le=365, description="Number of days")] = 30,
) -> list[TimeSeriesPoint]:
    """
    Get time series data for a specific RAG metric.

    Parameters:
    - metric: 'latency', 'token_count', or 'relevance'
    - granularity: 'hour', 'day', or 'week'
    - days: Number of days to include
    """
    try:
        start_dt = datetime.utcnow() - timedelta(days=days)

        # Map metric to SQL column
        metric_column = {
            "latency": "AVG(latency_ms)",
            "token_count": "AVG(token_count)",
            "relevance": "AVG(relevance_score)",
        }.get(metric, "AVG(latency_ms)")

        # Map granularity to SQL date_trunc
        granularity_sql = {
            "hour": "date_trunc('hour', created_at)",
            "day": "date_trunc('day', created_at)",
            "week": "date_trunc('week', created_at)",
        }.get(granularity, "date_trunc('day', created_at)")

        query = text(f"""
            SELECT
                {granularity_sql} as timestamp,
                {metric_column}::float as value
            FROM core.rag_query_logs
            WHERE created_at >= :start_dt
            GROUP BY {granularity_sql}
            ORDER BY timestamp
        """)

        result = await db.execute(query, {"start_dt": start_dt})
        rows = result.fetchall()

        return [
            TimeSeriesPoint(
                timestamp=row.timestamp.isoformat() if row.timestamp else "",
                value=round(row.value or 0, 2),
            )
            for row in rows
        ]

    except Exception as e:
        logger.error(f"Error getting RAG time series: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve RAG time series",
        ) from e


@router.get(
    "/rag/queries",
    response_model=RagQueryLogsListResponse,
    summary="Get RAG query logs",
    description="Retrieve paginated RAG query logs",
)
async def get_rag_query_logs(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 25,
    start_date: Annotated[Optional[str], Query(description="Start date (ISO format)")] = None,
    end_date: Annotated[Optional[str], Query(description="End date (ISO format)")] = None,
) -> RagQueryLogsListResponse:
    """
    Get paginated RAG query logs.

    Parameters:
    - page: Page number (starts at 1)
    - page_size: Number of items per page (max 100)
    - start_date: Optional start date filter (ISO format)
    - end_date: Optional end date filter (ISO format)
    """
    try:
        offset = (page - 1) * page_size

        # Build date filter
        date_filter = ""
        params: dict = {"limit": page_size, "offset": offset}

        if start_date:
            date_filter += " AND created_at >= :start_date"
            params["start_date"] = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        if end_date:
            date_filter += " AND created_at <= :end_date"
            params["end_date"] = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

        # Count total
        count_query = text(f"""
            SELECT COUNT(*)::int as total
            FROM core.rag_query_logs
            WHERE 1=1 {date_filter}
        """)
        count_result = await db.execute(count_query, params)
        total = count_result.scalar() or 0

        # Get logs
        logs_query = text(f"""
            SELECT
                id::text,
                query,
                context_used,
                response,
                token_count,
                latency_ms,
                relevance_score,
                user_feedback,
                created_at
            FROM core.rag_query_logs
            WHERE 1=1 {date_filter}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)

        result = await db.execute(logs_query, params)
        rows = result.fetchall()

        logs = [
            RagQueryLogResponse(
                id=row.id,
                query=row.query,
                context_used=row.context_used if isinstance(row.context_used, list) else [],
                response=row.response,
                token_count=row.token_count or 0,
                latency_ms=row.latency_ms or 0,
                relevance_score=float(row.relevance_score) if row.relevance_score else None,
                user_feedback=row.user_feedback,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return RagQueryLogsListResponse(logs=logs, total=total)

    except Exception as e:
        logger.error(f"Error getting RAG query logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve RAG query logs",
        ) from e
