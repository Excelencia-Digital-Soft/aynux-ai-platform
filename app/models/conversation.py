from datetime import datetime, timezone
from typing import ClassVar, List, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationMessage(BaseModel):
    """Modelo para un mensaje individual en una conversación"""

    role: Literal["persona", "bot", "system"]
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )


class ConversationHistory(BaseModel):
    """Modelo para el historial completo de conversación de un usuario"""

    user_id: str
    messages: List[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )

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

    def get_conversation_summary(self) -> str:
        """Obtiene un resumen de la conversación"""
        if not self.messages:
            return "No hay mensajes en la conversación"

        total_messages = len(self.messages)
        user_messages = len([msg for msg in self.messages if msg.role == "persona"])
        bot_messages = len([msg for msg in self.messages if msg.role == "bot"])

        return f"Conversación con {total_messages} mensajes: {user_messages} del usuario, {bot_messages} del bot"
