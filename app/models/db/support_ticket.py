"""
Support Ticket model for tracking incidents and feedback from users.

This module contains the SupportTicket model for storing user-reported issues,
feedback, questions, and suggestions captured through the chat interface.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA

# Ticket type enum values
TICKET_TYPES = ["incident", "feedback", "question", "suggestion"]

# Ticket status enum values
TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"]

# Ticket priority enum values
TICKET_PRIORITIES = ["low", "medium", "high", "critical"]


class SupportTicket(Base, TimestampMixin):
    """
    Support tickets created by users via chat.

    Stores incidents, feedback, questions, and suggestions from users
    interacting with the Excelencia ERP support agent.

    Attributes:
        id: Unique ticket identifier (UUID)
        user_phone: WhatsApp phone number of the user
        user_name: Name of the user (if known)
        conversation_id: Link to the conversation where ticket was created
        ticket_type: Type of ticket (incident, feedback, question, suggestion)
        category: Category (tecnico, facturacion, capacitacion, etc.)
        module: Affected module if applicable
        subject: Brief subject/title of the ticket
        description: Full description of the issue/feedback
        status: Ticket status (open, in_progress, resolved, closed)
        priority: Ticket priority (low, medium, high, critical)
        resolution: Resolution notes when ticket is resolved
        resolved_at: Timestamp when ticket was resolved
        resolved_by: Name/ID of person who resolved the ticket
        meta_data: Additional context from chat
    """

    __tablename__ = "support_tickets"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
        comment="Link to the conversation where ticket was created",
    )

    # Ticket content
    ticket_type = Column(
        ENUM(*TICKET_TYPES, name="ticket_type_enum"),
        nullable=False,
        comment="Type of ticket: incident, feedback, question, suggestion",
    )
    category = Column(
        String(100),
        nullable=True,
        comment="Category: tecnico, facturacion, capacitacion, etc.",
    )
    module = Column(
        String(100),
        nullable=True,
        comment="Affected module if applicable",
    )
    subject = Column(
        String(500),
        nullable=False,
        comment="Brief subject/title of the ticket",
    )
    description = Column(
        Text,
        nullable=False,
        comment="Full description of the issue/feedback",
    )

    # Status and tracking
    status = Column(
        ENUM(*TICKET_STATUSES, name="ticket_status_enum"),
        nullable=False,
        default="open",
        comment="Ticket status: open, in_progress, resolved, closed",
    )
    priority = Column(
        ENUM(*TICKET_PRIORITIES, name="ticket_priority_enum"),
        nullable=False,
        default="medium",
        comment="Ticket priority: low, medium, high, critical",
    )

    # Resolution
    resolution = Column(
        Text,
        nullable=True,
        comment="Resolution notes when ticket is resolved",
    )
    resolved_at = Column(
        DateTime,
        nullable=True,
        comment="Timestamp when ticket was resolved",
    )
    resolved_by = Column(
        String(200),
        nullable=True,
        comment="Name/ID of person who resolved the ticket",
    )

    # Metadata
    meta_data = Column(
        JSONB,
        default=dict,
        comment="Additional context from chat (message history, etc.)",
    )

    def __repr__(self) -> str:
        """String representation of the support ticket."""
        return f"<SupportTicket(id={self.id}, type={self.ticket_type}, status={self.status}, subject='{self.subject[:30]}...')>"

    def resolve(self, resolution: str, resolved_by: str | None = None) -> None:
        """Mark the ticket as resolved."""
        self.status = "resolved"
        self.resolution = resolution
        self.resolved_at = datetime.now()
        self.resolved_by = resolved_by

    def close(self) -> None:
        """Close the ticket."""
        self.status = "closed"

    @property
    def is_open(self) -> bool:
        """Check if the ticket is open."""
        return self.status in ("open", "in_progress")

    @property
    def ticket_id_short(self) -> str:
        """Return a short version of the ticket ID for display."""
        return str(self.id)[:8].upper()

    # Table-level configuration
    __table_args__ = (
        Index("idx_ticket_status", status),
        Index("idx_ticket_user_phone", user_phone),
        Index("idx_ticket_type", ticket_type),
        Index("idx_ticket_priority", priority),
        Index("idx_ticket_created_at", "created_at"),
        {"schema": CORE_SCHEMA},
    )
