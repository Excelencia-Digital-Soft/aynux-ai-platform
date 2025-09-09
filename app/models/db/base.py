"""
Base models and mixins for the database
"""

from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class TimestampMixin:
    """Mixin para agregar timestamps automáticos."""

    # Using naive datetimes for PostgreSQL TIMESTAMP WITHOUT TIME ZONE compatibility
    created_at = Column(DateTime, default=lambda: datetime.now(), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(),
        onupdate=lambda: datetime.now(),
        nullable=False,
    )