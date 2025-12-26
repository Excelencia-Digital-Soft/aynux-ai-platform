"""
Incident Category model for dynamic incident categorization.

Categories can be hierarchical (parent_id) and include SLA configuration
and Jira issue type mapping for integration.
"""

import uuid
from typing import cast

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import SOPORTE_SCHEMA


class IncidentCategory(Base, TimestampMixin):
    """
    Dynamic incident categories with SLA and Jira mapping.

    Attributes:
        id: Unique identifier (UUID)
        code: Unique category code (TECNICO, FACTURACION, etc.)
        name: Display name
        description: Category description
        parent_id: Parent category for hierarchical structure
        sla_response_hours: SLA hours for initial response
        sla_resolution_hours: SLA hours for resolution
        jira_issue_type: Mapped Jira issue type (Bug, Task, Story, etc.)
        is_active: Whether category is active
        sort_order: Display order in lists
    """

    __tablename__ = "incident_categories"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Category identification
    code = Column(
        String(50),
        unique=True,
        nullable=False,
        comment="Unique category code (TECNICO, FACTURACION, etc.)",
    )
    name = Column(
        String(100),
        nullable=False,
        comment="Display name for the category",
    )
    description = Column(
        Text,
        nullable=True,
        comment="Category description",
    )

    # Hierarchy
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SOPORTE_SCHEMA}.incident_categories.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent category for hierarchical structure",
    )

    # SLA Configuration
    sla_response_hours = Column(
        Integer,
        nullable=True,
        default=24,
        comment="SLA hours for initial response",
    )
    sla_resolution_hours = Column(
        Integer,
        nullable=True,
        default=72,
        comment="SLA hours for resolution",
    )

    # Jira mapping
    jira_issue_type = Column(
        String(50),
        nullable=True,
        default="Bug",
        comment="Mapped Jira issue type (Bug, Task, Story, Improvement)",
    )

    # Status and ordering
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether category is active",
    )
    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order in lists",
    )

    # Relationships
    parent = relationship(
        "IncidentCategory",
        remote_side=[id],
        backref="children",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<IncidentCategory(code={self.code}, name={self.name})>"

    @property
    def full_name(self) -> str:
        """Return full hierarchical name."""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return cast(str, self.name)

    # Table configuration
    __table_args__ = (
        Index("idx_incident_category_code", code),
        Index("idx_incident_category_active", is_active),
        Index("idx_incident_category_parent", parent_id),
        {"schema": SOPORTE_SCHEMA},
    )
