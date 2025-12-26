"""
Incident model for the support/incidents system.

Main table for storing all incidents, feedback, questions and suggestions.
Includes fields for Jira integration and SLA tracking.
"""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA, SOPORTE_SCHEMA

# Incident type enum values
INCIDENT_TYPES = ["incident", "feedback", "question", "suggestion"]

# Incident status enum values
INCIDENT_STATUSES = ["draft", "open", "in_progress", "pending_info", "resolved", "closed"]

# Incident priority enum values
INCIDENT_PRIORITIES = ["low", "medium", "high", "critical"]

# Incident urgency enum values
INCIDENT_URGENCIES = ["low", "medium", "high"]

# Impact levels
INCIDENT_IMPACTS = ["individual", "group", "department", "organization"]

# Source channels
INCIDENT_SOURCES = ["whatsapp", "email", "phone", "web"]

# Jira sync status
JIRA_SYNC_STATUSES = ["pending", "synced", "error", "manual"]


class Incident(Base, TimestampMixin):
    """
    Main incident/ticket table for the support system.

    Attributes:
        id: Unique identifier (UUID)
        folio: Human-readable folio (INC-2024-00001)
        organization_id: Optional link to organization (multi-tenant)
        user_phone: WhatsApp phone number
        user_name: User's name
        conversation_id: Link to conversation
        incident_type: Type (incident, feedback, question, suggestion)
        category_id: FK to IncidentCategory
        description: Full description
        priority: Priority level
        status: Current status
        ... (Jira fields, resolution fields, SLA fields)
    """

    __tablename__ = "incidents"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folio = Column(
        String(20),
        unique=True,
        nullable=False,
        comment="Human-readable folio (INC-2024-00001)",
    )

    # Multi-tenant support (optional)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Organization for multi-tenant isolation",
    )

    # User information
    user_phone = Column(
        String(50),
        nullable=False,
        comment="WhatsApp phone number of the user",
    )
    user_name = Column(
        String(200),
        nullable=True,
        comment="Name of the user (if known)",
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Link to the conversation where incident was created",
    )

    # Incident classification
    incident_type = Column(
        ENUM(*INCIDENT_TYPES, name="soporte_incident_type_enum", schema=SOPORTE_SCHEMA),
        nullable=False,
        default="incident",
        comment="Type: incident, feedback, question, suggestion",
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{SOPORTE_SCHEMA}.incident_categories.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to incident category",
    )

    # Content
    subject = Column(
        String(500),
        nullable=True,
        comment="Brief subject/title (auto-generated if not provided)",
    )
    description = Column(
        Text,
        nullable=False,
        comment="Full description of the incident",
    )

    # Priority and impact
    priority = Column(
        ENUM(*INCIDENT_PRIORITIES, name="soporte_incident_priority_enum", schema=SOPORTE_SCHEMA),
        nullable=False,
        default="medium",
        comment="Priority: low, medium, high, critical",
    )
    urgency = Column(
        ENUM(*INCIDENT_URGENCIES, name="soporte_incident_urgency_enum", schema=SOPORTE_SCHEMA),
        nullable=True,
        default="medium",
        comment="Urgency: low, medium, high",
    )
    impact = Column(
        ENUM(*INCIDENT_IMPACTS, name="soporte_incident_impact_enum", schema=SOPORTE_SCHEMA),
        nullable=True,
        comment="Impact scope: individual, group, department, organization",
    )

    # Status
    status = Column(
        ENUM(*INCIDENT_STATUSES, name="soporte_incident_status_enum", schema=SOPORTE_SCHEMA),
        nullable=False,
        default="open",
        comment="Status: draft, open, in_progress, pending_info, resolved, closed",
    )
    source = Column(
        ENUM(*INCIDENT_SOURCES, name="soporte_incident_source_enum", schema=SOPORTE_SCHEMA),
        nullable=False,
        default="whatsapp",
        comment="Source channel: whatsapp, email, phone, web",
    )

    # Technical details (optional)
    environment = Column(
        String(100),
        nullable=True,
        comment="Environment: produccion, pruebas, desarrollo",
    )
    steps_to_reproduce = Column(
        Text,
        nullable=True,
        comment="Steps to reproduce the issue",
    )
    expected_behavior = Column(
        Text,
        nullable=True,
        comment="Expected behavior",
    )
    actual_behavior = Column(
        Text,
        nullable=True,
        comment="Actual/observed behavior",
    )
    attachments = Column(
        JSONB,
        default=list,
        comment="List of attachment URLs",
    )

    # Jira integration fields
    jira_issue_key = Column(
        String(50),
        nullable=True,
        comment="Jira issue key (PROJ-123)",
    )
    jira_issue_id = Column(
        String(50),
        nullable=True,
        comment="Jira internal issue ID",
    )
    jira_project_key = Column(
        String(20),
        nullable=True,
        comment="Jira project key",
    )
    jira_sync_status = Column(
        ENUM(*JIRA_SYNC_STATUSES, name="soporte_jira_sync_status_enum", schema=SOPORTE_SCHEMA),
        nullable=True,
        default="pending",
        comment="Jira sync status: pending, synced, error, manual",
    )
    jira_last_sync_at = Column(
        DateTime,
        nullable=True,
        comment="Last Jira synchronization timestamp",
    )
    jira_sync_error = Column(
        Text,
        nullable=True,
        comment="Last Jira sync error message",
    )

    # Resolution
    resolution = Column(
        Text,
        nullable=True,
        comment="Resolution notes",
    )
    resolution_type = Column(
        String(100),
        nullable=True,
        comment="Resolution type: fixed, workaround, cannot_reproduce, duplicate, wont_fix",
    )
    resolved_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp when incident was resolved",
    )
    resolved_by = Column(
        String(200),
        nullable=True,
        comment="Name/ID of person who resolved",
    )

    # SLA tracking
    sla_response_due = Column(
        DateTime,
        nullable=True,
        comment="SLA deadline for first response",
    )
    sla_resolution_due = Column(
        DateTime,
        nullable=True,
        comment="SLA deadline for resolution",
    )
    sla_response_met = Column(
        Boolean,
        nullable=True,
        comment="Whether SLA response was met",
    )
    sla_resolution_met = Column(
        Boolean,
        nullable=True,
        comment="Whether SLA resolution was met",
    )

    # Metadata
    meta_data = Column(
        JSONB,
        default=dict,
        comment="Additional context (chat history, query analysis, etc.)",
    )

    # Relationships
    category = relationship("IncidentCategory", backref="incidents")

    def __repr__(self) -> str:
        """String representation."""
        return f"<Incident(folio={self.folio}, type={self.incident_type}, status={self.status})>"

    def resolve(self, resolution: str, resolution_type: str = "fixed", resolved_by: str | None = None) -> None:
        """Mark the incident as resolved."""
        self.status = "resolved"
        self.resolution = resolution
        self.resolution_type = resolution_type
        self.resolved_at = datetime.now()
        self.resolved_by = resolved_by

    def close(self) -> None:
        """Close the incident."""
        self.status = "closed"

    @property
    def is_open(self) -> bool:
        """Check if the incident is still open."""
        return self.status in ("draft", "open", "in_progress", "pending_info")

    @property
    def folio_short(self) -> str:
        """Return the folio for display."""
        return cast(str, self.folio)

    # Table configuration
    __table_args__ = (
        Index("idx_incidents_folio", folio),
        Index("idx_incidents_status", status),
        Index("idx_incidents_user_phone", user_phone),
        Index("idx_incidents_organization_id", organization_id),
        Index("idx_incidents_jira_issue_key", jira_issue_key),
        Index("idx_incidents_created_at", "created_at"),
        Index("idx_incidents_priority", priority),
        Index("idx_incidents_category_id", category_id),
        {"schema": SOPORTE_SCHEMA},
    )
