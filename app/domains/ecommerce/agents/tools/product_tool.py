"""
Product database query tool for E-commerce domain agents.
"""

import logging
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.database.async_db import get_async_db_context
from app.models.db import Brand, Category, Product

logger = logging.getLogger(__name__)


class ProductTool:
    """Tool for querying product information from the database."""

    def __init__(self):
        self.name = "product_database_tool"
        self.description = "Query product information from the database with advanced filtering and search capabilities"

    async def get_all_products(self, include_inactive: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        """
        Fetch all products from the database.

        Args:
            include_inactive: Whether to include inactive products
            limit: Maximum number of products to return

        Returns:
            List of product dictionaries
        """
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

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error fetching all products: {str(e)}")
            return []

    async def search_products(self, search_term: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Search products by name, description, or model.

        Args:
            search_term: Term to search for
            limit: Maximum number of results

        Returns:
            List of matching products
        """
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

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []

    async def get_products_by_category(self, category_name: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get products by category name.

        Args:
            category_name: Category name to filter by
            limit: Maximum number of results

        Returns:
            List of products in the category
        """
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
                                func.lower(Category.display_name) == category_name.lower(),
                            ),
                        )
                    )
                    .order_by(Product.price.asc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error fetching products by category: {str(e)}")
            return []

    async def get_products_by_brand(self, brand_name: str, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get products by brand name.

        Args:
            brand_name: Brand name to filter by
            limit: Maximum number of results

        Returns:
            List of products from the brand
        """
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id)
                    .where(and_(Product.active.is_(True), func.lower(Brand.name) == brand_name.lower()))
                    .order_by(Product.price.asc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error fetching products by brand: {str(e)}")
            return []

    async def get_products_by_price_range(
        self, min_price: float | None = None, max_price: float | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Get products within a price range.

        Args:
            min_price: Minimum price
            max_price: Maximum price
            limit: Maximum number of results

        Returns:
            List of products in the price range
        """
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

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error fetching products by price range: {str(e)}")
            return []

    async def get_product_by_id(self, product_id: int) -> dict[str, Any] | None:
        """
        Get a specific product by ID.

        Args:
            product_id: Product ID

        Returns:
            Product dictionary or None if not found
        """
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
                    return self._format_product_dict(product, category, brand)

                return None

        except Exception as e:
            logger.error(f"Error fetching product by ID: {str(e)}")
            return None

    async def get_featured_products(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get featured products.

        Args:
            limit: Maximum number of featured products

        Returns:
            List of featured products
        """
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(and_(Product.active.is_(True), Product.featured.is_(True)))
                    .order_by(Product.created_at.desc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error fetching featured products: {str(e)}")
            return []

    async def get_products_on_sale(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get products on sale.

        Args:
            limit: Maximum number of sale products

        Returns:
            List of products on sale
        """
        try:
            async with get_async_db_context() as db:
                query = (
                    select(Product, Category, Brand)
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(and_(Product.active.is_(True), Product.on_sale.is_(True)))
                    .order_by(Product.price.asc())
                    .limit(limit)
                )

                result = await db.execute(query)
                rows = result.all()

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

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
        """
        Advanced product search with multiple filters.

        Args:
            search_term: Text to search for
            category: Category to filter by
            brand: Brand to filter by
            min_price: Minimum price
            max_price: Maximum price
            in_stock: Only include products in stock
            limit: Maximum number of results

        Returns:
            List of filtered products
        """
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

                products = []
                for row in rows:
                    product, category, brand = row
                    products.append(self._format_product_dict(product, category, brand))

                return products

        except Exception as e:
            logger.error(f"Error in advanced search: {str(e)}")
            return []

    def _format_product_dict(self, product, category, brand) -> dict[str, Any]:
        """Format product data into a consistent dictionary."""
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "model": product.model,
            "price": float(product.price),
            "stock": product.stock,
            "active": product.active,
            "featured": product.featured,
            "on_sale": product.on_sale,
            "category": {
                "id": category.id if category else None,
                "name": category.name if category else None,
                "display_name": category.display_name if category else None,
            },
            "brand": {"id": brand.id if brand else None, "name": brand.name if brand else None},
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        }

    async def __call__(self, action: str, **kwargs) -> dict[str, Any]:
        """
        Execute tool action.

        Args:
            action: The action to perform
            **kwargs: Additional parameters for the action

        Returns:
            Dictionary with results or error
        """
        try:
            if action == "get_all":
                include_inactive = kwargs.get("include_inactive", False)
                limit = kwargs.get("limit", 50)
                products = await self.get_all_products(include_inactive, limit)
                return {"success": True, "products": products}

            elif action == "search":
                search_term = kwargs.get("search_term")
                if not search_term:
                    return {"success": False, "error": "search_term is required"}
                limit = kwargs.get("limit", 20)
                products = await self.search_products(search_term, limit)
                return {"success": True, "products": products}

            elif action == "by_category":
                category = kwargs.get("category")
                if not category:
                    return {"success": False, "error": "category is required"}
                limit = kwargs.get("limit", 20)
                products = await self.get_products_by_category(category, limit)
                return {"success": True, "products": products}

            elif action == "by_brand":
                brand = kwargs.get("brand")
                if not brand:
                    return {"success": False, "error": "brand is required"}
                limit = kwargs.get("limit", 20)
                products = await self.get_products_by_brand(brand, limit)
                return {"success": True, "products": products}

            elif action == "by_price_range":
                min_price = kwargs.get("min_price")
                max_price = kwargs.get("max_price")
                limit = kwargs.get("limit", 20)
                products = await self.get_products_by_price_range(min_price, max_price, limit)
                return {"success": True, "products": products}

            elif action == "by_id":
                product_id = kwargs.get("product_id")
                if not product_id:
                    return {"success": False, "error": "product_id is required"}
                product = await self.get_product_by_id(product_id)
                return {"success": True, "product": product}

            elif action == "featured":
                limit = kwargs.get("limit", 10)
                products = await self.get_featured_products(limit)
                return {"success": True, "products": products}

            elif action == "on_sale":
                limit = kwargs.get("limit", 10)
                products = await self.get_products_on_sale(limit)
                return {"success": True, "products": products}

            elif action == "advanced_search":
                products = await self.advanced_search(**kwargs)
                return {"success": True, "products": products}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            logger.error(f"Error executing product tool action: {str(e)}")
            return {"success": False, "error": str(e)}
