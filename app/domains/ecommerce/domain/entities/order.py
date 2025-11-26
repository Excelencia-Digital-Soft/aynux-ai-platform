"""
Order Entity for E-commerce Domain

Represents a customer order with items, status, and payment tracking.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.core.domain import (
    Address,
    AggregateRoot,
    BusinessRuleViolationException,
    InvalidOperationException,
    Money,
)

from ..value_objects.order_status import OrderStatus, PaymentStatus, ShipmentStatus
from ..value_objects.price import Price


@dataclass
class OrderItem:
    """
    Individual item in an order.

    Represents a line item with product, quantity, and pricing.
    """

    product_id: int
    product_name: str
    sku: str | None
    quantity: int
    unit_price: Price
    discount_applied: float = 0.0  # Percentage discount
    notes: str | None = None

    @property
    def subtotal(self) -> Price:
        """Calculate item subtotal."""
        if self.discount_applied > 0:
            discounted_price = self.unit_price.apply_promotional_discount(self.discount_applied)
            return discounted_price.multiply(self.quantity)
        return self.unit_price.multiply(self.quantity)

    @property
    def total_discount(self) -> Decimal:
        """Calculate total discount amount for this item."""
        if self.discount_applied == 0:
            return Decimal("0")
        original = self.unit_price.multiply(self.quantity)
        return original.amount - self.subtotal.amount

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "sku": self.sku,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price.amount),
            "discount_applied": self.discount_applied,
            "subtotal": float(self.subtotal.amount),
            "notes": self.notes,
        }


@dataclass
class Order(AggregateRoot[int]):
    """
    Order aggregate root for e-commerce domain.

    Manages order lifecycle, items, and payments.

    Example:
        ```python
        order = Order(customer_id=123)
        order.add_item(OrderItem(
            product_id=1,
            product_name="Laptop",
            quantity=1,
            unit_price=Price.from_float(999.99),
        ))
        order.confirm()
        order.process_payment(payment_id="PAY123")
        ```
    """

    # Customer reference
    customer_id: int = 0
    customer_name: str = ""
    customer_email: str | None = None
    customer_phone: str | None = None

    # Order items
    items: list[OrderItem] = field(default_factory=list)

    # Status tracking
    status: OrderStatus = OrderStatus.PENDING
    payment_status: PaymentStatus = PaymentStatus.PENDING
    shipment_status: ShipmentStatus | None = None

    # Addresses
    shipping_address: Address | None = None
    billing_address: Address | None = None

    # Pricing
    subtotal: Price = field(default_factory=lambda: Price.zero())
    shipping_cost: Price = field(default_factory=lambda: Price.zero())
    tax_amount: Price = field(default_factory=lambda: Price.zero())
    discount_amount: Price = field(default_factory=lambda: Price.zero())
    total: Price = field(default_factory=lambda: Price.zero())

    # Discounts
    coupon_code: str | None = None
    coupon_discount_percentage: float = 0.0
    loyalty_points_used: int = 0
    loyalty_discount: Price = field(default_factory=lambda: Price.zero())

    # Payment
    payment_method: str | None = None
    payment_id: str | None = None
    payment_date: datetime | None = None

    # Shipping
    shipping_method: str | None = None
    tracking_number: str | None = None
    estimated_delivery: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None

    # Notes and metadata
    customer_notes: str | None = None
    internal_notes: str | None = None
    order_number: str | None = None  # Human-readable order number

    # Timestamps
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self):
        """Initialize order calculations."""
        self._recalculate_totals()

    # Item Management

    def add_item(self, item: OrderItem) -> None:
        """
        Add an item to the order.

        Args:
            item: OrderItem to add

        Raises:
            InvalidOperationException: If order cannot be modified
        """
        if not self.status.is_active():
            raise InvalidOperationException(
                operation="add_item",
                current_state=self.status.value,
                message="Cannot add items to a non-active order",
            )

        # Check if same product exists
        for existing in self.items:
            if existing.product_id == item.product_id:
                existing.quantity += item.quantity
                self._recalculate_totals()
                self.touch()
                return

        self.items.append(item)
        self._recalculate_totals()
        self.touch()

    def remove_item(self, product_id: int) -> bool:
        """
        Remove an item from the order.

        Args:
            product_id: Product ID to remove

        Returns:
            True if removed
        """
        if not self.status.is_active():
            raise InvalidOperationException(
                operation="remove_item",
                current_state=self.status.value,
            )

        for item in self.items:
            if item.product_id == product_id:
                self.items.remove(item)
                self._recalculate_totals()
                self.touch()
                return True
        return False

    def update_item_quantity(self, product_id: int, quantity: int) -> bool:
        """
        Update quantity of an item.

        Args:
            product_id: Product ID
            quantity: New quantity (0 removes item)

        Returns:
            True if updated
        """
        if not self.status.is_active():
            raise InvalidOperationException(
                operation="update_quantity",
                current_state=self.status.value,
            )

        if quantity <= 0:
            return self.remove_item(product_id)

        for item in self.items:
            if item.product_id == product_id:
                item.quantity = quantity
                self._recalculate_totals()
                self.touch()
                return True
        return False

    def _recalculate_totals(self) -> None:
        """Recalculate all order totals."""
        # Calculate subtotal from items
        subtotal_amount = sum(item.subtotal.amount for item in self.items)
        self.subtotal = Price(amount=subtotal_amount)

        # Apply coupon discount
        if self.coupon_discount_percentage > 0:
            discount = subtotal_amount * Decimal(str(self.coupon_discount_percentage / 100))
            self.discount_amount = Price(amount=discount)
        else:
            self.discount_amount = Price.zero()

        # Calculate total
        total_amount = (
            self.subtotal.amount
            - self.discount_amount.amount
            - self.loyalty_discount.amount
            + self.shipping_cost.amount
            + self.tax_amount.amount
        )
        self.total = Price(amount=max(Decimal("0"), total_amount))

    # Discount Application

    def apply_coupon(self, code: str, discount_percentage: float) -> None:
        """
        Apply a coupon code.

        Args:
            code: Coupon code
            discount_percentage: Discount percentage (0-100)
        """
        if not self.status.is_active():
            raise InvalidOperationException(
                operation="apply_coupon",
                current_state=self.status.value,
            )

        self.coupon_code = code
        self.coupon_discount_percentage = discount_percentage
        self._recalculate_totals()
        self.touch()

    def remove_coupon(self) -> None:
        """Remove applied coupon."""
        self.coupon_code = None
        self.coupon_discount_percentage = 0.0
        self._recalculate_totals()
        self.touch()

    def apply_loyalty_points(self, points: int, value_per_point: float = 1.0) -> None:
        """
        Apply loyalty points as discount.

        Args:
            points: Points to use
            value_per_point: Value in currency per point
        """
        self.loyalty_points_used = points
        self.loyalty_discount = Price.from_float(points * value_per_point)
        self._recalculate_totals()
        self.touch()

    # Status Transitions

    def confirm(self) -> None:
        """
        Confirm the order.

        Validates order and transitions to CONFIRMED status.
        """
        if not self.status.can_transition_to(OrderStatus.CONFIRMED):
            raise InvalidOperationException(
                operation="confirm",
                current_state=self.status.value,
            )

        if not self.items:
            raise BusinessRuleViolationException(
                rule="ORDER_HAS_ITEMS",
                message="Cannot confirm an empty order",
            )

        if not self.shipping_address:
            raise BusinessRuleViolationException(
                rule="ORDER_HAS_SHIPPING_ADDRESS",
                message="Shipping address is required",
            )

        self.status = OrderStatus.CONFIRMED
        self.confirmed_at = datetime.now(UTC)
        self.touch()

    def start_processing(self) -> None:
        """Start processing the order."""
        if not self.status.can_transition_to(OrderStatus.PROCESSING):
            raise InvalidOperationException(
                operation="start_processing",
                current_state=self.status.value,
            )

        self.status = OrderStatus.PROCESSING
        self.touch()

    def ship(self, tracking_number: str | None = None) -> None:
        """
        Mark order as shipped.

        Args:
            tracking_number: Optional tracking number
        """
        if not self.status.can_transition_to(OrderStatus.SHIPPED):
            raise InvalidOperationException(
                operation="ship",
                current_state=self.status.value,
            )

        self.status = OrderStatus.SHIPPED
        self.shipment_status = ShipmentStatus.IN_TRANSIT
        self.shipped_at = datetime.now(UTC)
        if tracking_number:
            self.tracking_number = tracking_number
        self.touch()

    def deliver(self) -> None:
        """Mark order as delivered."""
        if not self.status.can_transition_to(OrderStatus.DELIVERED):
            raise InvalidOperationException(
                operation="deliver",
                current_state=self.status.value,
            )

        self.status = OrderStatus.DELIVERED
        self.shipment_status = ShipmentStatus.DELIVERED
        self.delivered_at = datetime.now(UTC)
        self.touch()

    def complete(self) -> None:
        """Mark order as completed."""
        if not self.status.can_transition_to(OrderStatus.COMPLETED):
            raise InvalidOperationException(
                operation="complete",
                current_state=self.status.value,
            )

        self.status = OrderStatus.COMPLETED
        self.touch()

    def cancel(self, reason: str | None = None) -> None:
        """
        Cancel the order.

        Args:
            reason: Cancellation reason
        """
        if not self.status.can_be_cancelled():
            raise InvalidOperationException(
                operation="cancel",
                current_state=self.status.value,
                message="Order cannot be cancelled in current state",
            )

        self.status = OrderStatus.CANCELLED
        self.cancelled_at = datetime.now(UTC)
        if reason:
            self.internal_notes = f"Cancelled: {reason}"
        self.touch()

    # Payment

    def process_payment(self, payment_id: str, payment_method: str | None = None) -> None:
        """
        Record successful payment.

        Args:
            payment_id: Payment transaction ID
            payment_method: Payment method used
        """
        self.payment_id = payment_id
        self.payment_method = payment_method
        self.payment_status = PaymentStatus.CAPTURED
        self.payment_date = datetime.now(UTC)
        self.touch()

    def fail_payment(self, reason: str | None = None) -> None:
        """Record failed payment."""
        self.payment_status = PaymentStatus.FAILED
        if reason:
            self.internal_notes = f"Payment failed: {reason}"
        self.touch()

    def refund(self) -> None:
        """Process refund."""
        self.payment_status = PaymentStatus.REFUNDED
        self.status = OrderStatus.REFUNDED
        self.touch()

    # Helpers

    @property
    def item_count(self) -> int:
        """Get total number of items (sum of quantities)."""
        return sum(item.quantity for item in self.items)

    @property
    def unique_item_count(self) -> int:
        """Get number of unique products."""
        return len(self.items)

    def is_paid(self) -> bool:
        """Check if order is paid."""
        return self.payment_status.is_successful()

    def can_be_modified(self) -> bool:
        """Check if order can be modified."""
        return self.status.is_active()

    # Serialization

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "id": self.id,
            "order_number": self.order_number,
            "status": self.status.value,
            "payment_status": self.payment_status.value,
            "item_count": self.item_count,
            "subtotal": float(self.subtotal.amount),
            "total": float(self.total.amount),
            "customer_name": self.customer_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """Convert to detailed dictionary."""
        return {
            **self.to_summary_dict(),
            "customer_id": self.customer_id,
            "customer_email": self.customer_email,
            "customer_phone": self.customer_phone,
            "items": [item.to_dict() for item in self.items],
            "shipping_address": str(self.shipping_address) if self.shipping_address else None,
            "billing_address": str(self.billing_address) if self.billing_address else None,
            "shipping_cost": float(self.shipping_cost.amount),
            "tax_amount": float(self.tax_amount.amount),
            "discount_amount": float(self.discount_amount.amount),
            "coupon_code": self.coupon_code,
            "tracking_number": self.tracking_number,
            "shipped_at": self.shipped_at.isoformat() if self.shipped_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "customer_notes": self.customer_notes,
        }

    @classmethod
    def create_for_customer(cls, customer_id: int, customer_name: str, customer_email: str | None = None) -> "Order":
        """
        Factory method to create order for customer.

        Args:
            customer_id: Customer ID
            customer_name: Customer name
            customer_email: Optional email

        Returns:
            New Order instance
        """
        return cls(
            customer_id=customer_id,
            customer_name=customer_name,
            customer_email=customer_email,
            status=OrderStatus.PENDING,
        )
