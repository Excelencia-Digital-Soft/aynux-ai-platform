import uuid

from sqlalchemy import Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..database import TimestampMixin

Base = declarative_base()


class ConversationMessage(Base, TimestampMixin):
    """Mensajes individuales de las conversaciones."""

    __tablename__ = "conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)

    # Contenido del mensaje
    message_type = Column(String(50), default="text", nullable=False)  # text, image, audio, file
    content = Column(Text, nullable=False)
    sender_type = Column(String(50), nullable=False)  # customer, agent, system
    agent_name = Column(String(100))  # Nombre del agente que respondió

    # Metadatos específicos del mensaje
    meta_data = Column(JSONB, default=dict)
    external_id = Column(String(255))  # ID del mensaje en el sistema externo (WhatsApp, etc.)

    # Relaciones
    conversation = relationship("Conversation", back_populates="messages")

    # Índices
    __table_args__ = (
        Index("idx_conversation_messages_conversation", conversation_id),
        Index("idx_conversation_messages_type", message_type),
        Index("idx_conversation_messages_sender", sender_type),
        Index("idx_conversation_messages_external", external_id),
    )
