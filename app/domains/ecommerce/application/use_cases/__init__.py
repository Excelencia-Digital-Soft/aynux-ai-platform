"""
E-commerce Use Cases

Business use cases for the e-commerce domain.
Each use case represents a single business operation.
"""

from .create_order import (
    CreateOrderRequest,
    CreateOrderResponse,
    CreateOrderUseCase,
    OrderItemInput,
)
from .get_customer_orders import (
    GetCustomerOrdersRequest,
    GetCustomerOrdersResponse,
    GetCustomerOrdersUseCase,
)
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
from .track_order import (
    TrackOrderRequest,
    TrackOrderResponse,
    TrackOrderUseCase,
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
    # Create order
    "CreateOrderUseCase",
    "CreateOrderRequest",
    "CreateOrderResponse",
    "OrderItemInput",
    # Track order
    "TrackOrderUseCase",
    "TrackOrderRequest",
    "TrackOrderResponse",
    # Get customer orders
    "GetCustomerOrdersUseCase",
    "GetCustomerOrdersRequest",
    "GetCustomerOrdersResponse",
]
