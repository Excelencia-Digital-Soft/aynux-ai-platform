"""
Customer management models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .conversations import Conversation
    from .inquiries import ProductInquiry
    from .orders import Order


class Customer(Base, TimestampMixin):
    """Clientes del chatbot"""

    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200))
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    profile_name = Column(String(200))  # Nombre del perfil de WhatsApp

    # Información adicional
    date_of_birth = Column(DateTime)
    gender = Column(String(10))

    # Customer analytics
    total_interactions = Column(Integer, default=0)
    total_inquiries = Column(Integer, default=0)
    interests = Column(JSONB)  # ["gaming", "work", "components"]
    preferences = Column(JSONB, default=dict)  # Preferencias generales del cliente
    meta_data = Column(JSONB, default=dict)
    budget_range = Column(String(50))  # "1000-1500", "1500-3000"
    preferred_brands = Column(JSONB)  # ["ASUS", "MSI"]

    # Status
    active = Column(Boolean, default=True)
    blocked = Column(Boolean, default=False)
    vip = Column(Boolean, default=False)

    first_contact = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_contact = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="customer")
    inquiries: Mapped[List["ProductInquiry"]] = relationship("ProductInquiry", back_populates="customer")
    reviews = relationship("ProductReview", back_populates="customer")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer")

    # Índices
    __table_args__ = (
        Index("idx_customers_active", active),
        Index("idx_customers_name", first_name, last_name),
    )

    def __repr__(self):
        return f"<Customer(phone='{self.phone_number}', name='{self.first_name} {self.last_name}')>"

    @hybrid_property
    def full_name(self) -> str:
        """Nombre completo del cliente."""
        names = [name for name in [self.first_name, self.last_name] if name]  # type: ignore
        return " ".join(names) if names else (self.phone_number or "")  # type: ignore

