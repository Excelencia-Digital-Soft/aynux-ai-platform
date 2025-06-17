"""
Promotion and discount models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base
from .catalog import product_promotion_association

if TYPE_CHECKING:
    from .catalog import Product


class Promotion(Base):
    """Promociones y ofertas"""

    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    discount_percentage = Column(Float)  # 15.0 para 15%
    discount_amount = Column(Float)  # Descuento fijo en $
    promo_code = Column(String(50), unique=True, index=True)  # Código promocional

    # Validity
    valid_from = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime, nullable=False)
    max_uses = Column(Integer)  # Límite de usos
    current_uses = Column(Integer, default=0)

    # Conditions
    min_purchase_amount = Column(Float)  # Monto mínimo de compra
    applicable_categories = Column(JSONB)  # ["laptops", "gaming"]

    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    products: Mapped[List["Product"]] = relationship(
        "Product", secondary=product_promotion_association, back_populates="promotions"
    )

    @property
    def is_valid(self) -> bool:
        """Verifica si la promoción está vigente"""
        now = datetime.now(timezone.utc)
        return bool(
            self.active
            and self.valid_from <= now <= self.valid_until
            and (self.max_uses is None or self.current_uses < self.max_uses)
        )