"""
E-commerce Use Cases

Business use cases for the e-commerce domain.
Each use case represents a single business operation.
"""

from .search_products import (
    SearchProductsUseCase,
    SearchProductsRequest,
    SearchProductsResponse,
)
from .get_products_by_category import (
    GetProductsByCategoryUseCase,
    GetProductsByCategoryRequest,
    GetProductsByCategoryResponse,
)
from .get_featured_products import (
    GetFeaturedProductsUseCase,
    GetFeaturedProductsRequest,
    GetFeaturedProductsResponse,
)

__all__ = [
    # Search products
    "SearchProductsUseCase",
    "SearchProductsRequest",
    "SearchProductsResponse",
    # Get by category
    "GetProductsByCategoryUseCase",
    "GetProductsByCategoryRequest",
    "GetProductsByCategoryResponse",
    # Get featured
    "GetFeaturedProductsUseCase",
    "GetFeaturedProductsRequest",
    "GetFeaturedProductsResponse",
]
