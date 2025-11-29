"""
Product Query Builder.

Single Responsibility: Build SQLAlchemy queries for product searches.
"""

import logging
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.database.async_db import get_async_db_context
from app.models.db import Brand, Category, Product

from .formatter import ProductFormatter

logger = logging.getLogger(__name__)


class ProductQueryBuilder:
    """Builds and executes product queries."""

    def __init__(self, formatter: ProductFormatter | None = None):
        self._formatter = formatter or ProductFormatter()

    async def get_all(
        self,
        include_inactive: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch all products from the database."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )

                if not include_inactive:
                    query = query.where(Product.active.is_(True))

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error fetching all products: {str(e)}")
            return []

    async def search(
        self,
        search_term: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search products by name, description, or model."""
        try:
            async with get_async_db_context() as db:
                search_pattern = f"%{search_term}%"

                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(
                        and_(
                            Product.active.is_(True),
                            or_(
                                Product.name.ilike(search_pattern),
                                Product.description.ilike(search_pattern),
                                Product.model.ilike(search_pattern),
                                Category.name.ilike(search_pattern),
                                Category.display_name.ilike(search_pattern),
                                Brand.name.ilike(search_pattern),
                            ),
                        )
                    )
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []

    async def get_by_category(
        self,
        category_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get products by category name."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(
                        and_(
                            Product.active.is_(True),
                            or_(
                                func.lower(Category.name) == category_name.lower(),
                                func.lower(Category.display_name)
                                == category_name.lower(),
                            ),
                        )
                    )
                    .order_by(Product.price.asc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error fetching products by category: {str(e)}")
            return []

    async def get_by_brand(
        self,
        brand_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get products by brand name."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id)
                    .where(
                        and_(
                            Product.active.is_(True),
                            func.lower(Brand.name) == brand_name.lower(),
                        )
                    )
                    .order_by(Product.price.asc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error fetching products by brand: {str(e)}")
            return []

    async def get_by_price_range(
        self,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get products within a price range."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(Product.active.is_(True))
                )

                if min_price is not None:
                    query = query.where(Product.price >= min_price)
                if max_price is not None:
                    query = query.where(Product.price <= max_price)

                query = query.order_by(Product.price.asc()).limit(limit)

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error fetching products by price range: {str(e)}")
            return []

    async def get_by_id(self, product_id: int) -> dict[str, Any] | None:
        """Get a specific product by ID."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(Product.id == product_id)
                )

                result = await db.execute(query)
                row = result.first()

                if row:
                    product, category, brand = row
                    return self._formatter.format_product(product, category, brand)

                return None

        except Exception as e:
            logger.error(f"Error fetching product by ID: {str(e)}")
            return None

    async def get_featured(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get featured products."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(
                        and_(Product.active.is_(True), Product.featured.is_(True))
                    )
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error fetching featured products: {str(e)}")
            return []

    async def get_on_sale(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get products on sale."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(
                        and_(Product.active.is_(True), Product.on_sale.is_(True))
                    )
                    .order_by(Product.price.asc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error fetching products on sale: {str(e)}")
            return []

    async def advanced_search(
        self,
        search_term: str | None = None,
        category: str | None = None,
        brand: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        in_stock: bool = True,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Advanced product search with multiple filters."""
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(Product.active.is_(True))
                )

                # Text search
                if search_term:
                    search_pattern = f"%{search_term}%"
                    query = query.where(
                        or_(
                            Product.name.ilike(search_pattern),
                            Product.description.ilike(search_pattern),
                            Product.model.ilike(search_pattern),
                        )
                    )

                # Category filter
                if category:
                    query = query.where(
                        or_(
                            func.lower(Category.name) == category.lower(),
                            func.lower(Category.display_name) == category.lower(),
                        )
                    )

                # Brand filter
                if brand:
                    query = query.where(func.lower(Brand.name) == brand.lower())

                # Price range
                if min_price is not None:
                    query = query.where(Product.price >= min_price)
                if max_price is not None:
                    query = query.where(Product.price <= max_price)

                # Stock filter
                if in_stock:
                    query = query.where(Product.stock > 0)

                query = query.order_by(Product.created_at.desc()).limit(limit)

                result = await db.execute(query)
                rows = result.all()

                return self._formatter.format_products(rows)

        except Exception as e:
            logger.error(f"Error in advanced search: {str(e)}")
            return []
