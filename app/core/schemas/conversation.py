from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class ConversationContext(BaseModel):
    """Contexto de la conversación actual"""

    conversation_id: str
    session_id: str
    channel: Literal["whatsapp", "web", "api"] = "whatsapp"
    language: str = "es"
    timezone: str = "America/Buenos_Aires"
    started_at: datetime = Field(default_factory=datetime.now)

    def duration_seconds(self) -> float:
        """Calcula la duración de la conversación en segundos"""
        return (datetime.now() - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "channel": self.channel,
            "language": self.language,
            "timezone": self.timezone,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": self.duration_seconds(),
        }
