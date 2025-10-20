"""
Knowledge Base Repository - Data Access Layer (Single Responsibility Principle)

This repository handles all database operations for the company_knowledge table.
It follows the Repository Pattern to abstract database access from business logic.

Responsibilities:
- CRUD operations (Create, Read, Update, Delete)
- Vector similarity search
- Full-text search
- Hybrid search (vector + text)
- Filtering and pagination

Does NOT contain business logic (that's in KnowledgeService).
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.knowledge_base import CompanyKnowledge, DOCUMENT_TYPES

logger = logging.getLogger(__name__)


class KnowledgeRepository:
    """
    Repository for CompanyKnowledge data access operations.

    Provides async methods for:
    - Basic CRUD operations
    - Vector similarity search
    - Full-text search
    - Hybrid search combining both
    - Filtering by type, category, tags
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with async database session.

        Args:
            db: Async SQLAlchemy session from FastAPI dependency injection
        """
        self.db = db

    # ============================================================================
    # CRUD Operations
    # ============================================================================

    async def create(self, knowledge_data: Dict[str, Any]) -> CompanyKnowledge:
        """
        Create a new knowledge document.

        Args:
            knowledge_data: Dictionary with document data

        Returns:
            Created CompanyKnowledge instance
        """
        try:
            knowledge = CompanyKnowledge(**knowledge_data)
            self.db.add(knowledge)
            await self.db.flush()  # Flush to get ID without committing
            await self.db.refresh(knowledge)
            return knowledge
        except Exception as e:
            logger.error(f"Error creating knowledge document: {e}")
            raise

    async def get_by_id(self, knowledge_id: UUID) -> Optional[CompanyKnowledge]:
        """
        Get a knowledge document by ID.

        Args:
            knowledge_id: UUID of the document

        Returns:
            CompanyKnowledge instance or None if not found
        """
        try:
            stmt = select(CompanyKnowledge).where(CompanyKnowledge.id == knowledge_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting knowledge document {knowledge_id}: {e}")
            raise

    async def get_all(
        self,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CompanyKnowledge]:
        """
        Get all knowledge documents with optional filtering and pagination.

        Args:
            document_type: Filter by document type
            category: Filter by category
            tags: Filter by tags (documents with ANY of these tags)
            active_only: Only return active documents
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of CompanyKnowledge instances
        """
        try:
            stmt = select(CompanyKnowledge)

            # Build filters
            filters = []
            if active_only:
                filters.append(CompanyKnowledge.active == True)
            if document_type:
                filters.append(CompanyKnowledge.document_type == document_type)
            if category:
                filters.append(CompanyKnowledge.category == category)
            if tags:
                # PostgreSQL array overlap operator
                filters.append(CompanyKnowledge.tags.overlap(tags))

            if filters:
                stmt = stmt.where(and_(*filters))

            # Order by sort_order, then by created_at descending
            stmt = stmt.order_by(CompanyKnowledge.sort_order, CompanyKnowledge.created_at.desc())

            # Pagination
            stmt = stmt.offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting knowledge documents: {e}")
            raise

    async def update(self, knowledge_id: UUID, update_data: Dict[str, Any]) -> Optional[CompanyKnowledge]:
        """
        Update a knowledge document.

        Args:
            knowledge_id: UUID of the document to update
            update_data: Dictionary with fields to update

        Returns:
            Updated CompanyKnowledge instance or None if not found
        """
        try:
            stmt = (
                update(CompanyKnowledge).where(CompanyKnowledge.id == knowledge_id).values(**update_data).returning(CompanyKnowledge)
            )
            result = await self.db.execute(stmt)
            await self.db.flush()
            knowledge = result.scalar_one_or_none()
            if knowledge:
                await self.db.refresh(knowledge)
            return knowledge
        except Exception as e:
            logger.error(f"Error updating knowledge document {knowledge_id}: {e}")
            raise

    async def delete(self, knowledge_id: UUID) -> bool:
        """
        Delete a knowledge document (hard delete).

        Args:
            knowledge_id: UUID of the document to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            stmt = delete(CompanyKnowledge).where(CompanyKnowledge.id == knowledge_id)
            result = await self.db.execute(stmt)
            await self.db.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting knowledge document {knowledge_id}: {e}")
            raise

    async def soft_delete(self, knowledge_id: UUID) -> Optional[CompanyKnowledge]:
        """
        Soft delete a knowledge document (set active=False).

        Args:
            knowledge_id: UUID of the document to deactivate

        Returns:
            Updated CompanyKnowledge instance or None if not found
        """
        return await self.update(knowledge_id, {"active": False})

    # ============================================================================
    # Vector Search Operations
    # ============================================================================

    async def search_by_vector(
        self,
        query_embedding: List[float],
        similarity_threshold: float = 0.7,
        max_results: int = 5,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge documents by vector similarity.

        Args:
            query_embedding: Query vector (1024 dimensions)
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
            # Build base query with similarity calculation
            # Using <=> operator for cosine distance, then converting to similarity (1 - distance)
            stmt = select(
                CompanyKnowledge,
                (1 - CompanyKnowledge.embedding.cosine_distance(query_embedding)).label("similarity_score"),
            )

            # Build filters
            filters = [CompanyKnowledge.embedding.isnot(None)]

            if active_only:
                filters.append(CompanyKnowledge.active == True)
            if document_type:
                filters.append(CompanyKnowledge.document_type == document_type)
            if category:
                filters.append(CompanyKnowledge.category == category)
            if tags:
                filters.append(CompanyKnowledge.tags.overlap(tags))

            # Add similarity threshold filter
            filters.append(text(f"1 - (embedding <=> :query_embedding) >= {similarity_threshold}"))

            stmt = stmt.where(and_(*filters))

            # Order by similarity (highest first), then by sort_order
            stmt = stmt.order_by(text("similarity_score DESC"), CompanyKnowledge.sort_order)

            # Limit results
            stmt = stmt.limit(max_results)

            # Bind parameter
            stmt = stmt.params(query_embedding=query_embedding)

            result = await self.db.execute(stmt)
            rows = result.all()

            # Format results
            return [
                {
                    "id": str(row.CompanyKnowledge.id),
                    "title": row.CompanyKnowledge.title,
                    "content": row.CompanyKnowledge.content,
                    "document_type": row.CompanyKnowledge.document_type,
                    "category": row.CompanyKnowledge.category,
                    "tags": row.CompanyKnowledge.tags,
                    "metadata": row.CompanyKnowledge.meta_data,
                    "similarity_score": float(row.similarity_score),
                    "created_at": row.CompanyKnowledge.created_at.isoformat(),
                    "updated_at": row.CompanyKnowledge.updated_at.isoformat(),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise

    # ============================================================================
    # Text Search Operations
    # ============================================================================

    async def search_by_text(
        self,
        query_text: str,
        max_results: int = 10,
        document_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
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
            # Build full-text search query
            stmt = select(
                CompanyKnowledge,
                func.ts_rank(CompanyKnowledge.search_vector, func.plainto_tsquery("spanish", query_text)).label("text_rank"),
            )

            # Build filters
            filters = [
                CompanyKnowledge.search_vector.op("@@")(func.plainto_tsquery("spanish", query_text))
            ]

            if active_only:
                filters.append(CompanyKnowledge.active == True)
            if document_type:
                filters.append(CompanyKnowledge.document_type == document_type)

            stmt = stmt.where(and_(*filters))

            # Order by text rank (highest first)
            stmt = stmt.order_by(text("text_rank DESC"))

            # Limit results
            stmt = stmt.limit(max_results)

            result = await self.db.execute(stmt)
            rows = result.all()

            # Format results
            return [
                {
                    "id": str(row.CompanyKnowledge.id),
                    "title": row.CompanyKnowledge.title,
                    "content": row.CompanyKnowledge.content,
                    "document_type": row.CompanyKnowledge.document_type,
                    "category": row.CompanyKnowledge.category,
                    "tags": row.CompanyKnowledge.tags,
                    "metadata": row.CompanyKnowledge.meta_data,
                    "text_rank": float(row.text_rank),
                    "created_at": row.CompanyKnowledge.created_at.isoformat(),
                    "updated_at": row.CompanyKnowledge.updated_at.isoformat(),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            raise

    # ============================================================================
    # Hybrid Search Operations
    # ============================================================================

    async def search_hybrid(
        self,
        query_text: str,
        query_embedding: List[float],
        max_results: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        similarity_threshold: float = 0.5,
        document_type: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector similarity and full-text search.

        Args:
            query_text: Search query text
            query_embedding: Query vector (1024 dimensions)
            max_results: Maximum number of results to return
            vector_weight: Weight for vector similarity (0.0-1.0)
            text_weight: Weight for text rank (0.0-1.0)
            similarity_threshold: Minimum vector similarity score
            document_type: Optional filter by document type
            active_only: Only search active documents

        Returns:
            List of dictionaries with document data and combined scores
        """
        try:
            # Calculate combined score: weighted sum of vector similarity and text rank
            vector_similarity = (1 - CompanyKnowledge.embedding.cosine_distance(query_embedding)).label(
                "vector_similarity"
            )
            text_rank = func.ts_rank(CompanyKnowledge.search_vector, func.plainto_tsquery("spanish", query_text)).label(
                "text_rank"
            )
            combined_score = (vector_weight * vector_similarity + text_weight * text_rank).label("combined_score")

            stmt = select(CompanyKnowledge, vector_similarity, text_rank, combined_score)

            # Build filters
            filters = [
                CompanyKnowledge.embedding.isnot(None),
                CompanyKnowledge.search_vector.isnot(None),
                text(f"1 - (embedding <=> :query_embedding) >= {similarity_threshold}"),
            ]

            if active_only:
                filters.append(CompanyKnowledge.active == True)
            if document_type:
                filters.append(CompanyKnowledge.document_type == document_type)

            stmt = stmt.where(and_(*filters))

            # Order by combined score (highest first)
            stmt = stmt.order_by(text("combined_score DESC"))

            # Limit results
            stmt = stmt.limit(max_results)

            # Bind parameter
            stmt = stmt.params(query_embedding=query_embedding)

            result = await self.db.execute(stmt)
            rows = result.all()

            # Format results
            return [
                {
                    "id": str(row.CompanyKnowledge.id),
                    "title": row.CompanyKnowledge.title,
                    "content": row.CompanyKnowledge.content,
                    "document_type": row.CompanyKnowledge.document_type,
                    "category": row.CompanyKnowledge.category,
                    "tags": row.CompanyKnowledge.tags,
                    "metadata": row.CompanyKnowledge.meta_data,
                    "vector_similarity": float(row.vector_similarity),
                    "text_rank": float(row.text_rank),
                    "combined_score": float(row.combined_score),
                    "created_at": row.CompanyKnowledge.created_at.isoformat(),
                    "updated_at": row.CompanyKnowledge.updated_at.isoformat(),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            raise

    # ============================================================================
    # Statistics and Utility Operations
    # ============================================================================

    async def count_documents(
        self,
        document_type: Optional[str] = None,
        active_only: bool = True,
    ) -> int:
        """
        Count knowledge documents with optional filters.

        Args:
            document_type: Optional filter by document type
            active_only: Only count active documents

        Returns:
            Total count of matching documents
        """
        try:
            stmt = select(func.count()).select_from(CompanyKnowledge)

            filters = []
            if active_only:
                filters.append(CompanyKnowledge.active == True)
            if document_type:
                filters.append(CompanyKnowledge.document_type == document_type)

            if filters:
                stmt = stmt.where(and_(*filters))

            result = await self.db.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting knowledge documents: {e}")
            raise

    async def get_documents_without_embeddings(self, active_only: bool = True) -> List[CompanyKnowledge]:
        """
        Get all documents that don't have embeddings yet.

        Args:
            active_only: Only return active documents

        Returns:
            List of CompanyKnowledge instances without embeddings
        """
        try:
            stmt = select(CompanyKnowledge).where(CompanyKnowledge.embedding.is_(None))

            if active_only:
                stmt = stmt.where(CompanyKnowledge.active == True)

            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting documents without embeddings: {e}")
            raise
