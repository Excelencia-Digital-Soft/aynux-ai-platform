"""
Conversation and messaging models
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from .base import Base

if TYPE_CHECKING:
    from .customers import Customer


class Conversation(Base):
    """Conversaciones del chatbot"""

    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    session_id = Column(String(100), index=True)  # Para agrupar mensajes de una sesión

    # Conversation metadata
    total_messages = Column(Integer, default=0)
    user_messages = Column(Integer, default=0)
    bot_messages = Column(Integer, default=0)
    intent_detected = Column(String(100))  # gaming, price_inquiry, support
    products_shown = Column(JSONB)  # IDs de productos mostrados
    conversion_stage = Column(String(50))  # inquiry, interested, qualified, closed

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation")


class Message(Base):
    """Mensajes individuales"""

    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_phone = Column(String, nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    message_type = Column(String(20), nullable=False)  # user, bot, system
    content = Column(Text, nullable=False)
    intent = Column(String(100))  # Intención detectada
    confidence = Column(Float)  # Confianza en la detección de intención

    # WhatsApp specific
    whatsapp_message_id = Column(String(100), unique=True, index=True)
    message_format = Column(String(20))  # text, image, document, interactive

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
