"""
Excelencia Domain SQLAlchemy Models

Database models for Excelencia ERP domain persistence.
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database.setup import Base


class ErpModuleModel(Base):
    """SQLAlchemy model for ERP Module entity."""

    __tablename__ = "erp_modules"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)  # e.g., 'FIN-001'
    name = Column(String(100), nullable=False)  # Internal name
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # finance, inventory, sales, etc.
    status = Column(String(30), nullable=False, default="active")  # active, beta, coming_soon, deprecated
    features = Column(JSONB, default=list)
    pricing_tier = Column(String(50), default="standard")  # standard, premium, enterprise

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    demo_requests = relationship("DemoModel", back_populates="module")


class DemoModel(Base):
    """SQLAlchemy model for Demo entity."""

    __tablename__ = "demos"

    id = Column(Integer, primary_key=True, index=True)

    # Request information (embedded DemoRequest value object)
    company_name = Column(String(200), nullable=False)
    contact_name = Column(String(200), nullable=False)
    contact_email = Column(String(200), nullable=False, index=True)
    contact_phone = Column(String(50), nullable=True)
    modules_of_interest = Column(JSONB, default=list)  # List of module codes
    demo_type = Column(String(50), default="general")  # general, module_specific, technical, executive
    request_notes = Column(Text, nullable=True)

    # Scheduling
    scheduled_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=60)
    assigned_to = Column(String(200), nullable=True)
    meeting_link = Column(String(500), nullable=True)

    # Status: pending, scheduled, completed, cancelled, no_show
    status = Column(String(30), nullable=False, default="pending", index=True)

    # Optional module reference (for module-specific demos)
    module_id = Column(Integer, ForeignKey("erp_modules.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    module = relationship("ErpModuleModel", back_populates="demo_requests")
