"""
Pricing Service for E-commerce Domain

Domain service that encapsulates complex pricing logic
that doesn't belong to a single entity.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ..entities.customer import Customer, CustomerTier
from ..entities.order import Order, OrderItem
from ..entities.product import Product
from ..value_objects.price import Price


@dataclass
class PricingContext:
    """Context for price calculations."""

    customer_tier: CustomerTier | None = None
    coupon_code: str | None = None
    coupon_discount: float = 0.0
    loyalty_points: int = 0
    is_wholesale: bool = False
    quantity_discount_enabled: bool = True


@dataclass
class PricingResult:
    """Result of pricing calculation."""

    original_price: Decimal
    final_price: Decimal
    discounts_applied: list[dict[str, Any]]
    tax_amount: Decimal
    total_savings: Decimal

    @property
    def discount_percentage(self) -> float:
        """Get total discount percentage."""
        if self.original_price == 0:
            return 0.0
        return float((self.original_price - self.final_price) / self.original_price * 100)


class PricingService:
    """
    Domain service for complex pricing calculations.

    Handles:
    - Customer tier discounts
    - Coupon/promotional discounts
    - Wholesale pricing
    - Quantity-based discounts
    - Tax calculations
    - Shipping cost calculations

    Example:
        ```python
        service = PricingService()
        result = service.calculate_product_price(
            product=product,
            quantity=5,
            context=PricingContext(customer_tier=CustomerTier.GOLD),
        )
        print(f"Final price: {result.final_price}")
        print(f"You save: {result.total_savings}")
        ```
    """

    def __init__(
        self,
        default_tax_rate: float = 21.0,
        loyalty_point_value: float = 1.0,
    ):
        """
        Initialize pricing service.

        Args:
            default_tax_rate: Default tax rate percentage (Argentina IVA = 21%)
            loyalty_point_value: Value in currency per loyalty point
        """
        self.default_tax_rate = default_tax_rate
        self.loyalty_point_value = loyalty_point_value

        # Quantity discount tiers (quantity: discount_percentage)
        self.quantity_tiers = {
            5: 3.0,
            10: 5.0,
            25: 8.0,
            50: 10.0,
            100: 15.0,
        }

        # Wholesale discount tiers
        self.wholesale_tiers = {
            10: 10.0,
            50: 15.0,
            100: 20.0,
            500: 25.0,
        }

    def calculate_product_price(
        self,
        product: Product,
        quantity: int = 1,
        context: PricingContext | None = None,
    ) -> PricingResult:
        """
        Calculate final price for a product.

        Args:
            product: Product to price
            quantity: Quantity being purchased
            context: Optional pricing context

        Returns:
            PricingResult with calculated prices
        """
        context = context or PricingContext()
        discounts: list[dict[str, Any]] = []

        # Start with product price
        base_price = product.price.amount * quantity
        current_price = base_price

        # 1. Apply product sale discount (if any)
        if product.on_sale and product.original_price:
            sale_discount = product.original_price.amount - product.price.amount
            discounts.append({
                "type": "sale",
                "description": f"Sale price",
                "percentage": product.get_discount_percentage(),
                "amount": sale_discount * quantity,
            })

        # 2. Apply quantity discount
        if context.quantity_discount_enabled and not context.is_wholesale:
            qty_discount = self._get_quantity_discount(quantity)
            if qty_discount > 0:
                discount_amount = current_price * Decimal(str(qty_discount / 100))
                current_price -= discount_amount
                discounts.append({
                    "type": "quantity",
                    "description": f"Quantity discount ({quantity}+ items)",
                    "percentage": qty_discount,
                    "amount": discount_amount,
                })

        # 3. Apply wholesale discount (exclusive with quantity discount)
        if context.is_wholesale:
            wholesale_discount = self._get_wholesale_discount(quantity)
            if wholesale_discount > 0:
                discount_amount = current_price * Decimal(str(wholesale_discount / 100))
                current_price -= discount_amount
                discounts.append({
                    "type": "wholesale",
                    "description": f"Wholesale discount",
                    "percentage": wholesale_discount,
                    "amount": discount_amount,
                })

        # 4. Apply customer tier discount
        if context.customer_tier:
            tier_discount = context.customer_tier.get_discount_percentage()
            if tier_discount > 0:
                discount_amount = current_price * Decimal(str(tier_discount / 100))
                current_price -= discount_amount
                discounts.append({
                    "type": "tier",
                    "description": f"{context.customer_tier.value.title()} member discount",
                    "percentage": tier_discount,
                    "amount": discount_amount,
                })

        # 5. Apply coupon discount
        if context.coupon_code and context.coupon_discount > 0:
            discount_amount = current_price * Decimal(str(context.coupon_discount / 100))
            current_price -= discount_amount
            discounts.append({
                "type": "coupon",
                "description": f"Coupon: {context.coupon_code}",
                "percentage": context.coupon_discount,
                "amount": discount_amount,
            })

        # 6. Apply loyalty points
        if context.loyalty_points > 0:
            points_value = Decimal(str(context.loyalty_points * self.loyalty_point_value))
            points_discount = min(points_value, current_price * Decimal("0.5"))  # Max 50% off with points
            current_price -= points_discount
            discounts.append({
                "type": "loyalty_points",
                "description": f"{context.loyalty_points} loyalty points",
                "amount": points_discount,
            })

        # Ensure price doesn't go below zero
        current_price = max(Decimal("0"), current_price)

        # Calculate tax
        tax_amount = self._calculate_tax(current_price)

        # Calculate total savings
        total_savings = base_price - current_price

        return PricingResult(
            original_price=base_price.quantize(Decimal("0.01"), ROUND_HALF_UP),
            final_price=current_price.quantize(Decimal("0.01"), ROUND_HALF_UP),
            discounts_applied=discounts,
            tax_amount=tax_amount.quantize(Decimal("0.01"), ROUND_HALF_UP),
            total_savings=total_savings.quantize(Decimal("0.01"), ROUND_HALF_UP),
        )

    def calculate_order_total(
        self,
        order: Order,
        customer: Customer | None = None,
    ) -> dict[str, Any]:
        """
        Calculate complete order total with all discounts.

        Args:
            order: Order to calculate
            customer: Optional customer for tier discounts

        Returns:
            Dictionary with pricing breakdown
        """
        context = PricingContext()
        if customer:
            context.customer_tier = customer.tier
            context.loyalty_points = order.loyalty_points_used

        if order.coupon_code:
            context.coupon_code = order.coupon_code
            context.coupon_discount = order.coupon_discount_percentage

        subtotal = Decimal("0")
        all_discounts: list[dict[str, Any]] = []

        # Calculate each item
        for item in order.items:
            item_total = item.unit_price.amount * item.quantity
            if item.discount_applied > 0:
                item_discount = item_total * Decimal(str(item.discount_applied / 100))
                item_total -= item_discount
                all_discounts.append({
                    "type": "item_discount",
                    "product": item.product_name,
                    "percentage": item.discount_applied,
                    "amount": item_discount,
                })
            subtotal += item_total

        # Apply order-level discounts
        current_total = subtotal

        # Customer tier discount
        if context.customer_tier:
            tier_discount = context.customer_tier.get_discount_percentage()
            if tier_discount > 0:
                discount_amount = current_total * Decimal(str(tier_discount / 100))
                current_total -= discount_amount
                all_discounts.append({
                    "type": "tier",
                    "description": f"{context.customer_tier.value.title()} discount",
                    "percentage": tier_discount,
                    "amount": discount_amount,
                })

        # Coupon discount
        if context.coupon_code and context.coupon_discount > 0:
            discount_amount = current_total * Decimal(str(context.coupon_discount / 100))
            current_total -= discount_amount
            all_discounts.append({
                "type": "coupon",
                "code": context.coupon_code,
                "percentage": context.coupon_discount,
                "amount": discount_amount,
            })

        # Loyalty points
        if context.loyalty_points > 0:
            points_value = Decimal(str(context.loyalty_points * self.loyalty_point_value))
            points_discount = min(points_value, current_total)
            current_total -= points_discount
            all_discounts.append({
                "type": "loyalty_points",
                "points_used": context.loyalty_points,
                "amount": points_discount,
            })

        # Add shipping
        shipping = order.shipping_cost.amount

        # Calculate tax on discounted subtotal
        tax = self._calculate_tax(current_total)

        # Final total
        final_total = current_total + shipping + tax

        return {
            "subtotal": float(subtotal.quantize(Decimal("0.01"), ROUND_HALF_UP)),
            "discounts": all_discounts,
            "total_discounts": float(sum(d.get("amount", 0) for d in all_discounts)),
            "subtotal_after_discounts": float(current_total.quantize(Decimal("0.01"), ROUND_HALF_UP)),
            "shipping": float(shipping.quantize(Decimal("0.01"), ROUND_HALF_UP)),
            "tax": float(tax.quantize(Decimal("0.01"), ROUND_HALF_UP)),
            "total": float(final_total.quantize(Decimal("0.01"), ROUND_HALF_UP)),
        }

    def _get_quantity_discount(self, quantity: int) -> float:
        """Get discount percentage based on quantity."""
        discount = 0.0
        for min_qty, disc in sorted(self.quantity_tiers.items()):
            if quantity >= min_qty:
                discount = disc
        return discount

    def _get_wholesale_discount(self, quantity: int) -> float:
        """Get wholesale discount percentage."""
        discount = 0.0
        for min_qty, disc in sorted(self.wholesale_tiers.items()):
            if quantity >= min_qty:
                discount = disc
        return discount

    def _calculate_tax(self, amount: Decimal) -> Decimal:
        """Calculate tax amount."""
        return amount * Decimal(str(self.default_tax_rate / 100))

    def calculate_shipping(
        self,
        weight: float,
        destination_zone: str = "local",
        is_express: bool = False,
    ) -> Price:
        """
        Calculate shipping cost.

        Args:
            weight: Package weight in kg
            destination_zone: Shipping zone (local, national, international)
            is_express: Express shipping option

        Returns:
            Shipping Price
        """
        # Base rates per kg
        zone_rates = {
            "local": 100.0,
            "national": 200.0,
            "international": 500.0,
        }

        base_rate = zone_rates.get(destination_zone, 200.0)
        shipping_cost = base_rate + (weight * 50)

        if is_express:
            shipping_cost *= 1.5

        # Minimum shipping cost
        shipping_cost = max(shipping_cost, 150.0)

        return Price.from_float(shipping_cost)

    def estimate_loyalty_points(
        self,
        order_total: Decimal,
        customer_tier: CustomerTier = CustomerTier.BRONZE,
    ) -> int:
        """
        Estimate loyalty points earned from an order.

        Args:
            order_total: Order total amount
            customer_tier: Customer tier for multiplier

        Returns:
            Points to be earned
        """
        # Base: 1 point per 100 currency
        base_points = int(order_total / 100)

        # Apply tier multiplier
        multiplier = customer_tier.get_points_multiplier()
        return int(base_points * multiplier)
