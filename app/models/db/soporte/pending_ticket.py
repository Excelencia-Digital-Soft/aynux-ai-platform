"""
Pending Ticket model for conversational ticket creation flow.

Stores the state of tickets being created through the multi-step
conversation flow before they become actual incidents.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import Boolean, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..base import Base
from ..schemas import SOPORTE_SCHEMA

# Flow steps for ticket creation
FLOW_STEPS = ["description", "priority", "confirmation"]


class PendingTicket(Base):
    """
    Pending tickets being created through conversational flow.

    Stores intermediate state while user provides information
    through the multi-step ticket creation process.

    Attributes:
        id: Unique identifier (UUID)
        conversation_id: WhatsApp conversation ID
        user_phone: User's phone number
        current_step: Current step in the flow (description, priority, confirmation)
        collected_data: JSON with data collected so far
        started_at: When the flow started
        expires_at: When the pending ticket expires (30 min default)
        is_active: Whether this pending ticket is still active
    """

    __tablename__ = "pending_tickets"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Conversation identification
    conversation_id = Column(
        String(255),
        nullable=False,
        comment="WhatsApp conversation ID",
    )
    user_phone = Column(
        String(50),
        nullable=False,
        comment="User's phone number",
    )

    # Flow state
    current_step = Column(
        String(50),
        nullable=False,
        default="description",
        comment="Current step: description, priority, confirmation",
    )

    # Collected data
    collected_data = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Data collected so far: {description, priority, category_code, etc.}",
    )

    # Timestamps
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="When the ticket creation flow started",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC) + timedelta(minutes=30),
        comment="When this pending ticket expires (30 min default)",
    )

    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this pending ticket is still active",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<PendingTicket(conv={self.conversation_id}, step={self.current_step}, active={self.is_active})>"

    @staticmethod
    def _ensure_utc(dt: datetime | None) -> datetime:
        """Normalize datetime to UTC-aware.

        Handles both naive datetimes (from legacy DB) and aware datetimes.
        """
        if dt is None:
            return datetime.now(UTC)
        if dt.tzinfo is None:
            # Naive datetime from DB - assume UTC and make aware
            return dt.replace(tzinfo=UTC)
        return dt

    @property
    def is_expired(self) -> bool:
        """Check if the pending ticket has expired."""
        expires_at_utc = self._ensure_utc(cast(datetime, self.expires_at))
        return datetime.now(UTC) > expires_at_utc

    @property
    def description(self) -> str | None:
        """Get collected description."""
        return self.collected_data.get("description") if self.collected_data else None

    @property
    def priority(self) -> str | None:
        """Get collected priority."""
        return self.collected_data.get("priority") if self.collected_data else None

    @property
    def category_code(self) -> str:
        """Get collected category code or default."""
        if self.collected_data:
            return self.collected_data.get("category_code", "GENERAL")
        return "GENERAL"

    def set_description(self, description: str) -> None:
        """Set description and advance to next step."""
        data = cast(dict[str, Any], self.collected_data) if self.collected_data else {}
        data["description"] = description
        self.collected_data = data
        self.current_step = "priority"

    def set_priority(self, priority: str) -> None:
        """Set priority and advance to confirmation step."""
        data = cast(dict[str, Any], self.collected_data) if self.collected_data else {}
        data["priority"] = priority
        self.collected_data = data
        self.current_step = "confirmation"

    def reset_to_description(self) -> None:
        """Reset flow back to description step."""
        self.collected_data = {}
        self.current_step = "description"

    def deactivate(self) -> None:
        """Mark pending ticket as inactive (completed or cancelled)."""
        self.is_active = False

    def extend_expiration(self, minutes: int = 30) -> None:
        """Extend the expiration time."""
        self.expires_at = datetime.now(UTC) + timedelta(minutes=minutes)

    # Table configuration
    __table_args__ = (
        Index("idx_pending_tickets_conversation_id", conversation_id),
        Index("idx_pending_tickets_user_phone", user_phone),
        Index("idx_pending_tickets_active", is_active),
        Index("idx_pending_tickets_expires", expires_at),
        {"schema": SOPORTE_SCHEMA},
    )
