"""
Modelos de datos para el sistema multi-agente (sin herencia de MessagesState)
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CustomerContext(BaseModel):
    """Contexto del cliente para personalización"""

    customer_id: str
    name: str
    email: Optional[str] = None
    phone: str
    tier: Literal["basic", "premium", "vip"] = "basic"
    purchase_history: List[Dict[str, Any]] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Obtiene una preferencia del cliente"""
        return self.preferences.get(key, default)

    def is_premium(self) -> bool:
        """Verifica si el cliente es premium o VIP"""
        return self.tier in ["premium", "vip"]

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "tier": self.tier,
            "purchase_history": self.purchase_history,
            "preferences": self.preferences,
        }


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


class IntentInfo(BaseModel):
    """Información de intención detectada"""

    primary_intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    requires_handoff: bool = False
    target_agent: Optional[str] = None
    detected_at: datetime = Field(default_factory=datetime.now)

    def is_confident(self, threshold: float = 0.7) -> bool:
        """Verifica si la detección tiene confianza suficiente"""
        return self.confidence >= threshold

    def get_entity(self, key: str, default: Any = None) -> Any:
        """Obtiene una entidad extraída"""
        return self.entities.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "primary_intent": self.primary_intent,
            "confidence": self.confidence,
            "entities": self.entities,
            "requires_handoff": self.requires_handoff,
            "target_agent": self.target_agent,
            "detected_at": self.detected_at.isoformat(),
        }


class IntentPattern(BaseModel):
    """Patrón para detección de intenciones"""

    intent: str
    keywords: List[str] = Field(default_factory=list)
    patterns: List[str] = Field(default_factory=list)
    confidence_boost: float = 0.0

    def matches(self, text: str) -> bool:
        """Verifica si el patrón coincide con el texto"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.keywords)


class AgentResponse(BaseModel):
    """Respuesta generada por un agente"""

    agent_name: str
    response_text: str
    data_retrieved: Dict[str, Any] = Field(default_factory=dict)
    tools_used: List[str] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    def add_tool_used(self, tool_name: str):
        """Añade una herramienta usada"""
        if tool_name not in self.tools_used:
            self.tools_used.append(tool_name)

    def set_processing_time(self, start_time: datetime):
        """Calcula y establece el tiempo de procesamiento"""
        self.processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para compatibilidad con TypedDict"""
        return {
            "agent_name": self.agent_name,
            "response_text": self.response_text,
            "data_retrieved": self.data_retrieved,
            "tools_used": self.tools_used,
            "processing_time_ms": self.processing_time_ms,
            "success": self.success,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }
