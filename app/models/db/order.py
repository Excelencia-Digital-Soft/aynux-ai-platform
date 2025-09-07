import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..database import TimestampMixin

Base = declarative_base()


class Order(Base, TimestampMixin):
    """Órdenes de compra."""

    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)

    # Información de la orden
    status = Column(String(50), default="pending", nullable=False)  # pending, confirmed, shipped, delivered, cancelled
    total_amount = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0)
    shipping_amount = Column(Numeric(10, 2), default=0)
    discount_amount = Column(Numeric(10, 2), default=0)

    # Fechas importantes
    order_date = Column(DateTime, default=datetime.now(timezone.utc), nullable=False)
    shipped_date = Column(DateTime)
    delivered_date = Column(DateTime)

    # Información de envío
    shipping_address = Column(JSONB)
    billing_address = Column(JSONB)

    # Metadatos
    meta_data = Column(JSONB, default=dict)

    # Relaciones
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    # Índices
    __table_args__ = (
        Index("idx_orders_customer", customer_id),
        Index("idx_orders_status", status),
        Index("idx_orders_date", order_date),
        Index("idx_orders_total", total_amount),
        CheckConstraint("total_amount >= 0", name="check_total_positive"),
    )

    def __repr__(self):
        return f"<Order(number='{self.order_number}', status='{self.status}', total={self.total_amount})>"


class OrderItem(Base, TimestampMixin):
    """Items de una orden."""

    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    # Snapshot de información del producto al momento de la compra
    product_name = Column(String(300), nullable=False)
    product_sku = Column(String(100))
    product_metadata = Column(JSONB, default=dict)

    # Relaciones
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    # Índices
    __table_args__ = (
        Index("idx_order_items_order", order_id),
        Index("idx_order_items_product", product_id),
        CheckConstraint("quantity > 0", name="check_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="check_unit_price_positive"),
    )
