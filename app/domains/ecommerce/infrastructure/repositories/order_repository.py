"""
Order Repository Implementation

SQLAlchemy implementation of IOrderRepository.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.ecommerce.application.ports import IOrderRepository
from app.domains.ecommerce.domain.entities.order import Order, OrderItem
from app.domains.ecommerce.domain.value_objects.order_status import (
    OrderStatus,
    PaymentStatus,
    ShipmentStatus,
)
from app.domains.ecommerce.domain.value_objects.price import Price
from app.models.db.orders import Order as OrderModel
from app.models.db.orders import OrderItem as OrderItemModel

logger = logging.getLogger(__name__)


class SQLAlchemyOrderRepository(IOrderRepository):
    """
    SQLAlchemy implementation of order repository.

    Handles all order data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(self, order: Order) -> Order:
        """Create a new order."""
        model = self._to_model(order)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model, attribute_names=["items"])
        return self._to_entity(model)

    async def get_by_id(self, order_id: str) -> Order | None:
        """Get order by ID."""
        try:
            order_uuid = uuid.UUID(order_id)
            result = await self.session.execute(
                select(OrderModel)
                .options(selectinload(OrderModel.items))
                .where(OrderModel.id == order_uuid)
            )
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None
        except ValueError:
            # Try by order number
            result = await self.session.execute(
                select(OrderModel)
                .options(selectinload(OrderModel.items))
                .where(OrderModel.order_number == order_id)
            )
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None
        except Exception as e:
            logger.error(f"Error getting order by ID {order_id}: {e}")
            raise

    async def get_by_customer(self, customer_id: str, limit: int = 10) -> list[Order]:
        """Get orders by customer."""
        try:
            customer_uuid = uuid.UUID(customer_id)
            result = await self.session.execute(
                select(OrderModel)
                .options(selectinload(OrderModel.items))
                .where(OrderModel.customer_id == customer_uuid)
                .order_by(OrderModel.order_date.desc())
                .limit(limit)
            )
            models = result.scalars().all()
            return [self._to_entity(m) for m in models]
        except ValueError:
            logger.warning(f"Invalid customer_id format: {customer_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting orders for customer {customer_id}: {e}")
            raise

    async def update_status(self, order_id: str, status: str) -> Order | None:
        """Update order status."""
        try:
            order_uuid = uuid.UUID(order_id)
            result = await self.session.execute(
                select(OrderModel)
                .options(selectinload(OrderModel.items))
                .where(OrderModel.id == order_uuid)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            model.status = status
            await self.session.commit()
            await self.session.refresh(model)
            return self._to_entity(model)
        except ValueError:
            logger.warning(f"Invalid order_id format: {order_id}")
            return None
        except Exception as e:
            logger.error(f"Error updating status for order {order_id}: {e}")
            await self.session.rollback()
            raise

    async def get_tracking_info(self, order_id: str) -> dict | None:
        """Get order tracking information."""
        try:
            order_uuid = uuid.UUID(order_id)
            result = await self.session.execute(
                select(OrderModel).where(OrderModel.id == order_uuid)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            return {
                "order_id": str(model.id),
                "order_number": model.order_number,
                "status": model.status,
                "tracking_number": model.tracking_number,
                "shipping_method": model.shipping_method,
                "expected_delivery": model.expected_delivery.isoformat() if model.expected_delivery else None,
                "delivered_at": model.delivered_at.isoformat() if model.delivered_at else None,
            }
        except ValueError:
            logger.warning(f"Invalid order_id format: {order_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting tracking info for order {order_id}: {e}")
            raise

    # Additional useful methods

    async def get_by_order_number(self, order_number: str) -> Order | None:
        """Get order by order number."""
        result = await self.session.execute(
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(OrderModel.order_number == order_number)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_status(self, status: str, limit: int = 100) -> list[Order]:
        """Find orders by status."""
        result = await self.session.execute(
            select(OrderModel)
            .options(selectinload(OrderModel.items))
            .where(OrderModel.status == status)
            .order_by(OrderModel.order_date.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count_by_customer(self, customer_id: uuid.UUID) -> int:
        """Count orders for a customer."""
        result = await self.session.execute(
            select(func.count()).where(OrderModel.customer_id == customer_id)
        )
        return result.scalar_one()

    async def delete(self, order_id: uuid.UUID) -> bool:
        """Delete an order."""
        result = await self.session.execute(
            select(OrderModel).where(OrderModel.id == order_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    # Mapping methods

    def _to_entity(self, model: OrderModel) -> Order:
        """Convert model to entity."""
        # Convert items
        items = []
        for item_model in model.items:
            items.append(
                OrderItem(
                    product_id=0,  # UUID to int not possible, use 0 as placeholder
                    product_name=item_model.product_name,
                    sku=item_model.product_sku,
                    quantity=item_model.quantity,
                    unit_price=Price.from_float(item_model.unit_price),
                )
            )

        # Map status strings to enums
        try:
            order_status = OrderStatus(model.status)
        except ValueError:
            order_status = OrderStatus.PENDING

        try:
            payment_status = PaymentStatus(model.payment_status) if model.payment_status else PaymentStatus.PENDING
        except ValueError:
            payment_status = PaymentStatus.PENDING

        order = Order(
            customer_id=0,  # UUID to int not possible
            customer_name="",
            items=items,
            status=order_status,
            payment_status=payment_status,
            subtotal=Price.from_float(model.subtotal or 0),
            shipping_cost=Price.from_float(model.shipping_amount or 0),
            tax_amount=Price.from_float(model.tax_amount or 0),
            discount_amount=Price.from_float(model.discount_amount or 0),
            total=Price.from_float(model.total_amount or 0),
            payment_method=model.payment_method,
            payment_id=model.payment_reference,
            shipping_method=model.shipping_method,
            tracking_number=model.tracking_number,
            estimated_delivery=model.expected_delivery,
            delivered_at=model.delivered_at,
            customer_notes=model.notes,
            internal_notes=model.internal_notes,
            order_number=model.order_number,
        )

        # Set ID using uuid string stored as internal attribute
        order._db_id = model.id  # Store UUID for reference

        if model.created_at:
            order.created_at = model.created_at
        if model.updated_at:
            order.updated_at = model.updated_at

        return order

    def _to_model(self, order: Order) -> OrderModel:
        """Convert entity to model."""
        # Generate order number if not set
        order_number = order.order_number or f"ORD-{uuid.uuid4().hex[:8].upper()}"

        model = OrderModel(
            order_number=order_number,
            customer_id=uuid.uuid4(),  # Need actual customer UUID
            status=order.status.value,
            subtotal=float(order.subtotal.amount),
            total_amount=float(order.total.amount),
            tax_amount=float(order.tax_amount.amount),
            shipping_amount=float(order.shipping_cost.amount),
            discount_amount=float(order.discount_amount.amount),
            payment_status=order.payment_status.value,
            payment_method=order.payment_method,
            payment_reference=order.payment_id,
            shipping_method=order.shipping_method,
            tracking_number=order.tracking_number,
            expected_delivery=order.estimated_delivery,
            delivered_at=order.delivered_at,
            notes=order.customer_notes,
            internal_notes=order.internal_notes,
        )

        # Convert items
        for item in order.items:
            item_model = OrderItemModel(
                product_id=uuid.uuid4(),  # Need actual product UUID
                quantity=item.quantity,
                unit_price=float(item.unit_price.amount),
                total_price=float(item.subtotal.amount),
                product_name=item.product_name,
                product_sku=item.sku,
            )
            model.items.append(item_model)

        return model
