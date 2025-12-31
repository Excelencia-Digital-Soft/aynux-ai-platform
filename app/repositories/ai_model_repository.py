# ============================================================================
# SCOPE: GLOBAL
# Description: Repository para persistencia de modelos de IA. Proporciona
#              operaciones CRUD y bulk sobre la tabla ai_models.
# Tenant-Aware: No - modelos son globales.
# ============================================================================
"""
AI Model Repository - Data persistence layer for AIModel entity.

Provides async CRUD operations, filtering, and bulk updates.
Follows Single Responsibility Principle - only handles data persistence.

Usage:
    repository = AIModelRepository(db)
    models = await repository.list(provider="ollama", enabled_only=True)
    model = await repository.get_by_model_id("llama3.2:3b")
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.ai_model import AIModel

logger = logging.getLogger(__name__)


class AIModelRepository:
    """
    Async repository for AIModel persistence.

    Single Responsibility: Data access layer for ai_models table.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with async database session.

        Args:
            db: SQLAlchemy async session
        """
        self._db = db

    # =========================================================================
    # Read Operations
    # =========================================================================

    async def find_all(
        self,
        provider: str | None = None,
        model_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[AIModel]:
        """Find all models with optional filtering.

        Args:
            provider: Filter by provider (e.g., "ollama", "openai")
            model_type: Filter by type ("llm" or "embedding")
            enabled_only: Only return enabled models

        Returns:
            List of AIModel instances ordered by sort_order, display_name
        """
        stmt = select(AIModel)

        if provider:
            stmt = stmt.where(AIModel.provider == provider)
        if model_type:
            stmt = stmt.where(AIModel.model_type == model_type)
        if enabled_only:
            stmt = stmt.where(AIModel.is_enabled == True)  # noqa: E712

        stmt = stmt.order_by(AIModel.sort_order, AIModel.display_name)

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, model_id: UUID) -> AIModel | None:
        """Get model by UUID.

        Args:
            model_id: Model UUID

        Returns:
            AIModel or None if not found
        """
        stmt = select(AIModel).where(AIModel.id == model_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_model_id(self, model_id: str) -> AIModel | None:
        """Get model by provider-specific model ID.

        Args:
            model_id: Provider model ID (e.g., "gpt-4", "llama3.2:3b")

        Returns:
            AIModel or None if not found
        """
        stmt = select(AIModel).where(AIModel.model_id == model_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def exists(self, model_id: str) -> bool:
        """Check if model exists by model_id.

        Args:
            model_id: Provider model ID

        Returns:
            True if exists, False otherwise
        """
        model = await self.get_by_model_id(model_id)
        return model is not None

    # =========================================================================
    # Write Operations
    # =========================================================================

    async def create(self, model: AIModel) -> AIModel:
        """Create a new model.

        Args:
            model: AIModel instance to persist

        Returns:
            Persisted AIModel with generated ID
        """
        self._db.add(model)
        await self._db.commit()
        await self._db.refresh(model)
        return model

    async def update(self, model: AIModel) -> AIModel:
        """Update an existing model.

        Args:
            model: AIModel instance with updated fields

        Returns:
            Updated AIModel
        """
        model.updated_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(model)
        return model

    async def delete(self, model_id: UUID) -> bool:
        """Delete a model by UUID.

        Args:
            model_id: Model UUID to delete

        Returns:
            True if deleted, False if not found
        """
        model = await self.get_by_id(model_id)
        if not model:
            return False

        await self._db.delete(model)
        await self._db.commit()
        return True

    async def save(self, model: AIModel) -> AIModel:
        """Save model (create or update).

        Args:
            model: AIModel to save

        Returns:
            Saved AIModel
        """
        if model.id:
            return await self.update(model)
        return await self.create(model)

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def bulk_update_enabled(
        self,
        model_ids: list[UUID],
        enabled: bool,
    ) -> int:
        """Bulk update enabled status for multiple models.

        Args:
            model_ids: List of model UUIDs
            enabled: New enabled status

        Returns:
            Number of rows updated
        """
        stmt = (
            update(AIModel)
            .where(AIModel.id.in_(model_ids))
            .values(is_enabled=enabled, updated_at=datetime.now(UTC))
        )
        result = await self._db.execute(stmt)
        await self._db.commit()
        return result.rowcount

    async def bulk_update_sort_order(self, orders: list[dict]) -> int:
        """Bulk update sort order for multiple models.

        Args:
            orders: List of {"id": UUID, "sort_order": int}

        Returns:
            Number of rows updated
        """
        updated = 0
        for item in orders:
            model = await self.get_by_id(item["id"])
            if model:
                model.sort_order = item["sort_order"]
                model.updated_at = datetime.now(UTC)
                updated += 1

        await self._db.commit()
        return updated

    async def bulk_create(self, models: list[AIModel]) -> int:
        """Bulk create multiple models.

        Args:
            models: List of AIModel instances

        Returns:
            Number of models created
        """
        for model in models:
            self._db.add(model)
        await self._db.commit()
        return len(models)

    # =========================================================================
    # Query Helpers
    # =========================================================================

    async def count(
        self,
        provider: str | None = None,
        enabled_only: bool = False,
    ) -> int:
        """Count models with optional filtering.

        Args:
            provider: Filter by provider
            enabled_only: Only count enabled models

        Returns:
            Number of matching models
        """
        models = await self.find_all(provider=provider, enabled_only=enabled_only)
        return len(models)

    async def get_enabled_for_select(self, model_type: str = "llm") -> list[dict]:
        """Get enabled models formatted for UI select components.

        Args:
            model_type: Filter by model type

        Returns:
            List of dicts with value/label format
        """
        models = await self.find_all(model_type=model_type, enabled_only=True)
        return [model.to_select_option() for model in models]
