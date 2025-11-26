"""
E-commerce Domain Layer

Domain-Driven Design implementation for e-commerce bounded context.

This module contains:
- Entities: Business objects with identity (Product, Order, Customer)
- Value Objects: Immutable domain primitives (Price, SKU, OrderStatus)
- Domain Services: Complex business logic (PricingService)
- Events: Domain events for communication (future)
"""

from app.domains.ecommerce.domain.entities import (
    Customer,
    CustomerStatus,
    CustomerTier,
    Order,
    OrderItem,
    Product,
)
from app.domains.ecommerce.domain.services import (
    PricingContext,
    PricingResult,
    PricingService,
)
from app.domains.ecommerce.domain.value_objects import (
    OrderStatus,
    OrderStatusTransition,
    PaymentStatus,
    Price,
    ProductStatus,
    ShipmentStatus,
    SKU,
)

__all__ = [
    # Entities
    "Product",
    "Order",
    "OrderItem",
    "Customer",
    "CustomerTier",
    "CustomerStatus",
    # Value Objects
    "Price",
    "SKU",
    "OrderStatus",
    "PaymentStatus",
    "ShipmentStatus",
    "ProductStatus",
    "OrderStatusTransition",
    # Services
    "PricingService",
    "PricingContext",
    "PricingResult",
]
