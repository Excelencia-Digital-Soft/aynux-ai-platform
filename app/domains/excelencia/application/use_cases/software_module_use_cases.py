"""
Software Module Use Cases.

CRUD operations for software modules with RAG synchronization.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.excelencia.infrastructure.repositories import SoftwareModuleRepository
from app.models.db import CompanyKnowledge, SoftwareModule

logger = logging.getLogger(__name__)


# ============================================================================
# DTOs (Data Transfer Objects)
# ============================================================================


class CreateModuleDTO(BaseModel):
    """DTO for creating a new module."""

    code: str = Field(..., min_length=2, max_length=20, description="Module code (e.g., HC-001)")
    name: str = Field(..., min_length=2, max_length=200, description="Module name")
    description: str = Field(..., min_length=10, description="Module description")
    category: str = Field(default="general", description="Module category")
    status: str = Field(default="active", description="Module status")
    features: list[str] = Field(default_factory=list, description="Module features")
    pricing_tier: str = Field(default="standard", description="Pricing tier")
    organization_id: UUID | None = Field(default=None, description="Organization ID (multi-tenant)")


class UpdateModuleDTO(BaseModel):
    """DTO for updating a module."""

    name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    category: str | None = Field(default=None)
    status: str | None = Field(default=None)
    features: list[str] | None = Field(default=None)
    pricing_tier: str | None = Field(default=None)


class ModuleResponseDTO(BaseModel):
    """DTO for module response."""

    id: str
    code: str
    name: str
    description: str
    category: str
    status: str
    features: list[str]
    pricing_tier: str
    active: bool
    created_at: str
    updated_at: str
    knowledge_synced: bool = False

    @classmethod
    def from_entity(cls, module: SoftwareModule) -> "ModuleResponseDTO":
        """Create DTO from SoftwareModule entity."""
        # Cast SQLAlchemy Column values to Python types
        features_list: list[str] = module.features if module.features else []  # type: ignore[assignment]
        return cls(
            id=str(module.id),
            code=str(module.code),
            name=str(module.name),
            description=str(module.description),
            category=str(module.category),
            status=str(module.status),
            features=features_list,
            pricing_tier=str(module.pricing_tier) if module.pricing_tier else "standard",
            active=bool(module.active),
            created_at=module.created_at.isoformat() if module.created_at else "",
            updated_at=module.updated_at.isoformat() if module.updated_at else "",
            knowledge_synced=module.knowledge_doc_id is not None,
        )


# ============================================================================
# Use Cases
# ============================================================================


class ListModulesUseCase:
    """
    Use Case: List all software modules.

    Retrieves modules from database with optional filtering.
    """

    def __init__(self, db: AsyncSession):
        self.repository = SoftwareModuleRepository(db)

    async def execute(
        self,
        category: str | None = None,
        status: str | None = None,
        search: str | None = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModuleResponseDTO]:
        """
        List modules with optional filters.

        Args:
            category: Filter by category
            status: Filter by status
            search: Search in name/description
            active_only: Only return active modules
            skip: Pagination offset
            limit: Pagination limit

        Returns:
            List of ModuleResponseDTO
        """
        try:
            if search:
                modules = await self.repository.search(search, limit=limit, active_only=active_only)
            elif category:
                modules = await self.repository.find_by_category(category, active_only=active_only)
            else:
                modules = await self.repository.find_all(
                    skip=skip, limit=limit, active_only=active_only
                )

            # Apply status filter if provided
            if status:
                modules = [m for m in modules if m.status == status]

            return [ModuleResponseDTO.from_entity(m) for m in modules]
        except Exception as e:
            logger.error(f"Error listing modules: {e}")
            raise


class GetModuleUseCase:
    """
    Use Case: Get a single module by ID or code.
    """

    def __init__(self, db: AsyncSession):
        self.repository = SoftwareModuleRepository(db)

    async def execute(
        self,
        module_id: UUID | None = None,
        code: str | None = None,
    ) -> ModuleResponseDTO | None:
        """
        Get module by ID or code.

        Args:
            module_id: Module UUID
            code: Module code (e.g., "HC-001")

        Returns:
            ModuleResponseDTO or None if not found
        """
        try:
            if module_id:
                module = await self.repository.find_by_id(module_id)
            elif code:
                module = await self.repository.find_by_code(code)
            else:
                return None

            return ModuleResponseDTO.from_entity(module) if module else None
        except Exception as e:
            logger.error(f"Error getting module: {e}")
            raise


class CreateModuleUseCase:
    """
    Use Case: Create a new software module.

    Creates module in database and optionally syncs to RAG.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SoftwareModuleRepository(db)

    async def execute(
        self,
        dto: CreateModuleDTO,
        sync_to_rag: bool = True,
    ) -> ModuleResponseDTO:
        """
        Create a new module.

        Args:
            dto: CreateModuleDTO with module data
            sync_to_rag: Whether to sync to company_knowledge

        Returns:
            Created ModuleResponseDTO

        Raises:
            ValueError: If module code already exists
        """
        try:
            # Check if code already exists
            existing = await self.repository.find_by_code(dto.code)
            if existing:
                raise ValueError(f"Module with code '{dto.code}' already exists")

            # Create module entity
            module = SoftwareModule(
                code=dto.code,
                name=dto.name,
                description=dto.description,
                category=dto.category,
                status=dto.status,
                features=dto.features,
                pricing_tier=dto.pricing_tier,
                organization_id=dto.organization_id,
                active=True,
            )

            # Save to database
            module = await self.repository.create(module)

            # Sync to RAG if requested
            if sync_to_rag:
                await self._sync_to_knowledge_base(module)

            logger.info(f"Created module: {module.code}")
            return ModuleResponseDTO.from_entity(module)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error creating module: {e}")
            raise

    async def _sync_to_knowledge_base(self, module: SoftwareModule) -> None:
        """Sync module to company_knowledge for RAG."""
        try:
            from app.integrations.vector_stores.knowledge_embedding_service import (
                KnowledgeEmbeddingService,
            )

            # Generate content for RAG
            content = module.to_rag_content()

            # Create CompanyKnowledge document
            knowledge_doc = CompanyKnowledge(
                title=f"Módulo: {module.name}",
                content=content,
                document_type="software_catalog",
                category=module.category,
                tags=module.features or [],
                active=True,
                meta_data={
                    "module_code": module.code,
                    "module_id": str(module.id),
                    "status": module.status,
                },
            )

            # Generate embedding using KnowledgeEmbeddingService
            embedding_service = KnowledgeEmbeddingService()
            embedding_vector = await embedding_service.generate_embedding(content)
            knowledge_doc.embedding = embedding_vector  # type: ignore[assignment]

            # Save to database
            self.db.add(knowledge_doc)
            await self.db.commit()
            await self.db.refresh(knowledge_doc)

            # Update module with knowledge doc reference (cast UUIDs for pyright)
            from uuid import UUID as UUIDType

            module_uuid = UUIDType(str(module.id))
            doc_uuid = UUIDType(str(knowledge_doc.id))
            await self.repository.update_knowledge_sync(module_uuid, doc_uuid)

            logger.info(f"Synced module {module.code} to knowledge base: {knowledge_doc.id}")
        except Exception as e:
            logger.error(f"Error syncing module to knowledge base: {e}")
            raise  # Re-raise to allow proper error handling


