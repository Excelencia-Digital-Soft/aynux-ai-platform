"""
Product Tool.

Single Responsibility: Orchestrate product queries using action dispatch.
"""

import logging
from typing import Any

from .formatter import ProductFormatter
from .query_builder import ProductQueryBuilder

logger = logging.getLogger(__name__)


class ProductTool:
    """
    Tool for querying product information from the database.

    Uses composition:
    - ProductQueryBuilder for database queries
    - ProductFormatter for result formatting
    """

    def __init__(self):
        self.name = "product_database_tool"
        self.description = (
            "Query product information from the database "
            "with advanced filtering and search capabilities"
        )

        # Compose dependencies
        self._formatter = ProductFormatter()
        self._query_builder = ProductQueryBuilder(self._formatter)

    async def get_all_products(
        self,
        include_inactive: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch all products from the database."""
        return await self._query_builder.get_all(include_inactive, limit)

    async def search_products(
        self,
        search_term: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search products by name, description, or model."""
        return await self._query_builder.search(search_term, limit)

    async def get_products_by_category(
        self,
        category_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get products by category name."""
        return await self._query_builder.get_by_category(category_name, limit)

    async def get_products_by_brand(
        self,
        brand_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get products by brand name."""
        return await self._query_builder.get_by_brand(brand_name, limit)

    async def get_products_by_price_range(
        self,
        min_price: float | None = None,
        max_price: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get products within a price range."""
        return await self._query_builder.get_by_price_range(
            min_price, max_price, limit
        )

    async def get_product_by_id(self, product_id: int) -> dict[str, Any] | None:
        """Get a specific product by ID."""
        return await self._query_builder.get_by_id(product_id)

    async def get_featured_products(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get featured products."""
        return await self._query_builder.get_featured(limit)

    async def get_products_on_sale(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get products on sale."""
        return await self._query_builder.get_on_sale(limit)

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
        return await self._query_builder.advanced_search(
            search_term=search_term,
            category=category,
            brand=brand,
            min_price=min_price,
            max_price=max_price,
            in_stock=in_stock,
            limit=limit,
        )

    async def __call__(self, action: str, **kwargs) -> dict[str, Any]:
        """Execute tool action."""
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
                products = await self.get_products_by_price_range(
                    min_price, max_price, limit
                )
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
