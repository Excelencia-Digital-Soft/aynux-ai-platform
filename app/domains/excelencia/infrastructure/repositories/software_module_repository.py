"""
Software Module Repository Implementation.

Repository for SoftwareModule entity following Repository Pattern.
Supports CRUD operations and RAG integration.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import SoftwareModule

logger = logging.getLogger(__name__)


class SoftwareModuleRepository:
    """
    Software Module Repository implementation.

    Single Responsibility: Data access for SoftwareModule entity only.
    Supports async operations for FastAPI compatibility.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with async database session.

        Args:
            db: AsyncSession from SQLAlchemy
        """
        self.db = db

    async def find_by_id(self, module_id: UUID) -> SoftwareModule | None:
        """
        Find module by ID.

        Args:
            module_id: Module UUID

        Returns:
            SoftwareModule or None if not found
        """
        try:
            result = await self.db.execute(
                select(SoftwareModule).where(SoftwareModule.id == module_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error finding module by ID {module_id}: {e}")
            return None

    async def find_by_code(self, code: str) -> SoftwareModule | None:
        """
        Find module by code (e.g., "HC-001").

        Args:
            code: Module code

        Returns:
            SoftwareModule or None if not found
        """
        try:
            result = await self.db.execute(
                select(SoftwareModule).where(SoftwareModule.code == code)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error finding module by code {code}: {e}")
            return None

    async def find_all(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
        organization_id: UUID | None = None,
    ) -> list[SoftwareModule]:
        """
        Find all modules with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Only return active modules
            organization_id: Filter by organization (multi-tenant)

        Returns:
            List of SoftwareModule
        """
        try:
            query = select(SoftwareModule)

            conditions = []
            if active_only:
                conditions.append(SoftwareModule.active == True)
            if organization_id:
                conditions.append(
                    or_(
                        SoftwareModule.organization_id == organization_id,
                        SoftwareModule.organization_id.is_(None),  # Include global modules
                    )
                )

            if conditions:
                query = query.where(and_(*conditions))

            query = query.order_by(SoftwareModule.code).offset(skip).limit(limit)

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error finding all modules: {e}")
            return []

    async def find_by_category(
        self,
        category: str,
        active_only: bool = True,
    ) -> list[SoftwareModule]:
        """
        Find modules by category.

        Args:
            category: Module category (healthcare, hospitality, etc.)
            active_only: Only return active modules

        Returns:
            List of SoftwareModule
        """
        try:
            query = select(SoftwareModule).where(SoftwareModule.category == category)

            if active_only:
                query = query.where(SoftwareModule.active == True)

            query = query.order_by(SoftwareModule.code)

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error finding modules by category {category}: {e}")
            return []

    async def search(
        self,
        query_text: str,
        limit: int = 20,
        active_only: bool = True,
    ) -> list[SoftwareModule]:
        """
        Search modules by name or description.

        Args:
            query_text: Search text
            limit: Maximum results
            active_only: Only return active modules

        Returns:
            List of matching SoftwareModule
        """
        try:
            search_pattern = f"%{query_text}%"
            query = select(SoftwareModule).where(
                or_(
                    SoftwareModule.name.ilike(search_pattern),
                    SoftwareModule.description.ilike(search_pattern),
                )
            )

            if active_only:
                query = query.where(SoftwareModule.active == True)

            query = query.order_by(SoftwareModule.name).limit(limit)

            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error searching modules: {e}")
            return []

    async def create(self, module: SoftwareModule) -> SoftwareModule:
        """
        Create a new module.

        Args:
            module: SoftwareModule to create

        Returns:
            Created SoftwareModule with ID
        """
        try:
            self.db.add(module)
            await self.db.commit()
            await self.db.refresh(module)
            logger.info(f"Created module: {module.code}")
            return module
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating module: {e}")
            raise

    async def update(self, module: SoftwareModule) -> SoftwareModule:
        """
        Update an existing module.

        Args:
            module: SoftwareModule with updated fields

        Returns:
            Updated SoftwareModule
        """
        try:
            module.updated_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(module)
            logger.info(f"Updated module: {module.code}")
            return module
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating module: {e}")
            raise

    async def delete(self, module_id: UUID, soft_delete: bool = True) -> bool:
        """
        Delete a module (soft delete by default).

        Args:
            module_id: Module UUID
            soft_delete: If True, set active=False instead of deleting

        Returns:
            True if deleted, False otherwise
        """
        try:
            module = await self.find_by_id(module_id)
            if not module:
                return False

            if soft_delete:
                module.active = False  # type: ignore[assignment]
                module.updated_at = datetime.now(UTC)
                await self.db.commit()
            else:
                await self.db.delete(module)
                await self.db.commit()

            logger.info(f"Deleted module: {module_id} (soft={soft_delete})")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting module {module_id}: {e}")
            return False

    async def count(self, active_only: bool = True) -> int:
        """
        Count total modules.

        Args:
            active_only: Only count active modules

        Returns:
            Total count
        """
        try:
            query = select(func.count(SoftwareModule.id))
            if active_only:
                query = query.where(SoftwareModule.active == True)

            result = await self.db.execute(query)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting modules: {e}")
            return 0

    async def update_embedding(
        self,
        module_id: UUID,
        embedding: list[float],
    ) -> bool:
        """
        Update module embedding for RAG.

        Args:
            module_id: Module UUID
            embedding: 768-dimensional embedding vector

        Returns:
            True if updated, False otherwise
        """
        try:
            await self.db.execute(
                update(SoftwareModule)
                .where(SoftwareModule.id == module_id)
                .values(
                    embedding=embedding,
                    embedding_updated_at=datetime.now(UTC),
                )
            )
            await self.db.commit()
            logger.info(f"Updated embedding for module: {module_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating embedding for module {module_id}: {e}")
            return False

    async def update_knowledge_sync(
        self,
        module_id: UUID,
        knowledge_doc_id: UUID,
    ) -> bool:
        """
        Update module's RAG knowledge sync status.

        Args:
            module_id: Module UUID
            knowledge_doc_id: CompanyKnowledge document ID

        Returns:
            True if updated, False otherwise
        """
        try:
            await self.db.execute(
                update(SoftwareModule)
                .where(SoftwareModule.id == module_id)
                .values(
                    knowledge_doc_id=knowledge_doc_id,
                    knowledge_synced_at=datetime.now(UTC),
                )
            )
            await self.db.commit()
            logger.info(f"Updated knowledge sync for module: {module_id}")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating knowledge sync for module {module_id}: {e}")
            return False

    async def get_all_as_dict(self, active_only: bool = True) -> dict[str, dict[str, Any]]:
        """
        Get all modules as dictionary (legacy format for ExcelenciaNode).

        Args:
            active_only: Only include active modules

        Returns:
            Dict of code -> module_data (legacy format)
        """
        modules = await self.find_all(active_only=active_only, limit=1000)
        return {str(module.code): module.to_dict() for module in modules}
