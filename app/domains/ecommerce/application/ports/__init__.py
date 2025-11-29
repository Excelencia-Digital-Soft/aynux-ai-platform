"""
Ecommerce Application Ports

Interface definitions (ports) for the Ecommerce domain.
Uses Protocol for structural typing.
"""

from typing import Protocol, runtime_checkable

from app.domains.ecommerce.domain.entities.order import Order
from app.domains.ecommerce.domain.entities.product import Product


@runtime_checkable
class IProductRepository(Protocol):
    """
    Interface for product repository.

    Defines the contract for product data access.
    """

    async def get_by_id(self, product_id: int) -> Product | None:
        """Get product by ID"""
        ...

    async def get_by_code(self, code: str) -> Product | None:
        """Get product by code"""
        ...

    async def search(self, query: str, limit: int = 10, offset: int = 0) -> list[Product]:
        """Search products by query"""
        ...

    async def get_by_category(self, category_id: int, limit: int = 20, offset: int = 0) -> list[Product]:
        """Get products by category"""
        ...

    async def get_featured(self, limit: int = 10) -> list[Product]:
        """Get featured products"""
        ...

    async def count_by_query(self, query: str) -> int:
        """Count products matching query"""
        ...

    async def save(self, product: Product) -> Product:
        """Save a product"""
        ...


@runtime_checkable
class IOrderRepository(Protocol):
    """
    Interface for order repository.

    Defines the contract for order data access.
    """

    async def create(self, order: Order) -> Order:
        """Create a new order"""
        ...

    async def get_by_id(self, order_id: str) -> Order | None:
        """Get order by ID"""
        ...

    async def get_by_customer(self, customer_id: str, limit: int = 10) -> list[Order]:
        """Get orders by customer"""
        ...

    async def update_status(self, order_id: str, status: str) -> Order | None:
        """Update order status"""
        ...

    async def get_tracking_info(self, order_id: str) -> dict | None:
        """Get order tracking information"""
        ...


@runtime_checkable
class ICategoryRepository(Protocol):
    """
    Interface for category repository.

    Defines the contract for category data access.
    """

    async def get_all(self) -> list[dict]:
        """Get all categories"""
        ...

    async def get_by_id(self, category_id: int) -> dict | None:
        """Get category by ID"""
        ...

    async def get_children(self, parent_id: int) -> list[dict]:
        """Get child categories"""
        ...


@runtime_checkable
class IPromotionRepository(Protocol):
    """
    Interface for promotion repository.

    Defines the contract for promotion data access.
    """

    async def get_active(self) -> list[dict]:
        """Get active promotions"""
        ...

    async def get_by_product(self, product_id: int) -> list[dict]:
        """Get promotions for a product"""
        ...

    async def get_by_category(self, category_id: int) -> list[dict]:
        """Get promotions for a category"""
        ...


__all__ = [
    "IProductRepository",
    "IOrderRepository",
    "ICategoryRepository",
    "IPromotionRepository",
]
