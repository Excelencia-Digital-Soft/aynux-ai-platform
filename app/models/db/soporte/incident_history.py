"""
Incident History model for tracking changes to incidents.

Stores audit trail of all field changes with old and new values.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..base import Base
from ..schemas import SOPORTE_SCHEMA


class IncidentHistory(Base):
    """
    Change history for incidents (audit trail).

    Attributes:
        id: Unique identifier (UUID)
        incident_id: FK to incident
        field_changed: Name of the field that changed
        old_value: Previous value
        new_value: New value
        changed_by: Who made the change
        changed_at: When the change was made
    """

    __tablename__ = "incident_history"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Incident reference
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SOPORTE_SCHEMA}.incidents.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to incident",
    )

    # Change details
    field_changed = Column(
        String(100),
        nullable=False,
        comment="Name of the field that changed",
    )
    old_value = Column(
        Text,
        nullable=True,
        comment="Previous value (as string)",
    )
    new_value = Column(
        Text,
        nullable=True,
        comment="New value (as string)",
    )

    # Audit info
    changed_by = Column(
        String(200),
        nullable=True,
        comment="Who made the change (user, agent, system)",
    )
    changed_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(),
        comment="When the change was made",
    )

    # Relationships
    incident = relationship("Incident", backref="history")

    def __repr__(self) -> str:
        """String representation."""
        return f"<IncidentHistory(incident_id={self.incident_id}, field={self.field_changed}, at={self.changed_at})>"

    # Table configuration
    __table_args__ = (
        Index("idx_incident_history_incident_id", incident_id),
        Index("idx_incident_history_changed_at", changed_at),
        Index("idx_incident_history_field", field_changed),
        {"schema": SOPORTE_SCHEMA},
    )
