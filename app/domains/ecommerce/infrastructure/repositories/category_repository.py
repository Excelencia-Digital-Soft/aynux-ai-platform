"""
Category Repository Implementation

SQLAlchemy implementation of ICategoryRepository.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.ecommerce.application.ports import ICategoryRepository
from app.models.db.catalog import Category as CategoryModel
from app.models.db.catalog import Subcategory as SubcategoryModel

logger = logging.getLogger(__name__)


class SQLAlchemyCategoryRepository(ICategoryRepository):
    """
    SQLAlchemy implementation of category repository.

    Handles all category data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_all(self) -> list[dict]:
        """Get all categories."""
        result = await self.session.execute(
            select(CategoryModel)
            .options(selectinload(CategoryModel.subcategories))
            .where(CategoryModel.active == True)
            .order_by(CategoryModel.sort_order, CategoryModel.name)
        )
        models = result.scalars().all()
        return [self._category_to_dict(m) for m in models]

    async def get_by_id(self, category_id: int) -> dict | None:
        """Get category by ID."""
        try:
            # Try to convert to UUID if it's a string representation
            if isinstance(category_id, str):
                cat_uuid = uuid.UUID(category_id)
            else:
                # If it's an integer, we need to find by external_id or name
                result = await self.session.execute(
                    select(CategoryModel)
                    .options(selectinload(CategoryModel.subcategories))
                    .where(CategoryModel.external_id == str(category_id))
                )
                model = result.scalar_one_or_none()
                return self._category_to_dict(model) if model else None

            result = await self.session.execute(
                select(CategoryModel)
                .options(selectinload(CategoryModel.subcategories))
                .where(CategoryModel.id == cat_uuid)
            )
            model = result.scalar_one_or_none()
            return self._category_to_dict(model) if model else None
        except (ValueError, TypeError):
            # Try by external_id
            result = await self.session.execute(
                select(CategoryModel)
                .options(selectinload(CategoryModel.subcategories))
                .where(CategoryModel.external_id == str(category_id))
            )
            model = result.scalar_one_or_none()
            return self._category_to_dict(model) if model else None
        except Exception as e:
            logger.error(f"Error getting category by ID {category_id}: {e}")
            raise

    async def get_children(self, parent_id: int) -> list[dict]:
        """Get child categories (subcategories)."""
        try:
            # Try as UUID
            if isinstance(parent_id, str):
                parent_uuid = uuid.UUID(parent_id)
            else:
                # Find category by external_id first
                result = await self.session.execute(
                    select(CategoryModel).where(CategoryModel.external_id == str(parent_id))
                )
                parent = result.scalar_one_or_none()
                if not parent:
                    return []
                parent_uuid = parent.id

            result = await self.session.execute(
                select(SubcategoryModel)
                .where(
                    SubcategoryModel.category_id == parent_uuid,
                    SubcategoryModel.active == True,
                )
            )
            models = result.scalars().all()
            return [self._subcategory_to_dict(m) for m in models]
        except (ValueError, TypeError):
            # Try by external_id
            result = await self.session.execute(
                select(CategoryModel).where(CategoryModel.external_id == str(parent_id))
            )
            parent = result.scalar_one_or_none()
            if not parent:
                return []

            result = await self.session.execute(
                select(SubcategoryModel).where(
                    SubcategoryModel.category_id == parent.id,
                    SubcategoryModel.active == True,
                )
            )
            models = result.scalars().all()
            return [self._subcategory_to_dict(m) for m in models]
        except Exception as e:
            logger.error(f"Error getting children for category {parent_id}: {e}")
            raise

    # Additional useful methods

    async def get_by_name(self, name: str) -> dict | None:
        """Get category by name."""
        result = await self.session.execute(
            select(CategoryModel)
            .options(selectinload(CategoryModel.subcategories))
            .where(CategoryModel.name == name)
        )
        model = result.scalar_one_or_none()
        return self._category_to_dict(model) if model else None

    async def get_active(self) -> list[dict]:
        """Get all active categories."""
        return await self.get_all()

    async def get_with_products(self) -> list[dict]:
        """Get categories that have products."""
        result = await self.session.execute(
            select(CategoryModel)
            .options(selectinload(CategoryModel.subcategories))
            .where(CategoryModel.active == True)
            .order_by(CategoryModel.sort_order, CategoryModel.name)
        )
        models = result.scalars().all()
        # Filter categories with products would require a join
        return [self._category_to_dict(m) for m in models]

    async def count(self) -> int:
        """Get total category count."""
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count()).select_from(CategoryModel)
        )
        return result.scalar_one()

    # Mapping methods

    def _category_to_dict(self, model: CategoryModel) -> dict:
        """Convert category model to dictionary."""
        return {
            "id": str(model.id),
            "name": model.name,
            "display_name": model.display_name,
            "description": model.description,
            "active": model.active,
            "sort_order": model.sort_order,
            "external_id": model.external_id,
            "subcategories": [
                self._subcategory_to_dict(sub)
                for sub in (model.subcategories or [])
                if sub.active
            ],
            "meta_data": model.meta_data,
        }

    def _subcategory_to_dict(self, model: SubcategoryModel) -> dict:
        """Convert subcategory model to dictionary."""
        return {
            "id": str(model.id),
            "name": model.name,
            "display_name": model.display_name,
            "description": model.description,
            "category_id": str(model.category_id),
            "active": model.active,
        }
