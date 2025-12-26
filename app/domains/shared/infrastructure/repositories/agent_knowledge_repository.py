"""
Agent Knowledge Repository Implementation

SQLAlchemy implementation for agent-specific knowledge base operations.
Supports semantic search using pgvector and full-text search.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.agent_knowledge import AgentKnowledge

logger = logging.getLogger(__name__)


class AgentKnowledgeRepository:
    """
    Repository for agent-specific knowledge base operations.

    Provides:
    - CRUD operations for agent knowledge documents
    - Semantic search using pgvector embeddings
    - Full-text search using PostgreSQL TSVECTOR
    - Hybrid search combining both approaches
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_agent(
        self,
        agent_key: str,
        active_only: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all knowledge documents for an agent.

        Args:
            agent_key: Agent identifier
            active_only: Only return active documents
            limit: Maximum number of documents to return

        Returns:
            List of document dictionaries
        """
        stmt = select(AgentKnowledge).where(AgentKnowledge.agent_key == agent_key)

        if active_only:
            stmt = stmt.where(AgentKnowledge.active == True)  # noqa: E712

        stmt = stmt.order_by(AgentKnowledge.sort_order, AgentKnowledge.created_at.desc())

        if limit:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [model.to_dict() for model in models]

    async def get_by_id(self, doc_id: uuid.UUID | str) -> dict[str, Any] | None:
        """
        Get a specific document by ID.

        Args:
            doc_id: Document UUID

        Returns:
            Document dictionary or None if not found
        """
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)

        result = await self.session.execute(
            select(AgentKnowledge).where(AgentKnowledge.id == doc_id)
        )
        model = result.scalar_one_or_none()

        return model.to_dict() if model else None

    async def create(
        self,
        agent_key: str,
        title: str,
        content: str,
        document_type: str = "general",
        category: str | None = None,
        tags: list[str] | None = None,
        meta_data: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new knowledge document.

        Args:
            agent_key: Agent identifier
            title: Document title
            content: Document content
            document_type: Type of document
            category: Optional category
            tags: Optional tags
            meta_data: Optional metadata
            embedding: Optional embedding vector (768 dims)

        Returns:
            Created document dictionary
        """
        model = AgentKnowledge(
            agent_key=agent_key,
            title=title,
            content=content,
            document_type=document_type,
            category=category,
            tags=tags or [],
            meta_data=meta_data or {},
            embedding=embedding,
            embedding_updated_at=datetime.now(UTC) if embedding else None,
            active=True,
        )

        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)

        logger.info(f"Created agent knowledge: {agent_key}/{title}")
        return model.to_dict()

    async def update(
        self,
        doc_id: uuid.UUID | str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Update an existing document.

        Args:
            doc_id: Document UUID
            **kwargs: Fields to update

        Returns:
            Updated document dictionary or None if not found
        """
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)

        result = await self.session.execute(
            select(AgentKnowledge).where(AgentKnowledge.id == doc_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Update allowed fields
        allowed_fields = {
            "title",
            "content",
            "document_type",
            "category",
            "tags",
            "meta_data",
            "active",
            "sort_order",
            "embedding",
        }

        for field, value in kwargs.items():
            if field in allowed_fields and hasattr(model, field):
                setattr(model, field, value)

        await self.session.commit()
        await self.session.refresh(model)

        logger.info(f"Updated agent knowledge: {doc_id}")
        return model.to_dict()

    async def delete(self, doc_id: uuid.UUID | str, hard: bool = False) -> bool:
        """
        Delete a document.

        Args:
            doc_id: Document UUID
            hard: If True, permanently delete. If False, soft delete (set active=False)

        Returns:
            True if deleted, False if not found
        """
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)

        if hard:
            result = await self.session.execute(
                delete(AgentKnowledge).where(AgentKnowledge.id == doc_id)
            )
            await self.session.commit()
            return result.rowcount > 0
        else:
            # Soft delete
            result = await self.session.execute(
                select(AgentKnowledge).where(AgentKnowledge.id == doc_id)
            )
            model = result.scalar_one_or_none()
            if model:
                model.active = False
                await self.session.commit()
                return True
            return False

    async def count_by_agent(self, agent_key: str, active_only: bool = True) -> int:
        """
        Count documents for an agent.

        Args:
            agent_key: Agent identifier
            active_only: Only count active documents

        Returns:
            Number of documents
        """
        stmt = select(func.count(AgentKnowledge.id)).where(
            AgentKnowledge.agent_key == agent_key
        )

        if active_only:
            stmt = stmt.where(AgentKnowledge.active == True)  # noqa: E712

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def search_semantic(
        self,
        agent_key: str,
        query_embedding: list[float],
        max_results: int = 5,
        min_similarity: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search documents using semantic similarity (vector search).

        Args:
            agent_key: Agent identifier
            query_embedding: Query embedding vector (768 dims)
            max_results: Maximum results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of documents with similarity scores
        """
        # Convert embedding to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Use raw SQL for vector similarity search
        # pgvector uses <=> for cosine distance, similarity = 1 - distance
        # Note: Use CAST() instead of :: to avoid asyncpg parameter confusion
        sql = text(
            """
            SELECT
                id,
                agent_key,
                title,
                content,
                document_type,
                category,
                tags,
                meta_data,
                active,
                sort_order,
                created_at,
                updated_at,
                1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM core.agent_knowledge
            WHERE agent_key = :agent_key
              AND active = TRUE
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_similarity
            ORDER BY similarity DESC
            LIMIT :limit
            """
        )

        result = await self.session.execute(
            sql,
            {
                "agent_key": agent_key,
                "embedding": embedding_str,
                "min_similarity": min_similarity,
                "limit": max_results,
            },
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "agent_key": row.agent_key,
                "title": row.title,
                "content": row.content,
                "document_type": row.document_type,
                "category": row.category,
                "tags": row.tags or [],
                "meta_data": row.meta_data or {},
                "active": row.active,
                "sort_order": row.sort_order,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "similarity_score": float(row.similarity),
            }
            for row in rows
        ]

    async def search_fulltext(
        self,
        agent_key: str,
        query: str,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search documents using full-text search.

        Args:
            agent_key: Agent identifier
            query: Search query text
            max_results: Maximum results to return

        Returns:
            List of documents with rank scores
        """
        sql = text(
            """
            SELECT
                id,
                agent_key,
                title,
                content,
                document_type,
                category,
                tags,
                meta_data,
                active,
                sort_order,
                created_at,
                updated_at,
                ts_rank(search_vector, plainto_tsquery('spanish', :query)) as rank
            FROM core.agent_knowledge
            WHERE agent_key = :agent_key
              AND active = TRUE
              AND search_vector @@ plainto_tsquery('spanish', :query)
            ORDER BY rank DESC
            LIMIT :limit
            """
        )

        result = await self.session.execute(
            sql,
            {
                "agent_key": agent_key,
                "query": query,
                "limit": max_results,
            },
        )
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "agent_key": row.agent_key,
                "title": row.title,
                "content": row.content,
                "document_type": row.document_type,
                "category": row.category,
                "tags": row.tags or [],
                "meta_data": row.meta_data or {},
                "active": row.active,
                "sort_order": row.sort_order,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "rank_score": float(row.rank),
            }
            for row in rows
        ]

    async def update_embedding(
        self,
        doc_id: uuid.UUID | str,
        embedding: list[float],
    ) -> bool:
        """
        Update the embedding for a document.

        Args:
            doc_id: Document UUID
            embedding: New embedding vector (768 dims)

        Returns:
            True if updated, False if not found
        """
        if isinstance(doc_id, str):
            doc_id = uuid.UUID(doc_id)

        result = await self.session.execute(
            select(AgentKnowledge).where(AgentKnowledge.id == doc_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return False

        model.embedding = embedding
        model.embedding_updated_at = datetime.now(UTC)
        await self.session.commit()

        logger.info(f"Updated embedding for document: {doc_id}")
        return True

    async def get_stats(self, agent_key: str) -> dict[str, Any]:
        """
        Get statistics for an agent's knowledge base.

        Args:
            agent_key: Agent identifier

        Returns:
            Dictionary with statistics
        """
        # Total count
        total = await self.count_by_agent(agent_key, active_only=False)
        active = await self.count_by_agent(agent_key, active_only=True)

        # Count with embeddings
        stmt = select(func.count(AgentKnowledge.id)).where(
            AgentKnowledge.agent_key == agent_key,
            AgentKnowledge.active == True,  # noqa: E712
            AgentKnowledge.embedding != None,  # noqa: E711
        )
        result = await self.session.execute(stmt)
        with_embedding = result.scalar() or 0

        return {
            "agent_key": agent_key,
            "total_documents": total,
            "active_documents": active,
            "with_embedding": with_embedding,
            "embedding_coverage": (with_embedding / active * 100) if active > 0 else 0,
        }


__all__ = ["AgentKnowledgeRepository"]
