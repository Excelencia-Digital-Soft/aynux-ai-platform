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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.models.analytics_schemas import (
    AgentKnowledgeStats,
    EmbeddingStatsResponse,
    MissingEmbeddingDocument,
    MissingEmbeddingsResponse,
    SourceStats,
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
    source: SourceFilter = Query(
        SourceFilter.ALL,
        description="Filter by knowledge source: all, company, or agent",
    ),
    agent_key: Optional[str] = Query(
        None,
        description="Filter by specific agent key (only for source=agent)",
    ),
    db: AsyncSession = Depends(get_async_db),
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
    source: SourceFilter = Query(
        SourceFilter.ALL,
        description="Filter by knowledge source: all, company, or agent",
    ),
    agent_key: Optional[str] = Query(
        None,
        description="Filter by specific agent key (only for source=agent)",
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_db),
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
