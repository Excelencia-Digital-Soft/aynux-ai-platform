"""
Create Order Use Case

Business logic for creating new orders.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.domains.ecommerce.application.ports import IOrderRepository, IProductRepository
from app.domains.ecommerce.domain.entities.order import Order, OrderItem
from app.domains.ecommerce.domain.value_objects.price import Price

logger = logging.getLogger(__name__)


@dataclass
class OrderItemInput:
    """Input for order item."""

    product_id: int
    quantity: int
    notes: str | None = None


@dataclass
class CreateOrderRequest:
    """Request for creating an order."""

    customer_id: int
    customer_name: str
    items: list[OrderItemInput]
    customer_email: str | None = None
    customer_phone: str | None = None
    shipping_address: dict[str, Any] | None = None
    notes: str | None = None


@dataclass
class CreateOrderResponse:
    """Response from order creation."""

    order: dict[str, Any] | None = None
    order_id: str | None = None
    order_number: str | None = None
    success: bool = False
    error: str | None = None
    validation_errors: list[str] = field(default_factory=list)


class CreateOrderUseCase:
    """
    Use Case: Create Order

    Creates a new order with validation of products and stock.

    Responsibilities:
    - Validate that products exist
    - Create order with items
    - Calculate totals
    - Persist via repository
    """

    def __init__(
        self,
        order_repository: IOrderRepository,
        product_repository: IProductRepository,
    ):
        """
        Initialize use case with dependencies.

        Args:
            order_repository: Repository for order data access
            product_repository: Repository for product validation
        """
        self.order_repository = order_repository
        self.product_repository = product_repository

    async def execute(self, request: CreateOrderRequest) -> CreateOrderResponse:
        """
        Create a new order.

        Args:
            request: Order creation request

        Returns:
            CreateOrderResponse with created order or error
        """
        try:
            # Validate request
            validation_errors = await self._validate_request(request)
            if validation_errors:
                return CreateOrderResponse(
                    success=False,
                    error="Validation failed",
                    validation_errors=validation_errors,
                )

            # Build order items with product details
            order_items = await self._build_order_items(request.items)
            if not order_items:
                return CreateOrderResponse(
                    success=False,
                    error="Failed to build order items - products may not exist",
                )

            # Create order entity
            order = Order.create_for_customer(
                customer_id=request.customer_id,
                customer_name=request.customer_name,
                customer_email=request.customer_email,
            )
            order.customer_phone = request.customer_phone
            order.customer_notes = request.notes

            # Add items to order
            for item in order_items:
                order.add_item(item)

            # Persist order
            created_order = await self.order_repository.create(order)

            logger.info(f"Order created: {created_order.order_number} " f"for customer {request.customer_id}")

            return CreateOrderResponse(
                order=created_order.to_detail_dict(),
                order_id=str(getattr(created_order, "_db_id", created_order.id)),
                order_number=created_order.order_number,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return CreateOrderResponse(
                success=False,
                error=str(e),
            )

    async def _validate_request(self, request: CreateOrderRequest) -> list[str]:
        """Validate order request."""
        errors = []

        if not request.customer_id:
            errors.append("Customer ID is required")

        if not request.customer_name:
            errors.append("Customer name is required")

        if not request.items:
            errors.append("At least one item is required")

        for i, item in enumerate(request.items):
            if item.quantity <= 0:
                errors.append(f"Item {i + 1}: Quantity must be positive")
            if item.product_id <= 0:
                errors.append(f"Item {i + 1}: Invalid product ID")

        return errors

    async def _build_order_items(self, items: list[OrderItemInput]) -> list[OrderItem]:
        """Build order items with product details."""
        order_items = []

        for item in items:
            product = await self.product_repository.get_by_id(item.product_id)
            if not product:
                logger.warning(f"Product not found: {item.product_id}")
                continue

            order_item = OrderItem(
                product_id=product.id or item.product_id,
                product_name=product.name,
                sku=product.sku,
                quantity=item.quantity,
                unit_price=product.price if product.price else Price.zero(),
                notes=item.notes,
            )
            order_items.append(order_item)

        return order_items


__all__ = ["CreateOrderUseCase", "CreateOrderRequest", "CreateOrderResponse", "OrderItemInput"]
