from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """Modelo para un mensaje individual en una conversación"""

    role: Literal["persona", "bot", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationHistory(BaseModel):
    """Modelo para el historial completo de conversación de un usuario"""

    user_id: str
    messages: List[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_message(self, role: Literal["persona", "bot", "system"], content: str) -> None:
        """Añade un mensaje al historial"""
        message = ConversationMessage(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_last_messages(self, count: int = 10) -> List[ConversationMessage]:
        """Obtiene los últimos N mensajes"""
        return self.messages[-count:] if len(self.messages) > count else self.messages

    def to_formatted_history(self) -> str:
        """Convierte el historial a string formateado"""
        return "\n".join([f"{msg.role}: {msg.content}" for msg in self.messages])

