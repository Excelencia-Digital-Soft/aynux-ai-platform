"""
Promotion Repository Implementation

SQLAlchemy implementation of IPromotionRepository.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.ecommerce.application.ports import IPromotionRepository
from app.models.db.promotions import Promotion as PromotionModel

logger = logging.getLogger(__name__)


class SQLAlchemyPromotionRepository(IPromotionRepository):
    """
    SQLAlchemy implementation of promotion repository.

    Handles all promotion data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_active(self) -> list[dict]:
        """Get active promotions."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(PromotionModel)
            .options(selectinload(PromotionModel.products))
            .where(
                PromotionModel.active == True,
                PromotionModel.valid_from <= now,
                PromotionModel.valid_until >= now,
            )
            .order_by(PromotionModel.valid_until.asc())
        )
        models = result.scalars().all()
        return [self._to_dict(m) for m in models if self._is_valid(m)]

    async def get_by_product(self, product_id: int) -> list[dict]:
        """Get promotions for a product."""
        try:
            # Try to convert to UUID
            if isinstance(product_id, str):
                product_uuid = uuid.UUID(product_id)
            else:
                # If integer, cannot directly query - would need product lookup
                logger.warning(f"Product ID {product_id} is not a UUID, skipping promotion lookup")
                return []

            now = datetime.now(timezone.utc)
            result = await self.session.execute(
                select(PromotionModel)
                .options(selectinload(PromotionModel.products))
                .where(
                    PromotionModel.active == True,
                    PromotionModel.valid_from <= now,
                    PromotionModel.valid_until >= now,
                )
            )
            models = result.scalars().all()

            # Filter promotions that include this product
            promotions = []
            for promo in models:
                if self._is_valid(promo):
                    product_ids = [str(p.id) for p in promo.products]
                    if str(product_uuid) in product_ids:
                        promotions.append(self._to_dict(promo))

            return promotions
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid product_id format: {product_id}, error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting promotions for product {product_id}: {e}")
            raise

    async def get_by_category(self, category_id: int) -> list[dict]:
        """Get promotions for a category."""
        try:
            # Try to convert to UUID
            if isinstance(category_id, str):
                category_uuid_str = category_id
            else:
                category_uuid_str = str(category_id)

            now = datetime.now(timezone.utc)
            result = await self.session.execute(
                select(PromotionModel)
                .options(selectinload(PromotionModel.products))
                .where(
                    PromotionModel.active == True,
                    PromotionModel.valid_from <= now,
                    PromotionModel.valid_until >= now,
                )
            )
            models = result.scalars().all()

            # Filter promotions that apply to this category
            promotions = []
            for promo in models:
                if self._is_valid(promo):
                    applicable_categories = promo.applicable_categories or []
                    if category_uuid_str in applicable_categories:
                        promotions.append(self._to_dict(promo))

            return promotions
        except Exception as e:
            logger.error(f"Error getting promotions for category {category_id}: {e}")
            raise

    # Additional useful methods

    async def get_by_id(self, promotion_id: str) -> dict | None:
        """Get promotion by ID."""
        try:
            promo_uuid = uuid.UUID(promotion_id)
            result = await self.session.execute(
                select(PromotionModel)
                .options(selectinload(PromotionModel.products))
                .where(PromotionModel.id == promo_uuid)
            )
            model = result.scalar_one_or_none()
            return self._to_dict(model) if model else None
        except ValueError:
            logger.warning(f"Invalid promotion_id format: {promotion_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting promotion by ID {promotion_id}: {e}")
            raise

    async def get_by_code(self, promo_code: str) -> dict | None:
        """Get promotion by promo code."""
        result = await self.session.execute(
            select(PromotionModel)
            .options(selectinload(PromotionModel.products))
            .where(PromotionModel.promo_code == promo_code)
        )
        model = result.scalar_one_or_none()
        return self._to_dict(model) if model else None

    async def validate_code(self, promo_code: str) -> dict | None:
        """Validate a promo code and return promotion if valid."""
        promo = await self.get_by_code(promo_code)
        if promo and promo.get("is_valid"):
            return promo
        return None

    async def get_all(self, include_inactive: bool = False) -> list[dict]:
        """Get all promotions."""
        query = select(PromotionModel).options(selectinload(PromotionModel.products))

        if not include_inactive:
            query = query.where(PromotionModel.active == True)

        result = await self.session.execute(query.order_by(PromotionModel.valid_until.desc()))
        models = result.scalars().all()
        return [self._to_dict(m) for m in models]

    async def count_active(self) -> int:
        """Get count of active promotions."""
        from sqlalchemy import func

        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(func.count()).where(
                PromotionModel.active == True,
                PromotionModel.valid_from <= now,
                PromotionModel.valid_until >= now,
            )
        )
        return result.scalar_one()

    # Helper methods

    def _is_valid(self, model: PromotionModel) -> bool:
        """Check if promotion is currently valid."""
        if model.active is not True:
            return False

        now = datetime.now(timezone.utc)
        valid_from = cast(datetime | None, model.valid_from)
        valid_until = cast(datetime | None, model.valid_until)
        max_uses = cast(int | None, model.max_uses)
        current_uses = cast(int | None, model.current_uses)

        if valid_from is not None and valid_from > now:
            return False
        if valid_until is not None and valid_until < now:
            return False
        if max_uses is not None and current_uses is not None and current_uses >= max_uses:
            return False

        return True

    def _to_dict(self, model: PromotionModel) -> dict:
        """Convert promotion model to dictionary."""
        return {
            "id": str(model.id),
            "name": model.name,
            "description": model.description,
            "discount_percentage": model.discount_percentage,
            "discount_amount": model.discount_amount,
            "promo_code": model.promo_code,
            "valid_from": model.valid_from.isoformat() if model.valid_from is not None else None,
            "valid_until": model.valid_until.isoformat() if model.valid_until is not None else None,
            "max_uses": model.max_uses,
            "current_uses": model.current_uses,
            "min_purchase_amount": model.min_purchase_amount,
            "applicable_categories": model.applicable_categories,
            "active": model.active,
            "is_valid": self._is_valid(model),
            "product_count": len(model.products) if model.products else 0,
            "created_at": model.created_at.isoformat() if model.created_at is not None else None,
        }
