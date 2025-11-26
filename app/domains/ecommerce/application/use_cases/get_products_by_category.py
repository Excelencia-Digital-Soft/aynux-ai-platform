"""
Get Products By Category Use Case

Use case for retrieving products filtered by category and subcategory.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.interfaces.repository import ISearchableRepository

logger = logging.getLogger(__name__)


@dataclass
class GetProductsByCategoryRequest:
    """Request for getting products by category"""

    category: str
    subcategory: Optional[str] = None
    active_only: bool = True
    limit: int = 50
    sort_by: str = "featured"  # 'featured', 'price_asc', 'price_desc', 'name'


@dataclass
class GetProductsByCategoryResponse:
    """Response with products by category"""

    products: List[Dict[str, Any]]
    category: str
    subcategory: Optional[str]
    total_count: int
    success: bool
    error: Optional[str] = None


class GetProductsByCategoryUseCase:
    """
    Use case for getting products by category.

    Single Responsibility: Only handles category-based product retrieval
    """

    def __init__(self, product_repository: ISearchableRepository):
        """
        Initialize use case.

        Args:
            product_repository: Repository for product data access
        """
        self.product_repo = product_repository

    async def execute(self, request: GetProductsByCategoryRequest) -> GetProductsByCategoryResponse:
        """
        Execute use case to get products by category.

        Args:
            request: Request parameters

        Returns:
            Response with products
        """
        try:
            # Build filters for filter_by method
            filter_kwargs: dict[str, Any] = {
                "category": request.category.lower(),
            }

            if request.subcategory:
                filter_kwargs["subcategory"] = request.subcategory.lower()

            if request.active_only:
                filter_kwargs["active"] = True

            # Query products using filter_by (ISearchableRepository method)
            products = await self.product_repo.filter_by(**filter_kwargs)

            # Convert to dicts
            product_dicts = [self._product_to_dict(p) for p in products]

            return GetProductsByCategoryResponse(
                products=product_dicts,
                category=request.category,
                subcategory=request.subcategory,
                total_count=len(product_dicts),
                success=True,
            )

        except Exception as e:
            logger.error(f"Error getting products by category: {e}", exc_info=True)
            return GetProductsByCategoryResponse(
                products=[],
                category=request.category,
                subcategory=request.subcategory,
                total_count=0,
                success=False,
                error=str(e),
            )

    def _product_to_dict(self, product: Any) -> dict[str, Any]:
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
            "subcategory": product.subcategory.display_name if product.subcategory else None,
            "brand": product.brand.name if product.brand else None,
            "specs": getattr(product, "specs", None),
            "featured": getattr(product, "featured", False),
            "on_sale": getattr(product, "on_sale", False),
            "active": getattr(product, "active", True),
        }
