"""
Ecommerce Application DTOs

Data Transfer Objects for the Ecommerce domain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


# ==================== Product DTOs ====================


@dataclass
class ProductDTO:
    """Product data transfer object"""

    id: int
    code: str
    name: str
    description: str
    price: Decimal
    stock: int
    category_id: int | None
    category_name: str | None
    brand: str | None
    image_url: str | None
    is_active: bool = True


@dataclass
class SearchProductsRequest:
    """Request for product search"""

    query: str
    limit: int = 10
    offset: int = 0
    category_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False


@dataclass
class SearchProductsResponse:
    """Response with product search results"""

    products: list[ProductDTO]
    total_count: int
    query: str
    page: int = 1
    page_size: int = 10


@dataclass
class GetProductByIdRequest:
    """Request to get product by ID"""

    product_id: int


@dataclass
class GetProductByIdResponse:
    """Response with product details"""

    product: ProductDTO | None
    found: bool


@dataclass
class GetProductsByCategoryRequest:
    """Request to get products by category"""

    category_id: int
    limit: int = 20
    offset: int = 0


@dataclass
class GetProductsByCategoryResponse:
    """Response with products in category"""

    products: list[ProductDTO]
    category_name: str
    total_count: int


@dataclass
class GetFeaturedProductsRequest:
    """Request for featured products"""

    limit: int = 10


@dataclass
class GetFeaturedProductsResponse:
    """Response with featured products"""

    products: list[ProductDTO]
    total_count: int


# ==================== Category DTOs ====================


@dataclass
class CategoryDTO:
    """Category data transfer object"""

    id: int
    code: str
    name: str
    description: str | None
    parent_id: int | None
    product_count: int = 0


@dataclass
class GetCategoriesResponse:
    """Response with categories"""

    categories: list[CategoryDTO]
    total_count: int


# ==================== Order DTOs ====================


@dataclass
class OrderItemDTO:
    """Order item data transfer object"""

    product_id: int
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


@dataclass
class OrderDTO:
    """Order data transfer object"""

    id: str
    customer_id: str
    items: list[OrderItemDTO]
    total_amount: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class CreateOrderRequest:
    """Request to create an order"""

    customer_id: str
    items: list[dict]  # [{product_id, quantity}]
    notes: str = ""


@dataclass
class CreateOrderResponse:
    """Response after creating order"""

    order: OrderDTO
    success: bool
    message: str


@dataclass
class TrackOrderRequest:
    """Request to track an order"""

    order_id: str


@dataclass
class TrackOrderResponse:
    """Response with order tracking info"""

    order_id: str
    status: str
    status_history: list[dict]
    estimated_delivery: datetime | None
    tracking_number: str | None


__all__ = [
    # Product DTOs
    "ProductDTO",
    "SearchProductsRequest",
    "SearchProductsResponse",
    "GetProductByIdRequest",
    "GetProductByIdResponse",
    "GetProductsByCategoryRequest",
    "GetProductsByCategoryResponse",
    "GetFeaturedProductsRequest",
    "GetFeaturedProductsResponse",
    # Category DTOs
    "CategoryDTO",
    "GetCategoriesResponse",
    # Order DTOs
    "OrderItemDTO",
    "OrderDTO",
    "CreateOrderRequest",
    "CreateOrderResponse",
    "TrackOrderRequest",
    "TrackOrderResponse",
]
