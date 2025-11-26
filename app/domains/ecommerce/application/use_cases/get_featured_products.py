"""
Get Featured Products Use Case

Use case for retrieving featured/highlighted products.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.interfaces.repository import ISearchableRepository

logger = logging.getLogger(__name__)


@dataclass
class GetFeaturedProductsRequest:
    """Request for getting featured products"""

    limit: int = 10
    category: Optional[str] = None  # Optional category filter


@dataclass
class GetFeaturedProductsResponse:
    """Response with featured products"""

    products: List[Dict[str, Any]]
    total_count: int
    success: bool
    error: Optional[str] = None


class GetFeaturedProductsUseCase:
    """
    Use case for getting featured products.

    Single Responsibility: Only handles featured products retrieval
    """

    def __init__(self, product_repository: ISearchableRepository):
        """
        Initialize use case.

        Args:
            product_repository: Repository for product data access (must support search and base operations)
        """
        self.product_repo = product_repository

    async def execute(self, request: GetFeaturedProductsRequest) -> GetFeaturedProductsResponse:
        """
        Execute use case to get featured products.

        Args:
            request: Request parameters

        Returns:
            Response with featured products
        """
        try:
            # Get all products (repository should handle filtering)
            all_products = await self.product_repo.find_all(skip=0, limit=request.limit * 2)

            # Filter featured products
            featured_products = [
                p for p in all_products if getattr(p, "featured", False) and getattr(p, "active", True)
            ]

            # Apply category filter if specified
            if request.category:
                featured_products = [
                    p for p in featured_products if p.category and p.category.name.lower() == request.category.lower()
                ]

            # Limit results
            featured_products = featured_products[: request.limit]

            # Convert to dicts
            product_dicts = [self._product_to_dict(p) for p in featured_products]

            return GetFeaturedProductsResponse(
                products=product_dicts,
                total_count=len(product_dicts),
                success=True,
            )

        except Exception as e:
            logger.error(f"Error getting featured products: {e}", exc_info=True)
            return GetFeaturedProductsResponse(
                products=[],
                total_count=0,
                success=False,
                error=str(e),
            )

    def _product_to_dict(self, product: Any) -> Dict[str, Any]:
        """Convert product to dictionary"""
        if isinstance(product, dict):
            return product

        return {
            "id": product.id,
            "name": product.name,
            "description": getattr(product, "description", None),
            "price": product.price,
            "stock": product.stock,
            "category": product.category.display_name if product.category else None,
            "brand": product.brand.name if product.brand else None,
            "specs": getattr(product, "specs", None),
            "featured": True,
            "on_sale": getattr(product, "on_sale", False),
            "active": True,
        }
