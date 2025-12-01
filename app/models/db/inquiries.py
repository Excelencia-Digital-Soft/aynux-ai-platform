"""
Product inquiry models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base
from .schemas import ECOMMERCE_SCHEMA

if TYPE_CHECKING:
    from .catalog import Category, Product
    from .customers import Customer


class ProductInquiry(Base):
    """Consultas específicas sobre productos"""

    __tablename__ = "product_inquiries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey(f"{ECOMMERCE_SCHEMA}.customers.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey(f"{ECOMMERCE_SCHEMA}.products.id"))
    category_id = Column(UUID(as_uuid=True), ForeignKey(f"{ECOMMERCE_SCHEMA}.categories.id"))

    inquiry_type = Column(String(50), nullable=False)  # price, specs, availability, comparison
    inquiry_text = Column(Text)
    budget_mentioned = Column(Float)
    urgency = Column(String(20))  # low, medium, high
    status = Column(String(20), default="open")  # open, responded, closed

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    responded_at = Column(DateTime)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="inquiries")
    product: Mapped[Optional["Product"]] = relationship("Product")
    category: Mapped[Optional["Category"]] = relationship("Category")

    __table_args__ = ({"schema": ECOMMERCE_SCHEMA},)
