"""
Module Repository Implementation

SQLAlchemy implementation of module repository for Excelencia ERP.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.excelencia.application.ports import IModuleRepository
from app.domains.excelencia.domain.entities.module import (
    ERPModule,
    ModuleCategory,
    ModuleStatus,
)
from app.domains.excelencia.infrastructure.persistence.sqlalchemy.models import (
    ErpModuleModel,
)

logger = logging.getLogger(__name__)


class SQLAlchemyModuleRepository(IModuleRepository):
    """
    SQLAlchemy implementation of IModuleRepository.

    Handles all module data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_all(self) -> list[ERPModule]:
        """Get all modules."""
        result = await self.session.execute(select(ErpModuleModel))
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_id(self, module_id: str) -> ERPModule | None:
        """Get module by ID."""
        # ID in entity is string like 'mod-001', but DB uses integer
        # Try to extract numeric part or use code field
        result = await self.session.execute(
            select(ErpModuleModel).where(ErpModuleModel.code == module_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            # Try parsing as integer ID
            try:
                int_id = int(module_id.replace("mod-", "")) if module_id.startswith("mod-") else int(module_id)
                result = await self.session.execute(
                    select(ErpModuleModel).where(ErpModuleModel.id == int_id)
                )
                model = result.scalar_one_or_none()
            except ValueError:
                return None

        return self._to_entity(model) if model else None

    async def get_by_code(self, code: str) -> ERPModule | None:
        """Get module by code."""
        result = await self.session.execute(
            select(ErpModuleModel).where(ErpModuleModel.code == code)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_category(self, category: ModuleCategory) -> list[ERPModule]:
        """Get modules by category."""
        result = await self.session.execute(
            select(ErpModuleModel).where(ErpModuleModel.category == category.value)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def save(self, module: ERPModule) -> ERPModule:
        """Save or update a module."""
        # Try to find existing by code
        result = await self.session.execute(
            select(ErpModuleModel).where(ErpModuleModel.code == module.code)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            self._update_model(existing, module)
            model = existing
        else:
            # Create new
            model = self._to_model(module)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        logger.info(f"Saved module: {model.code}")
        return self._to_entity(model)

    async def delete(self, module_id: str) -> bool:
        """Delete a module."""
        module = await self.get_by_id(module_id)
        if not module:
            return False

        result = await self.session.execute(
            select(ErpModuleModel).where(ErpModuleModel.code == module.code)
        )
        model = result.scalar_one_or_none()

        if model:
            await self.session.delete(model)
            await self.session.commit()
            logger.info(f"Deleted module: {module_id}")
            return True
        return False

    async def count(self) -> int:
        """Get total module count."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).select_from(ErpModuleModel)
        )
        return result.scalar_one()

    async def exists(self, code: str) -> bool:
        """Check if module with code exists."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).where(ErpModuleModel.code == code)
        )
        return result.scalar_one() > 0

    # Mapping methods

    def _to_entity(self, model: ErpModuleModel) -> ERPModule:
        """Convert model to entity."""
        # Cast SQLAlchemy Column types to Python types
        model_id = cast(int, model.id)
        code = cast(str, model.code)
        name = cast(str, model.name)
        description = cast(str | None, model.description) or ""
        category_str = cast(str, model.category)
        status_str = cast(str, model.status)
        features = cast(list[Any] | None, model.features) or []
        pricing_tier = cast(str | None, model.pricing_tier) or "standard"
        created_at = cast(datetime, model.created_at)
        updated_at = cast(datetime, model.updated_at)

        return ERPModule(
            id=f"mod-{model_id:03d}",
            code=code,
            name=name,
            description=description,
            category=ModuleCategory(category_str),
            status=ModuleStatus(status_str),
            features=features,
            pricing_tier=pricing_tier,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_model(self, module: ERPModule) -> ErpModuleModel:
        """Convert entity to model."""
        return ErpModuleModel(
            code=module.code,
            name=module.name,
            description=module.description,
            category=module.category.value,
            status=module.status.value,
            features=module.features,
            pricing_tier=module.pricing_tier,
        )

    def _update_model(self, model: ErpModuleModel, module: ERPModule) -> None:
        """Update model from entity."""
        setattr(model, "name", module.name)
        setattr(model, "description", module.description)
        setattr(model, "category", module.category.value)
        setattr(model, "status", module.status.value)
        setattr(model, "features", module.features)
        setattr(model, "pricing_tier", module.pricing_tier)


# Keep backward compatibility alias
InMemoryModuleRepository = SQLAlchemyModuleRepository
