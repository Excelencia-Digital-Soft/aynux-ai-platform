"""
SQLAlchemy models for conversation history management.

Tables in schema 'core':
- conversation_contexts: Stores rolling summaries and metadata
- conversation_messages: Stores individual messages for history retrieval
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.db.base import Base, TimestampMixin


class ConversationContext(Base, TimestampMixin):
    """
    Stores conversation context with rolling summary.

    This table maintains the LLM-generated rolling summary and metadata
    for each conversation, enabling context injection across all agents.
    """

    __tablename__ = "conversation_contexts"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identification
    conversation_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique identifier for the conversation (e.g., whatsapp_{phone})",
    )
    organization_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Multi-tenancy: organization that owns this conversation",
    )
    pharmacy_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Pharmacy that owns this conversation (for multi-pharmacy orgs)",
    )
    user_phone = Column(
        String(50),
        nullable=True,
        index=True,
        comment="User phone number for WhatsApp conversations",
    )

    # Context data
    rolling_summary = Column(
        Text,
        nullable=True,
        comment="LLM-generated rolling summary of the conversation",
    )
    topic_history = Column(
        JSONB,
        nullable=False,
        default=[],
        server_default="[]",
        comment="List of topics discussed in the conversation",
    )
    key_entities = Column(
        JSONB,
        nullable=False,
        default={},
        server_default="{}",
        comment="Key entities mentioned (names, products, preferences)",
    )

    # Tracking metrics
    total_turns = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Total number of conversation turns",
    )
    last_user_message = Column(
        Text,
        nullable=True,
        comment="Last message from user for quick access",
    )
    last_bot_response = Column(
        Text,
        nullable=True,
        comment="Last response from assistant for quick access",
    )

    # Extra context data
    extra_data = Column(
        JSONB,
        nullable=False,
        default={},
        server_default="{}",
        comment="Additional context data (channel, language, etc.)",
    )

    # Activity tracking
    last_activity_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
        comment="Last activity timestamp for cleanup queries",
    )

    # Relationships
    messages = relationship(
        "ConversationMessage",
        back_populates="context",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ConversationContext(id={self.conversation_id}, turns={self.total_turns})>"


class ConversationMessage(Base):
    """
    Stores individual conversation messages.

    Each message is linked to a ConversationContext and includes
    sender type, content, and optional agent attribution.
    """

    __tablename__ = "conversation_messages"
    __table_args__ = {"schema": "core"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign key to context
    conversation_id = Column(
        String(255),
        ForeignKey("core.conversation_contexts.conversation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to conversation_contexts.conversation_id",
    )

    # Message content
    sender_type = Column(
        Enum("user", "assistant", "system", name="sender_type_enum"),
        nullable=False,
        index=True,
        comment="Who sent the message: user, assistant, or system",
    )
    content = Column(
        Text,
        nullable=False,
        comment="Message content",
    )
    agent_name = Column(
        String(100),
        nullable=True,
        comment="Name of agent that generated response (for assistant messages)",
    )

    # Extra message data
    extra_data = Column(
        JSONB,
        nullable=False,
        default={},
        server_default="{}",
        comment="Additional message data (intent, confidence, etc.)",
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    # Relationships
    context = relationship("ConversationContext", back_populates="messages")

    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id}, sender={self.sender_type})>"
