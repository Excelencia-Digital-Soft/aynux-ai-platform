"""
E-commerce Use Cases

Business use cases for the e-commerce domain.
Each use case represents a single business operation.
"""

from .get_featured_products import (
    GetFeaturedProductsRequest,
    GetFeaturedProductsResponse,
    GetFeaturedProductsUseCase,
)
from .get_product_by_id import (
    GetProductByIdRequest,
    GetProductByIdResponse,
    GetProductByIdUseCase,
)
from .get_products_by_category import (
    GetProductsByCategoryRequest,
    GetProductsByCategoryResponse,
    GetProductsByCategoryUseCase,
)
from .search_products import (
    SearchProductsRequest,
    SearchProductsResponse,
    SearchProductsUseCase,
)

__all__ = [
    # Search products
    "SearchProductsUseCase",
    "SearchProductsRequest",
    "SearchProductsResponse",
    # Get by ID
    "GetProductByIdUseCase",
    "GetProductByIdRequest",
    "GetProductByIdResponse",
    # Get by category
    "GetProductsByCategoryUseCase",
    "GetProductsByCategoryRequest",
    "GetProductsByCategoryResponse",
    # Get featured
    "GetFeaturedProductsUseCase",
    "GetFeaturedProductsRequest",
    "GetFeaturedProductsResponse",
]
