"""
Product review models
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .catalog import Product
    from .customers import Customer


class ProductReview(Base, TimestampMixin):
    """Reviews y calificaciones de productos"""

    __tablename__ = "product_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(200))
    customer_phone = Column(String(20))  # Para identificar cliente de WhatsApp
    rating = Column(Integer, nullable=False)  # 1-5 estrellas
    review_text = Column(Text)
    verified_purchase = Column(Boolean, default=False)
    helpful_votes = Column(Integer, default=0)

    active = Column(Boolean, default=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product")
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="reviews")
