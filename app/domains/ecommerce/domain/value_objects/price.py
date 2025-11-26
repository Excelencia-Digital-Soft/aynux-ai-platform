"""
Price Value Object for E-commerce Domain

Represents a product price with currency and discount handling.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.core.domain import Money, ValueObject


@dataclass(frozen=True)
class Price(ValueObject):
    """
    Price value object for e-commerce products.

    Extends Money with e-commerce specific operations like
    tax calculations, wholesale pricing, and promotional discounts.

    Example:
        ```python
        price = Price(amount=Decimal("99.99"), currency="ARS")
        with_tax = price.add_tax(21.0)  # 21% IVA
        discounted = price.apply_promotional_discount(10)  # 10% off
        ```
    """

    amount: Decimal
    currency: str = "ARS"
    includes_tax: bool = True
    tax_rate: Decimal = Decimal("21.0")  # Argentina IVA

    def _validate(self) -> None:
        """Validate price constraints."""
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, "amount", Decimal(str(self.amount)))
        if self.amount < 0:
            raise ValueError("Price cannot be negative")

    def add_tax(self, tax_rate: float | None = None) -> "Price":
        """
        Add tax to price (if not already included).

        Args:
            tax_rate: Optional custom tax rate (default: instance tax_rate)

        Returns:
            New Price with tax added
        """
        if self.includes_tax:
            return self

        rate = Decimal(str(tax_rate)) if tax_rate else self.tax_rate
        tax_multiplier = 1 + (rate / 100)
        new_amount = (self.amount * tax_multiplier).quantize(Decimal("0.01"), ROUND_HALF_UP)

        return Price(
            amount=new_amount,
            currency=self.currency,
            includes_tax=True,
            tax_rate=rate,
        )

    def remove_tax(self) -> "Price":
        """
        Remove tax from price (get base price).

        Returns:
            New Price without tax
        """
        if not self.includes_tax:
            return self

        tax_divisor = 1 + (self.tax_rate / 100)
        new_amount = (self.amount / tax_divisor).quantize(Decimal("0.01"), ROUND_HALF_UP)

        return Price(
            amount=new_amount,
            currency=self.currency,
            includes_tax=False,
            tax_rate=self.tax_rate,
        )

    def get_tax_amount(self) -> Decimal:
        """Get the tax portion of the price."""
        if not self.includes_tax:
            return Decimal("0")

        base = self.remove_tax().amount
        return (self.amount - base).quantize(Decimal("0.01"), ROUND_HALF_UP)

    def apply_promotional_discount(self, percentage: float) -> "Price":
        """
        Apply a promotional percentage discount.

        Args:
            percentage: Discount percentage (0-100)

        Returns:
            New discounted Price
        """
        if percentage < 0 or percentage > 100:
            raise ValueError("Discount percentage must be between 0 and 100")

        discount_factor = Decimal(str(1 - percentage / 100))
        new_amount = (self.amount * discount_factor).quantize(Decimal("0.01"), ROUND_HALF_UP)

        return Price(
            amount=new_amount,
            currency=self.currency,
            includes_tax=self.includes_tax,
            tax_rate=self.tax_rate,
        )

    def apply_fixed_discount(self, discount_amount: Decimal) -> "Price":
        """
        Apply a fixed amount discount.

        Args:
            discount_amount: Fixed discount to subtract

        Returns:
            New discounted Price
        """
        new_amount = self.amount - discount_amount
        if new_amount < 0:
            new_amount = Decimal("0")

        return Price(
            amount=new_amount.quantize(Decimal("0.01"), ROUND_HALF_UP),
            currency=self.currency,
            includes_tax=self.includes_tax,
            tax_rate=self.tax_rate,
        )

    def calculate_wholesale_price(self, quantity: int, discount_tiers: dict[int, float] | None = None) -> "Price":
        """
        Calculate wholesale price based on quantity.

        Args:
            quantity: Number of items
            discount_tiers: Dict of {min_quantity: discount_percentage}

        Returns:
            Price with wholesale discount applied
        """
        default_tiers = {
            10: 5.0,  # 5% off for 10+ items
            50: 10.0,  # 10% off for 50+ items
            100: 15.0,  # 15% off for 100+ items
        }
        tiers = discount_tiers or default_tiers

        applicable_discount = 0.0
        for min_qty, discount in sorted(tiers.items()):
            if quantity >= min_qty:
                applicable_discount = discount

        if applicable_discount > 0:
            return self.apply_promotional_discount(applicable_discount)
        return self

    def to_money(self) -> Money:
        """Convert to base Money value object."""
        return Money(amount=self.amount, currency=self.currency)

    def multiply(self, quantity: int) -> "Price":
        """Multiply price by quantity."""
        new_amount = (self.amount * quantity).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Price(
            amount=new_amount,
            currency=self.currency,
            includes_tax=self.includes_tax,
            tax_rate=self.tax_rate,
        )

    def is_free(self) -> bool:
        """Check if price is zero (free product)."""
        return self.amount == Decimal("0")

    def __str__(self) -> str:
        return f"${self.amount:,.2f} {self.currency}"

    def __repr__(self) -> str:
        return f"Price(amount={self.amount}, currency='{self.currency}', includes_tax={self.includes_tax})"

    @classmethod
    def zero(cls, currency: str = "ARS") -> "Price":
        """Create a zero price."""
        return cls(amount=Decimal("0"), currency=currency)

    @classmethod
    def from_float(cls, amount: float, currency: str = "ARS") -> "Price":
        """Create Price from float with proper rounding."""
        return cls(amount=Decimal(str(amount)).quantize(Decimal("0.01"), ROUND_HALF_UP), currency=currency)
