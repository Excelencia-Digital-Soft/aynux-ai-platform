"""
Product Entity for E-commerce Domain

Represents a product in the catalog with business logic.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.domain import AggregateRoot, InsufficientStockException, Quantity

from ..value_objects.order_status import ProductStatus
from ..value_objects.price import Price
from ..value_objects.sku import SKU


@dataclass
class Product(AggregateRoot[int]):
    """
    Product aggregate root for e-commerce domain.

    Contains business logic for:
    - Stock management
    - Pricing and discounts
    - Product lifecycle (active/inactive)
    - Catalog visibility

    Example:
        ```python
        product = Product(
            name="Laptop Gaming Pro",
            sku=SKU("ELEC-LAPTOP-00001"),
            price=Price.from_float(999.99),
            stock=Quantity(50),
        )
        product.apply_discount(10.0)  # 10% off
        product.reserve_stock(5)  # Reserve 5 units
        ```
    """

    name: str = ""
    description: str | None = None
    sku: SKU | None = None
    price: Price = field(default_factory=lambda: Price.zero())
    original_price: Price | None = None  # For showing discounts
    stock: Quantity = field(default_factory=lambda: Quantity.zero())
    reserved_stock: Quantity = field(default_factory=lambda: Quantity.zero())

    # Categorization
    category_id: int | None = None
    category_name: str | None = None
    subcategory_id: int | None = None
    brand_id: int | None = None
    brand_name: str | None = None

    # Product attributes
    specs: dict[str, Any] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    weight: float | None = None  # In kg
    dimensions: dict[str, float] | None = None  # width, height, depth in cm

    # Status and visibility
    status: ProductStatus = ProductStatus.DRAFT
    featured: bool = False
    on_sale: bool = False

    # SEO
    slug: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None

    def __post_init__(self):
        """Validate product after initialization."""
        if not self.name:
            raise ValueError("Product name is required")

    # Stock Management

    def is_available(self, quantity: int = 1) -> bool:
        """
        Check if product is available for purchase.

        Args:
            quantity: Required quantity

        Returns:
            True if stock is available and product is active
        """
        return (
            self.status == ProductStatus.ACTIVE
            and self.get_available_stock() >= quantity
        )

    def get_available_stock(self) -> int:
        """Get stock available for sale (total - reserved)."""
        return max(0, self.stock.value - self.reserved_stock.value)

    def reserve_stock(self, quantity: int) -> None:
        """
        Reserve stock for an order.

        Args:
            quantity: Amount to reserve

        Raises:
            InsufficientStockException: If not enough stock
        """
        available = self.get_available_stock()
        if quantity > available:
            raise InsufficientStockException(
                product_id=self.id or 0,
                requested=quantity,
                available=available,
            )

        self.reserved_stock = self.reserved_stock.add(quantity)
        self.touch()

    def release_reserved_stock(self, quantity: int) -> None:
        """
        Release reserved stock (e.g., order cancelled).

        Args:
            quantity: Amount to release
        """
        current = self.reserved_stock.value
        new_reserved = max(0, current - quantity)
        self.reserved_stock = Quantity(new_reserved)
        self.touch()

    def confirm_stock_reduction(self, quantity: int) -> None:
        """
        Confirm stock reduction (order shipped).

        Moves stock from reserved to actually reduced.

        Args:
            quantity: Amount to reduce
        """
        # Reduce from reserved first
        self.release_reserved_stock(quantity)
        # Then reduce actual stock
        self.stock = self.stock.subtract(quantity)
        self.touch()

        # Update status if out of stock
        if self.stock.is_zero():
            self.status = ProductStatus.OUT_OF_STOCK

    def add_stock(self, quantity: int) -> None:
        """
        Add stock (restock operation).

        Args:
            quantity: Amount to add
        """
        self.stock = self.stock.add(quantity)
        self.touch()

        # Reactivate if was out of stock
        if self.status == ProductStatus.OUT_OF_STOCK and self.stock.value > 0:
            self.status = ProductStatus.ACTIVE

    # Pricing

    def apply_discount(self, percentage: float) -> None:
        """
        Apply a percentage discount.

        Args:
            percentage: Discount percentage (0-100)
        """
        if self.original_price is None:
            self.original_price = self.price

        self.price = self.original_price.apply_promotional_discount(percentage)
        self.on_sale = True
        self.touch()

    def remove_discount(self) -> None:
        """Remove discount and restore original price."""
        if self.original_price is not None:
            self.price = self.original_price
            self.original_price = None
            self.on_sale = False
            self.touch()

    def get_discount_percentage(self) -> float:
        """Get current discount percentage."""
        if self.original_price is None or self.original_price.amount == 0:
            return 0.0

        discount = float(self.original_price.amount - self.price.amount)
        return round((discount / float(self.original_price.amount)) * 100, 2)

    def set_price(self, new_price: Price) -> None:
        """
        Update product price.

        Args:
            new_price: New price value
        """
        self.price = new_price
        self.on_sale = False
        self.original_price = None
        self.touch()

    # Status Management

    def activate(self) -> None:
        """Activate product for sale."""
        if self.stock.is_zero():
            self.status = ProductStatus.OUT_OF_STOCK
        else:
            self.status = ProductStatus.ACTIVE
        self.touch()

    def deactivate(self) -> None:
        """Deactivate product (hide from catalog)."""
        self.status = ProductStatus.INACTIVE
        self.touch()

    def discontinue(self) -> None:
        """Mark product as discontinued."""
        self.status = ProductStatus.DISCONTINUED
        self.touch()

    def set_as_coming_soon(self) -> None:
        """Mark product as coming soon."""
        self.status = ProductStatus.COMING_SOON
        self.touch()

    # Feature toggles

    def set_featured(self, featured: bool = True) -> None:
        """Set product featured status."""
        self.featured = featured
        self.touch()

    # Catalog helpers

    def is_visible_in_catalog(self) -> bool:
        """Check if product should appear in catalog."""
        return self.status.is_visible()

    def is_purchasable(self) -> bool:
        """Check if product can be purchased."""
        return self.status.is_available_for_sale() and self.get_available_stock() > 0

    # Serialization

    def to_catalog_dict(self) -> dict[str, Any]:
        """
        Convert to catalog-friendly dictionary.

        Returns:
            Dictionary with catalog display data
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sku": str(self.sku) if self.sku else None,
            "price": str(self.price),
            "price_amount": float(self.price.amount),
            "original_price": str(self.original_price) if self.original_price else None,
            "discount_percentage": self.get_discount_percentage() if self.on_sale else None,
            "stock_available": self.get_available_stock(),
            "in_stock": self.is_available(),
            "category": self.category_name,
            "brand": self.brand_name,
            "images": self.images,
            "featured": self.featured,
            "on_sale": self.on_sale,
            "status": self.status.value,
        }

    def to_search_dict(self) -> dict[str, Any]:
        """
        Convert to search-indexable dictionary.

        Returns:
            Dictionary for vector/search indexing
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "category": self.category_name or "",
            "brand": self.brand_name or "",
            "specs": self.specs,
            "tags": self.tags,
            "price": float(self.price.amount),
        }
