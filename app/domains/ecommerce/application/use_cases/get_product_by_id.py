"""
Get Product By ID Use Case

Use case for retrieving a single product by its ID.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.core.interfaces.repository import IRepository

logger = logging.getLogger(__name__)


@dataclass
class GetProductByIdRequest:
    """Request for getting product by ID."""

    product_id: int


@dataclass
class GetProductByIdResponse:
    """Response from get product by ID."""

    product: dict[str, Any] | None
    success: bool
    error: str | None = None


class GetProductByIdUseCase:
    """
    Use case for getting a product by ID.

    Single Responsibility: Only handles single product retrieval
    Dependency Inversion: Depends on IRepository interface
    """

    def __init__(self, product_repository: IRepository):
        """
        Initialize use case with dependencies.

        Args:
            product_repository: Repository for product data access
        """
        self.product_repo = product_repository

    async def execute(self, product_id: int) -> GetProductByIdResponse:
        """
        Execute get product by ID use case.

        Args:
            product_id: Product ID to retrieve

        Returns:
            Response with product or error
        """
        try:
            product = await self.product_repo.find_by_id(product_id)

            if product is None:
                return GetProductByIdResponse(
                    product=None,
                    success=False,
                    error=f"Product with ID {product_id} not found",
                )

            product_dict = self._product_to_dict(product)

            return GetProductByIdResponse(
                product=product_dict,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error getting product by ID {product_id}: {e}", exc_info=True)
            return GetProductByIdResponse(
                product=None,
                success=False,
                error=str(e),
            )

    def _product_to_dict(self, product: Any) -> dict[str, Any]:
        """
        Convert product model to dictionary.

        Args:
            product: Product model (SQLAlchemy or dict)

        Returns:
            Product as dictionary
        """
        if isinstance(product, dict):
            return product

        # Convert SQLAlchemy model to dict
        return {
            "id": product.id,
            "name": product.name,
            "description": getattr(product, "description", None),
            "price": product.price,
            "stock": product.stock,
            "category_id": getattr(product, "category_id", None),
            "category": product.category.display_name if getattr(product, "category", None) else None,
            "brand": product.brand.name if getattr(product, "brand", None) else None,
            "model": getattr(product, "model", None),
            "specs": getattr(product, "specs", None),
            "featured": getattr(product, "featured", False),
            "on_sale": getattr(product, "on_sale", False),
            "active": getattr(product, "active", True),
        }