class UpdateModuleUseCase:
    """
    Use Case: Update an existing software module.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SoftwareModuleRepository(db)

    async def execute(
        self,
        module_id: UUID,
        dto: UpdateModuleDTO,
        sync_to_rag: bool = True,
    ) -> ModuleResponseDTO:
        """
        Update an existing module.

        Args:
            module_id: Module UUID
            dto: UpdateModuleDTO with fields to update
            sync_to_rag: Whether to sync changes to RAG

        Returns:
            Updated ModuleResponseDTO

        Raises:
            ValueError: If module not found
        """
        try:
            module = await self.repository.find_by_id(module_id)
            if not module:
                raise ValueError(f"Module with ID '{module_id}' not found")

            # Update fields (type: ignore for SQLAlchemy ORM)
            if dto.name is not None:
                module.name = dto.name  # type: ignore[assignment]
            if dto.description is not None:
                module.description = dto.description  # type: ignore[assignment]
            if dto.category is not None:
                module.category = dto.category  # type: ignore[assignment]
            if dto.status is not None:
                module.status = dto.status  # type: ignore[assignment]
            if dto.features is not None:
                module.features = dto.features  # type: ignore[assignment]
            if dto.pricing_tier is not None:
                module.pricing_tier = dto.pricing_tier  # type: ignore[assignment]

            # Save changes
            module = await self.repository.update(module)

            # Sync to RAG if requested
            if sync_to_rag:
                await self._sync_to_knowledge_base(module)

            logger.info(f"Updated module: {module.code}")
            return ModuleResponseDTO.from_entity(module)
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating module: {e}")
            raise

    async def _sync_to_knowledge_base(self, module: SoftwareModule) -> None:
        """Sync module changes to company_knowledge."""
        try:
            from sqlalchemy import update

            from app.integrations.vector_stores.knowledge_embedding_service import (
                KnowledgeEmbeddingService,
            )

            content = module.to_rag_content()

            if module.knowledge_doc_id:
                # Update existing document
                embedding_service = KnowledgeEmbeddingService()
                embedding_vector = await embedding_service.generate_embedding(content)

                await self.db.execute(
                    update(CompanyKnowledge)
                    .where(CompanyKnowledge.id == module.knowledge_doc_id)
                    .values(
                        title=f"Módulo: {module.name}",
                        content=content,
                        category=module.category,
                        tags=module.features or [],
                        embedding=embedding_vector,
                        updated_at=datetime.now(UTC),
                        meta_data={
                            "module_code": module.code,
                            "module_id": str(module.id),
                            "status": module.status,
                        },
                    )
                )
                await self.db.commit()
                logger.info(f"Updated knowledge doc for module {module.code}")
            else:
                # Create new document
                await CreateModuleUseCase(self.db)._sync_to_knowledge_base(module)
        except Exception as e:
            logger.error(f"Error syncing module to knowledge base: {e}")


class DeleteModuleUseCase:
    """
    Use Case: Delete a software module (soft delete).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SoftwareModuleRepository(db)

    async def execute(
        self,
        module_id: UUID,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete a module.

        Args:
            module_id: Module UUID
            hard_delete: If True, permanently delete

        Returns:
            True if deleted successfully
        """
        try:
            module = await self.repository.find_by_id(module_id)
            if not module:
                return False

            # Deactivate knowledge doc if exists
            if module.knowledge_doc_id:
                from sqlalchemy import update

                await self.db.execute(
                    update(CompanyKnowledge)
                    .where(CompanyKnowledge.id == module.knowledge_doc_id)
                    .values(active=False, updated_at=datetime.now(UTC))
                )
                await self.db.commit()

            # Delete module
            return await self.repository.delete(module_id, soft_delete=not hard_delete)
        except Exception as e:
            logger.error(f"Error deleting module: {e}")
            raise


class GetModulesForChatbotUseCase:
    """
    Use Case: Get modules in legacy format for chatbot (ExcelenciaNode).

    Returns dict format compatible with _FALLBACK_MODULES.
    """

    def __init__(self, db: AsyncSession):
        self.repository = SoftwareModuleRepository(db)

    async def execute(self) -> dict[str, dict[str, Any]]:
        """
        Get all active modules as dictionary.

        Returns:
            Dict of code -> {name, description, features, target}
        """
        try:
            return await self.repository.get_all_as_dict(active_only=True)
        except Exception as e:
            logger.error(f"Error getting modules for chatbot: {e}")
            return {}


class SyncAllModulesToRagUseCase:
    """
    Use Case: Sync all modules to RAG (company_knowledge).

    Useful for initial migration or re-sync.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = SoftwareModuleRepository(db)

    async def execute(self) -> dict[str, Any]:
        """
        Sync all modules to knowledge base.

        Returns:
            Summary of sync operation
        """
        try:
            modules = await self.repository.find_all(active_only=True)
            synced = 0
            failed = 0

            for module in modules:
                try:
                    await CreateModuleUseCase(self.db)._sync_to_knowledge_base(module)
                    synced += 1
                except Exception as e:
                    logger.error(f"Failed to sync module {module.code}: {e}")
                    failed += 1

            return {
                "total": len(modules),
                "synced": synced,
                "failed": failed,
            }
        except Exception as e:
            logger.error(f"Error syncing all modules to RAG: {e}")
            raise
