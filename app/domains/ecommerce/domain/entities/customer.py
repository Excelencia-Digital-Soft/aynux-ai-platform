"""
Customer Entity for E-commerce Domain

Represents a customer with profile, preferences, and order history.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.core.domain import Address, AggregateRoot, Email, PhoneNumber, StatusEnum


class CustomerTier(StatusEnum):
    """Customer loyalty tiers with benefits."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    VIP = "vip"

    def get_discount_percentage(self) -> float:
        """Get discount percentage for tier."""
        discounts = {
            "bronze": 0.0,
            "silver": 5.0,
            "gold": 10.0,
            "platinum": 15.0,
            "vip": 20.0,
        }
        return discounts.get(self.value, 0.0)

    def get_points_multiplier(self) -> float:
        """Get loyalty points multiplier."""
        multipliers = {
            "bronze": 1.0,
            "silver": 1.5,
            "gold": 2.0,
            "platinum": 2.5,
            "vip": 3.0,
        }
        return multipliers.get(self.value, 1.0)


class CustomerStatus(StatusEnum):
    """Customer account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


@dataclass
class Customer(AggregateRoot[int]):
    """
    Customer aggregate root for e-commerce domain.

    Manages customer profile, addresses, and loyalty program.

    Example:
        ```python
        customer = Customer(
            first_name="Juan",
            last_name="Pérez",
            email=Email("juan@example.com"),
            phone=PhoneNumber("1155551234"),
        )
        customer.add_loyalty_points(100)
        discount = customer.get_tier_discount()
        ```
    """

    # Personal information
    first_name: str = ""
    last_name: str = ""
    email: Email | None = None
    phone: PhoneNumber | None = None

    # WhatsApp specific
    whatsapp_phone: str | None = None  # Normalized WhatsApp number
    whatsapp_name: str | None = None  # WhatsApp profile name

    # Account status
    status: CustomerStatus = CustomerStatus.ACTIVE

    # Addresses
    default_shipping_address: Address | None = None
    default_billing_address: Address | None = None
    addresses: list[Address] = field(default_factory=list)

    # Loyalty program
    tier: CustomerTier = CustomerTier.BRONZE
    loyalty_points: int = 0
    total_spent: float = 0.0
    total_orders: int = 0

    # Preferences
    language: str = "es"
    currency: str = "ARS"
    marketing_consent: bool = False
    notification_preferences: dict[str, bool] = field(
        default_factory=lambda: {
            "email": True,
            "whatsapp": True,
            "sms": False,
            "push": True,
        }
    )

    # Metadata
    last_order_at: datetime | None = None
    last_login_at: datetime | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate customer after initialization."""
        if not self.first_name and not self.whatsapp_name:
            raise ValueError("Customer must have a name")

    @property
    def full_name(self) -> str:
        """Get full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        if self.first_name:
            return self.first_name
        return self.whatsapp_name or "Unknown"

    @property
    def display_name(self) -> str:
        """Get display name for chat/messages."""
        return self.first_name or self.whatsapp_name or "Cliente"

    # Loyalty Program

    def add_loyalty_points(self, points: int) -> int:
        """
        Add loyalty points with tier multiplier.

        Args:
            points: Base points to add

        Returns:
            Actual points added (after multiplier)
        """
        multiplier = self.tier.get_points_multiplier()
        actual_points = int(points * multiplier)
        self.loyalty_points += actual_points
        self.touch()
        self._check_tier_upgrade()
        return actual_points

    def redeem_loyalty_points(self, points: int) -> bool:
        """
        Redeem loyalty points.

        Args:
            points: Points to redeem

        Returns:
            True if successful
        """
        if points > self.loyalty_points:
            return False

        self.loyalty_points -= points
        self.touch()
        return True

    def _check_tier_upgrade(self) -> None:
        """Check and apply tier upgrade based on total spent."""
        tier_thresholds = {
            50000: CustomerTier.SILVER,
            150000: CustomerTier.GOLD,
            500000: CustomerTier.PLATINUM,
            1000000: CustomerTier.VIP,
        }

        for threshold, tier in sorted(tier_thresholds.items()):
            if self.total_spent >= threshold:
                self.tier = tier

    def get_tier_discount(self) -> float:
        """Get discount percentage based on tier."""
        return self.tier.get_discount_percentage()

    # Order Tracking

    def record_order(self, order_total: float) -> None:
        """
        Record a completed order.

        Args:
            order_total: Total order amount
        """
        self.total_orders += 1
        self.total_spent += order_total
        self.last_order_at = datetime.now(UTC)
        self.touch()
        self._check_tier_upgrade()

    def get_average_order_value(self) -> float:
        """Get average order value."""
        if self.total_orders == 0:
            return 0.0
        return self.total_spent / self.total_orders

    # Address Management

    def add_address(self, address: Address, set_as_default_shipping: bool = False, set_as_default_billing: bool = False) -> None:
        """
        Add a new address.

        Args:
            address: Address to add
            set_as_default_shipping: Set as default shipping address
            set_as_default_billing: Set as default billing address
        """
        self.addresses.append(address)

        if set_as_default_shipping or self.default_shipping_address is None:
            self.default_shipping_address = address

        if set_as_default_billing or self.default_billing_address is None:
            self.default_billing_address = address

        self.touch()

    def remove_address(self, address: Address) -> bool:
        """
        Remove an address.

        Args:
            address: Address to remove

        Returns:
            True if removed
        """
        if address in self.addresses:
            self.addresses.remove(address)
            if self.default_shipping_address == address:
                self.default_shipping_address = self.addresses[0] if self.addresses else None
            if self.default_billing_address == address:
                self.default_billing_address = self.addresses[0] if self.addresses else None
            self.touch()
            return True
        return False

    # Account Status

    def activate(self) -> None:
        """Activate customer account."""
        self.status = CustomerStatus.ACTIVE
        self.touch()

    def suspend(self, reason: str | None = None) -> None:
        """Suspend customer account."""
        self.status = CustomerStatus.SUSPENDED
        if reason:
            self.notes = f"Suspended: {reason}"
        self.touch()

    def is_active(self) -> bool:
        """Check if customer account is active."""
        return self.status == CustomerStatus.ACTIVE

    # Preferences

    def update_notification_preferences(self, preferences: dict[str, bool]) -> None:
        """Update notification preferences."""
        self.notification_preferences.update(preferences)
        self.touch()

    def set_marketing_consent(self, consent: bool) -> None:
        """Set marketing consent."""
        self.marketing_consent = consent
        self.touch()

    # Serialization

    def to_profile_dict(self) -> dict[str, Any]:
        """Convert to profile dictionary."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": str(self.email) if self.email else None,
            "phone": str(self.phone) if self.phone else None,
            "whatsapp_phone": self.whatsapp_phone,
            "tier": self.tier.value,
            "loyalty_points": self.loyalty_points,
            "total_orders": self.total_orders,
            "status": self.status.value,
            "language": self.language,
        }

    def to_chat_context(self) -> dict[str, Any]:
        """Convert to chat context for agent conversations."""
        return {
            "customer_id": self.id,
            "name": self.display_name,
            "tier": self.tier.value,
            "points": self.loyalty_points,
            "discount": self.get_tier_discount(),
            "language": self.language,
            "total_orders": self.total_orders,
        }

    @classmethod
    def from_whatsapp(cls, phone: str, name: str | None = None) -> "Customer":
        """
        Create customer from WhatsApp contact.

        Args:
            phone: WhatsApp phone number
            name: WhatsApp profile name

        Returns:
            New Customer instance
        """
        return cls(
            first_name=name or "",
            whatsapp_phone=phone,
            whatsapp_name=name,
            status=CustomerStatus.ACTIVE,
        )
