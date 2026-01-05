"""
Knowledge Search Repository - Vector and Text Search Operations.

This repository handles all search operations for the company_knowledge table,
including vector similarity search and full-text search.

Separated from KnowledgeRepository to follow Single Responsibility Principle.
"""

import logging
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.knowledge_base import CompanyKnowledge

from ._helpers import KnowledgeFilterBuilder, KnowledgeResultFormatter

logger = logging.getLogger(__name__)


class KnowledgeSearchRepository:
    """
    Repository for knowledge search operations.

    Provides async methods for:
    - Vector similarity search (semantic search)
    - Full-text search (PostgreSQL ts_rank)

    Uses pgvector for vector operations with CAST() syntax for asyncpg compatibility.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with async database session.

        Args:
            db: Async SQLAlchemy session from FastAPI dependency injection
        """
        self.db = db

    async def search_by_vector(
        self,
        query_embedding: list[float],
        similarity_threshold: float = 0.7,
        max_results: int = 5,
        document_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge documents by vector similarity.

        Args:
            query_embedding: Query vector (768 dimensions for nomic-embed-text)
            similarity_threshold: Minimum similarity score (0.0-1.0)
            max_results: Maximum number of results to return
            document_type: Optional filter by document type
            category: Optional filter by category
            tags: Optional filter by tags
            active_only: Only search active documents

        Returns:
            List of dictionaries with document data and similarity scores
        """
        try:
            stmt = select(
                CompanyKnowledge,
                (1 - CompanyKnowledge.embedding.cosine_distance(query_embedding)).label("similarity_score"),
            )

            filters = KnowledgeFilterBuilder.build_base_filters(
                document_type=document_type,
                category=category,
                tags=tags,
                active_only=active_only,
            )
            KnowledgeFilterBuilder.add_embedding_requirement(filters)

            # Add similarity threshold filter using CAST() for asyncpg compatibility
            filters.append(
                text("1 - (embedding <=> CAST(:query_embedding AS vector)) >= :similarity_threshold").bindparams(
                    similarity_threshold=similarity_threshold
                )
            )

            stmt = stmt.where(and_(*filters))
            stmt = stmt.order_by(text("similarity_score DESC"), CompanyKnowledge.sort_order)
            stmt = stmt.limit(max_results)
            stmt = stmt.params(query_embedding=query_embedding)

            result = await self.db.execute(stmt)
            rows = result.all()

            return [KnowledgeResultFormatter.format_vector_result(row) for row in rows]
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise

    async def search_by_text(
        self,
        query_text: str,
        max_results: int = 10,
        document_type: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge documents by full-text search.

        Args:
            query_text: Search query text
            max_results: Maximum number of results to return
            document_type: Optional filter by document type
            active_only: Only search active documents

        Returns:
            List of dictionaries with document data and text rank scores
        """
        try:
            stmt = select(
                CompanyKnowledge,
                func.ts_rank(CompanyKnowledge.search_vector, func.plainto_tsquery("spanish", query_text)).label(
                    "text_rank"
                ),
            )

            # Full-text search match is always required
            filters: list[Any] = [
                CompanyKnowledge.search_vector.op("@@")(func.plainto_tsquery("spanish", query_text))
            ]

            if active_only:
                filters.append(CompanyKnowledge.active)
            if document_type:
                filters.append(CompanyKnowledge.document_type == document_type)

            stmt = stmt.where(and_(*filters))
            stmt = stmt.order_by(text("text_rank DESC"))
            stmt = stmt.limit(max_results)

            result = await self.db.execute(stmt)
            rows = result.all()

            return [KnowledgeResultFormatter.format_text_result(row) for row in rows]
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            raise
