"""
Order Status Value Object for E-commerce Domain

Represents the lifecycle states of an order with transition rules.
"""

from dataclasses import dataclass
from enum import Enum

from app.core.domain import StatusEnum


class OrderStatus(StatusEnum):
    """
    Order lifecycle states.

    Valid transitions:
    - PENDING -> CONFIRMED, CANCELLED
    - CONFIRMED -> PROCESSING, CANCELLED
    - PROCESSING -> SHIPPED, CANCELLED
    - SHIPPED -> DELIVERED, RETURNED
    - DELIVERED -> RETURNED, COMPLETED
    - RETURNED -> REFUNDED
    - CANCELLED, REFUNDED, COMPLETED -> (terminal states)
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RETURNED = "returned"
    REFUNDED = "refunded"

    # Transition rules: status -> list of valid next statuses
    _transitions: dict[str, list[str]] = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["processing", "cancelled"],
        "processing": ["shipped", "cancelled"],
        "shipped": ["delivered", "returned"],
        "delivered": ["returned", "completed"],
        "completed": [],  # Terminal state
        "cancelled": [],  # Terminal state
        "returned": ["refunded"],
        "refunded": [],  # Terminal state
    }

    def can_transition_to(self, new_status: "OrderStatus") -> bool:
        """
        Check if transition to new status is valid.

        Args:
            new_status: Target status

        Returns:
            True if transition is allowed
        """
        allowed = self._transitions.get(self.value, [])
        return new_status.value in allowed

    def get_valid_transitions(self) -> list["OrderStatus"]:
        """
        Get list of valid next statuses.

        Returns:
            List of OrderStatus that can be transitioned to
        """
        allowed_values = self._transitions.get(self.value, [])
        return [OrderStatus(v) for v in allowed_values]

    def is_terminal(self) -> bool:
        """Check if this is a terminal (final) state."""
        return len(self._transitions.get(self.value, [])) == 0

    def is_active(self) -> bool:
        """Check if order is still active (can be modified)."""
        return self.value in ["pending", "confirmed", "processing"]

    def is_shipped(self) -> bool:
        """Check if order has been shipped."""
        return self.value in ["shipped", "delivered", "completed"]

    def requires_payment(self) -> bool:
        """Check if this status requires payment to proceed."""
        return self.value == "pending"

    def can_be_cancelled(self) -> bool:
        """Check if order can be cancelled in this state."""
        return self.value in ["pending", "confirmed", "processing"]

    def can_be_returned(self) -> bool:
        """Check if order can be returned in this state."""
        return self.value in ["shipped", "delivered"]


class PaymentStatus(StatusEnum):
    """Payment status for orders."""

    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.value in ["authorized", "captured"]

    def is_refundable(self) -> bool:
        """Check if payment can be refunded."""
        return self.value in ["authorized", "captured", "partially_refunded"]


class ShipmentStatus(StatusEnum):
    """Shipment/delivery status."""

    PREPARING = "preparing"
    READY_FOR_PICKUP = "ready_for_pickup"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED_TO_SENDER = "returned_to_sender"

    def is_in_transit(self) -> bool:
        """Check if shipment is currently in transit."""
        return self.value in ["in_transit", "out_for_delivery"]

    def is_delivered(self) -> bool:
        """Check if shipment has been delivered."""
        return self.value == "delivered"


class ProductStatus(StatusEnum):
    """Product availability status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"
    COMING_SOON = "coming_soon"
    DRAFT = "draft"

    def is_available_for_sale(self) -> bool:
        """Check if product can be purchased."""
        return self.value == "active"

    def is_visible(self) -> bool:
        """Check if product should be visible in catalog."""
        return self.value in ["active", "out_of_stock", "coming_soon"]


@dataclass(frozen=True)
class OrderStatusTransition:
    """
    Represents a status transition with metadata.

    Used to track status history with timestamps and reasons.
    """

    from_status: OrderStatus | None
    to_status: OrderStatus
    reason: str | None = None
    performed_by: str | None = None

    def __str__(self) -> str:
        from_str = self.from_status.value if self.from_status else "NEW"
        return f"{from_str} -> {self.to_status.value}"
