"""
Base Value Object Classes for Domain-Driven Design

Value Objects are immutable domain primitives that have no identity.
They are compared by their values, not by reference.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any, Self


@dataclass(frozen=True)
class ValueObject(ABC):
    """
    Base class for all value objects.

    Value objects are:
    - Immutable (frozen=True)
    - Compared by value (dataclass equality)
    - Have no identity

    Example:
        ```python
        @dataclass(frozen=True)
        class Email(ValueObject):
            address: str

            def __post_init__(self):
                if "@" not in self.address:
                    raise ValueError("Invalid email address")
        ```
    """

    def __post_init__(self):
        """Override to add validation logic."""
        self._validate()

    def _validate(self) -> None:
        """Validate the value object. Override in subclasses."""
        pass


@dataclass(frozen=True)
class Money(ValueObject):
    """
    Money value object for financial calculations.

    Represents an amount with currency and supports arithmetic operations.

    Example:
        ```python
        price = Money(amount=Decimal("99.99"), currency="USD")
        discounted = price.apply_discount(10)  # 10% off
        total = price.add(Money(Decimal("10.00"), "USD"))
        ```
    """

    amount: Decimal
    currency: str = "ARS"

    def _validate(self) -> None:
        """Validate money constraints."""
        if not isinstance(self.amount, Decimal):
            # Convert to Decimal if float/int
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")
        if not self.currency or len(self.currency) != 3:
            raise ValueError("Currency must be a 3-letter ISO code")

    def add(self, other: "Money") -> "Money":
        """Add two Money values (must be same currency)."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} to {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: "Money") -> "Money":
        """Subtract Money (must be same currency)."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {other.currency} from {self.currency}")
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("Result cannot be negative")
        return Money(amount=result, currency=self.currency)

    def multiply(self, factor: int | float | Decimal) -> "Money":
        """Multiply by a factor."""
        new_amount = self.amount * Decimal(str(factor))
        return Money(amount=new_amount.quantize(Decimal("0.01"), ROUND_HALF_UP), currency=self.currency)

    def apply_discount(self, percentage: float) -> "Money":
        """Apply a percentage discount."""
        if percentage < 0 or percentage > 100:
            raise ValueError("Percentage must be between 0 and 100")
        discount_factor = Decimal(str(1 - percentage / 100))
        new_amount = self.amount * discount_factor
        return Money(amount=new_amount.quantize(Decimal("0.01"), ROUND_HALF_UP), currency=self.currency)

    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == Decimal("0")

    def is_positive(self) -> bool:
        """Check if amount is positive."""
        return self.amount > Decimal("0")

    def __str__(self) -> str:
        return f"{self.currency} {self.amount:,.2f}"

    def __repr__(self) -> str:
        return f"Money(amount={self.amount}, currency='{self.currency}')"

    @classmethod
    def zero(cls, currency: str = "ARS") -> "Money":
        """Create a zero Money value."""
        return cls(amount=Decimal("0"), currency=currency)

    @classmethod
    def from_float(cls, amount: float, currency: str = "ARS") -> "Money":
        """Create Money from float (with proper rounding)."""
        return cls(amount=Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP), currency=currency)


@dataclass(frozen=True)
class Percentage(ValueObject):
    """
    Percentage value object.

    Represents a percentage value (0-100 or custom range).
    """

    value: Decimal
    min_value: Decimal = Decimal("0")
    max_value: Decimal = Decimal("100")

    def _validate(self) -> None:
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, "value", Decimal(str(self.value)))
        if self.value < self.min_value or self.value > self.max_value:
            raise ValueError(f"Percentage must be between {self.min_value} and {self.max_value}")

    def as_decimal(self) -> Decimal:
        """Get percentage as decimal (0.0 - 1.0)."""
        return self.value / Decimal("100")

    def apply_to(self, amount: Decimal) -> Decimal:
        """Apply percentage to an amount."""
        return amount * self.as_decimal()

    def __str__(self) -> str:
        return f"{self.value}%"


@dataclass(frozen=True)
class Quantity(ValueObject):
    """
    Quantity value object for stock/inventory.

    Represents a non-negative integer quantity.
    """

    value: int

    def _validate(self) -> None:
        if self.value < 0:
            raise ValueError("Quantity cannot be negative")

    def add(self, amount: int) -> "Quantity":
        """Add to quantity."""
        return Quantity(value=self.value + amount)

    def subtract(self, amount: int) -> "Quantity":
        """Subtract from quantity."""
        if amount > self.value:
            raise ValueError("Cannot subtract more than current quantity")
        return Quantity(value=self.value - amount)

    def is_zero(self) -> bool:
        """Check if quantity is zero."""
        return self.value == 0

    def is_available(self, required: int = 1) -> bool:
        """Check if required quantity is available."""
        return self.value >= required

    def __str__(self) -> str:
        return str(self.value)

    def __int__(self) -> int:
        return self.value

    @classmethod
    def zero(cls) -> "Quantity":
        """Create zero quantity."""
        return cls(value=0)


@dataclass(frozen=True)
class Email(ValueObject):
    """
    Email address value object.

    Validates and normalizes email addresses.
    """

    address: str

    def _validate(self) -> None:
        if not self.address or "@" not in self.address:
            raise ValueError(f"Invalid email address: {self.address}")
        # Normalize to lowercase
        object.__setattr__(self, "address", self.address.lower().strip())

    def get_domain(self) -> str:
        """Get email domain."""
        return self.address.split("@")[1]

    def __str__(self) -> str:
        return self.address


@dataclass(frozen=True)
class PhoneNumber(ValueObject):
    """
    Phone number value object.

    Normalizes and validates phone numbers.
    """

    number: str
    country_code: str = "54"  # Argentina default

    def _validate(self) -> None:
        # Remove non-digits except leading +
        cleaned = "".join(c for c in self.number if c.isdigit() or c == "+")
        if len(cleaned) < 8:
            raise ValueError(f"Invalid phone number: {self.number}")
        object.__setattr__(self, "number", cleaned)

    def get_formatted(self) -> str:
        """Get formatted phone number."""
        return f"+{self.country_code}{self.number}"

    def __str__(self) -> str:
        return self.get_formatted()


@dataclass(frozen=True)
class Address(ValueObject):
    """
    Physical address value object.
    """

    street: str
    city: str
    state: str
    postal_code: str
    country: str = "Argentina"

    def _validate(self) -> None:
        if not self.street or not self.city:
            raise ValueError("Street and city are required")

    def get_full_address(self) -> str:
        """Get full formatted address."""
        parts = [self.street, self.city, self.state, self.postal_code, self.country]
        return ", ".join(p for p in parts if p)

    def __str__(self) -> str:
        return self.get_full_address()


class StatusEnum(str, Enum):
    """
    Base class for status enums.

    Provides common functionality for all status value objects.
    """

    @classmethod
    def values(cls) -> list[str]:
        """Get all possible values."""
        return [e.value for e in cls]

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create from string value (case-insensitive)."""
        for member in cls:
            if member.value.lower() == value.lower():
                return member
        raise ValueError(f"Invalid {cls.__name__}: {value}")
