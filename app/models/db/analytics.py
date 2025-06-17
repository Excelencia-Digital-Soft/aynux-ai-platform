"""
Analytics and tracking models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base

if TYPE_CHECKING:
    from .catalog import Product


class Analytics(Base):
    """Analytics y métricas del chatbot"""

    __tablename__ = "analytics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_data = Column(JSONB)  # Datos adicionales
    period_type = Column(String(20))  # daily, weekly, monthly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PriceHistory(Base):
    """Historial de precios para analytics"""

    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    change_reason = Column(String(100))  # promotion, market_change, cost_update
    notes = Column(Text)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    product: Mapped["Product"] = relationship("Product")


class StockMovement(Base):
    """Movimientos de inventario"""

    __tablename__ = "stock_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    movement_type = Column(String(20), nullable=False)  # in, out, adjustment
    quantity = Column(Integer, nullable=False)
    previous_stock = Column(Integer, nullable=False)
    new_stock = Column(Integer, nullable=False)
    reason = Column(String(100))  # sale, restock, damaged, adjustment
    notes = Column(Text)
    reference_number = Column(String(100))  # Número de orden, factura, etc.

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(100))  # Usuario que hizo el movimiento

    # Relationships
    product: Mapped["Product"] = relationship("Product")