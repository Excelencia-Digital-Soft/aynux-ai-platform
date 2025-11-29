"""
Order Repository Implementation

SQLAlchemy implementation of IOrderRepository.
"""

import logging
import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.ecommerce.application.ports import IOrderRepository
from app.domains.ecommerce.domain.entities.order import Order, OrderItem
from app.domains.ecommerce.domain.value_objects.order_status import (
    OrderStatus,
    PaymentStatus,
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

            setattr(model, "status", status)
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

            expected_dt = cast(datetime | None, model.expected_delivery)
            delivered_dt = cast(datetime | None, model.delivered_at)
            return {
                "order_id": str(model.id),
                "order_number": model.order_number,
                "status": model.status,
                "tracking_number": model.tracking_number,
                "shipping_method": model.shipping_method,
                "expected_delivery": expected_dt.isoformat() if expected_dt else None,
                "delivered_at": delivered_dt.isoformat() if delivered_dt else None,
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
        # Convert items - extract Python values from SQLAlchemy columns using cast
        items = []
        model_items = model.items or []
        for item_model in model_items:
            product_name = cast(str, item_model.product_name) or ""
            product_sku = cast(str | None, item_model.product_sku)
            quantity = cast(int, item_model.quantity) or 0
            unit_price_val = cast(float | None, item_model.unit_price) or 0.0

            items.append(
                OrderItem(
                    product_id=0,  # UUID to int not possible, use 0 as placeholder
                    product_name=product_name,
                    sku=product_sku,
                    quantity=quantity,
                    unit_price=Price.from_float(unit_price_val),
                )
            )

        # Map status strings to enums
        status_str = cast(str | None, model.status) or "pending"
        try:
            order_status = OrderStatus(status_str)
        except ValueError:
            order_status = OrderStatus.PENDING

        payment_status_str = cast(str | None, model.payment_status)
        try:
            payment_status = (
                PaymentStatus(payment_status_str) if payment_status_str else PaymentStatus.PENDING
            )
        except ValueError:
            payment_status = PaymentStatus.PENDING

        # Extract values from model columns using cast
        subtotal_val = cast(float | None, model.subtotal) or 0.0
        shipping_val = cast(float | None, model.shipping_amount) or 0.0
        tax_val = cast(float | None, model.tax_amount) or 0.0
        discount_val = cast(float | None, model.discount_amount) or 0.0
        total_val = cast(float | None, model.total_amount) or 0.0

        # Cast string fields
        payment_method = cast(str | None, model.payment_method)
        payment_ref = cast(str | None, model.payment_reference)
        shipping_method = cast(str | None, model.shipping_method)
        tracking_number = cast(str | None, model.tracking_number)
        notes = cast(str | None, model.notes)
        internal_notes = cast(str | None, model.internal_notes)
        order_number = cast(str | None, model.order_number)

        # Cast datetime fields
        expected_delivery = cast(datetime | None, model.expected_delivery)
        delivered_at = cast(datetime | None, model.delivered_at)
        created_at = cast(datetime | None, model.created_at)
        updated_at = cast(datetime | None, model.updated_at)

        order = Order(
            customer_id=0,  # UUID to int not possible
            customer_name="",
            items=items,
            status=order_status,
            payment_status=payment_status,
            subtotal=Price.from_float(subtotal_val),
            shipping_cost=Price.from_float(shipping_val),
            tax_amount=Price.from_float(tax_val),
            discount_amount=Price.from_float(discount_val),
            total=Price.from_float(total_val),
            payment_method=payment_method,
            payment_id=payment_ref,
            shipping_method=shipping_method,
            tracking_number=tracking_number,
            estimated_delivery=expected_delivery,
            delivered_at=delivered_at,
            customer_notes=notes,
            internal_notes=internal_notes,
            order_number=order_number,
        )

        # Store DB UUID in order's id field as int hash (for reference only)
        model_id = cast(uuid.UUID | None, model.id)
        if model_id is not None:
            uuid_int = int(model_id)  # Convert UUID to int
            order.id = uuid_int % (2**31)

        if created_at is not None:
            order.created_at = created_at
        if updated_at is not None:
            order.updated_at = updated_at

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
        if model.items is None:
            model.items = []
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
