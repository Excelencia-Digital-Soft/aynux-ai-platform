"""
Knowledge Repository - CRUD and Statistics Operations.

This repository handles all CRUD and statistical operations for the company_knowledge table.
Search operations are handled by KnowledgeSearchRepository.

Follows Single Responsibility Principle by focusing only on data persistence and statistics.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.knowledge_base import CompanyKnowledge

from ._helpers import KnowledgeFilterBuilder

logger = logging.getLogger(__name__)


class KnowledgeRepository:
    """
    Repository for CompanyKnowledge CRUD and statistics operations.

    Provides async methods for:
    - Basic CRUD operations (create, read, update, delete)
    - Soft delete functionality
    - Document statistics and counting
    - Filtering by type, category, tags

    For search operations, use KnowledgeSearchRepository.
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

    async def create(self, knowledge_data: dict[str, Any]) -> CompanyKnowledge:
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
            await self.db.flush()
            await self.db.refresh(knowledge)
            return knowledge
        except Exception as e:
            logger.error(f"Error creating knowledge document: {e}")
            raise

    async def get_by_id(self, knowledge_id: UUID) -> CompanyKnowledge | None:
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
        document_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CompanyKnowledge]:
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

            filters = KnowledgeFilterBuilder.build_base_filters(
                document_type=document_type,
                category=category,
                tags=tags,
                active_only=active_only,
            )

            if filters:
                stmt = stmt.where(and_(*filters))

            stmt = stmt.order_by(CompanyKnowledge.sort_order, CompanyKnowledge.created_at.desc())
            stmt = stmt.offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting knowledge documents: {e}")
            raise

    async def update(self, knowledge_id: UUID, update_data: dict[str, Any]) -> CompanyKnowledge | None:
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
                update(CompanyKnowledge)
                .where(CompanyKnowledge.id == knowledge_id)
                .values(**update_data)
                .returning(CompanyKnowledge)
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

    async def soft_delete(self, knowledge_id: UUID) -> CompanyKnowledge | None:
        """
        Soft delete a knowledge document (set active=False).

        Args:
            knowledge_id: UUID of the document to deactivate

        Returns:
            Updated CompanyKnowledge instance or None if not found
        """
        return await self.update(knowledge_id, {"active": False})

    # ============================================================================
    # Statistics and Utility Operations
    # ============================================================================

    async def count_documents(
        self,
        document_type: str | None = None,
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

            filters = KnowledgeFilterBuilder.build_base_filters(
                document_type=document_type,
                active_only=active_only,
            )

            if filters:
                stmt = stmt.where(and_(*filters))

            result = await self.db.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting knowledge documents: {e}")
            raise

    async def get_documents_without_embeddings(self, active_only: bool = True) -> list[CompanyKnowledge]:
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
                stmt = stmt.where(CompanyKnowledge.active)

            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting documents without embeddings: {e}")
            raise

    async def count_by_document_type(self, active_only: bool = False) -> dict[str, int]:
        """
        Count documents grouped by document_type.

        Args:
            active_only: Only count active documents

        Returns:
            Dictionary mapping document_type to count
        """
        try:
            stmt = select(
                CompanyKnowledge.document_type,
                func.count().label("count"),
            ).group_by(CompanyKnowledge.document_type)

            if active_only:
                stmt = stmt.where(CompanyKnowledge.active)

            result = await self.db.execute(stmt)
            counts: dict[str, int] = {
                str(row.document_type): int(row.count) for row in result.all()
            }
            return counts
        except Exception as e:
            logger.error(f"Error counting documents by type: {e}")
            raise
