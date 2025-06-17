"""
Order management models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .catalog import Product
    from .customers import Customer


class Order(Base, TimestampMixin):
    """Órdenes de compra"""

    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    
    # Order details
    status = Column(String(20), nullable=False, default="pending")  # pending, confirmed, processing, shipped, delivered, cancelled
    subtotal = Column(Float, nullable=False, default=0)
    total_amount = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0)
    shipping_amount = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    
    # Payment
    payment_status = Column(String(20), default="pending")  # pending, paid, failed, refunded
    payment_method = Column(String(50))  # cash, card, transfer, etc.
    payment_reference = Column(String(100))
    
    # Shipping
    shipping_address = Column(JSONB)  # {"street": "...", "city": "...", "zip": "..."}
    shipping_method = Column(String(50))  # standard, express, pickup
    tracking_number = Column(String(100))
    
    # Timestamps
    order_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expected_delivery = Column(DateTime)
    delivered_at = Column(DateTime)
    
    # Notes
    notes = Column(Text)
    internal_notes = Column(Text)
    
    # Metadatos adicionales
    meta_data = Column(JSONB, default=dict)
    
    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    
    # Índices
    __table_args__ = (
        Index("idx_orders_customer", customer_id),
        Index("idx_orders_status", status),
        Index("idx_orders_date", order_date),
        Index("idx_orders_payment_status", payment_status),
        Index("idx_orders_customer_status_date", customer_id, status, order_date),
    )
    
    def __repr__(self):
        return f"<Order(number='{self.order_number}', status='{self.status}', total={self.total_amount})>"
    
    @hybrid_property
    def is_completed(self) -> bool:
        """Verifica si la orden está completada."""
        return self.status == "delivered"
    
    @hybrid_property
    def is_cancelled(self) -> bool:
        """Verifica si la orden está cancelada."""
        return self.status == "cancelled"
    
    @hybrid_property
    def can_be_cancelled(self) -> bool:
        """Verifica si la orden puede ser cancelada."""
        return self.status in ["pending", "confirmed"]


class OrderItem(Base, TimestampMixin):
    """Items individuales de una orden"""

    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    
    # Item details
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)  # Precio al momento de la compra
    total_price = Column(Float, nullable=False)  # quantity * unit_price
    
    # Product info at time of purchase (for historical accuracy)
    product_name = Column(String(255), nullable=False)
    product_sku = Column(String(50))
    product_specs = Column(Text)
    
    # Metadatos adicionales
    meta_data = Column(JSONB, default=dict)
    
    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")
    
    # Índices
    __table_args__ = (
        Index("idx_order_items_order", order_id),
        Index("idx_order_items_product", product_id),
    )
    
    def __repr__(self):
        return f"<OrderItem(product='{self.product_name}', quantity={self.quantity}, price={self.unit_price})>"