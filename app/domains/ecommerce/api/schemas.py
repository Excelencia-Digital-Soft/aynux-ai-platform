"""
E-commerce API Schemas

Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductResponse(BaseModel):
    """Product response schema."""

    id: int
    name: str
    description: str | None = None
    price: Decimal
    stock: int
    category_id: int | None = None
    brand: str | None = None
    model: str | None = None
    is_active: bool = True

    class Config:
        from_attributes = True


class ProductSearchRequest(BaseModel):
    """Product search request schema."""

    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=100)
    category_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None


class ProductSearchResponse(BaseModel):
    """Product search response schema."""

    products: list[ProductResponse]
    total: int
    query: str


class OrderItemRequest(BaseModel):
    """Order item request schema."""

    product_id: int
    quantity: int = Field(..., ge=1)


class CreateOrderRequest(BaseModel):
    """Create order request schema."""

    customer_id: int
    items: list[OrderItemRequest]
    notes: str | None = None


class OrderResponse(BaseModel):
    """Order response schema."""

    id: int
    customer_id: int
    status: str
    total: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    """Category response schema."""

    id: int
    name: str
    display_name: str
    parent_id: int | None = None

    class Config:
        from_attributes = True


__all__ = [
    "ProductResponse",
    "ProductSearchRequest",
    "ProductSearchResponse",
    "OrderItemRequest",
    "CreateOrderRequest",
    "OrderResponse",
    "CategoryResponse",
]
