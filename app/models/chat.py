"""
Modelos Pydantic para el endpoint de chat con LangGraph
"""

from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    """Tipos de eventos para streaming"""
    THINKING = "thinking"
    PROCESSING = "processing"
    GENERATING = "generating"
    COMPLETE = "complete"
    ERROR = "error"


class ChatMessageRequest(BaseModel):
    """Modelo para solicitud de mensaje de chat"""

    message: str = Field(..., description="Mensaje del usuario", min_length=1, max_length=5000)
    user_id: str = Field(..., description="ID único del usuario", min_length=1, max_length=100)
    session_id: Optional[str] = Field(None, description="ID de sesión para mantener contexto", max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos adicionales opcionales")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hola, ¿qué productos tienen disponibles?",
                "user_id": "user123",
                "session_id": "session456",
                "metadata": {"channel": "web", "locale": "es"},
            }
        }


class ChatMessageResponse(BaseModel):
    """Modelo para respuesta de mensaje de chat"""

    response: str = Field(..., description="Respuesta del bot")
    agent_used: str = Field(..., description="Agente que procesó el mensaje")
    session_id: str = Field(..., description="ID de sesión usado")
    status: Literal["success", "error"] = Field("success", description="Estado de la respuesta")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de la respuesta")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "¡Hola! Tenemos una gran variedad de productos. ¿Buscas algo en particular?",
                "agent_used": "product_agent",
                "session_id": "session456",
                "status": "success",
                "metadata": {
                    "requires_human": False,
                    "is_complete": False,
                    "processing_time_ms": 245,
                    "confidence": 0.95,
                },
            }
        }


class ChatErrorResponse(BaseModel):
    """Modelo para respuesta de error en chat"""

    error: str = Field(..., description="Mensaje de error")
    status: Literal["error"] = Field("error", description="Estado de error")
    detail: Optional[str] = Field(None, description="Detalles adicionales del error")

    class Config:
        json_schema_extra = {
            "example": {"error": "Error procesando el mensaje", "status": "error", "detail": "Servicio temporalmente no disponible"}
        }


class ConversationHistoryRequest(BaseModel):
    """Modelo para solicitud de historial de conversación"""

    user_id: str = Field(..., description="ID del usuario")
    session_id: Optional[str] = Field(None, description="ID de sesión específica")
    limit: int = Field(50, description="Límite de mensajes a obtener", ge=1, le=100)


class ConversationHistoryResponse(BaseModel):
    """Modelo para respuesta de historial de conversación"""

    user_id: str
    session_id: Optional[str]
    messages: list = Field(default_factory=list, description="Lista de mensajes")
    total_messages: int = Field(0, description="Total de mensajes en la conversación")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatStreamRequest(BaseModel):
    """Modelo para solicitud de mensaje de chat con streaming"""

    message: str = Field(..., description="Mensaje del usuario", min_length=1, max_length=5000)
    user_id: str = Field(..., description="ID único del usuario", min_length=1, max_length=100)
    session_id: Optional[str] = Field(None, description="ID de sesión para mantener contexto", max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadatos adicionales opcionales")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hola, ¿qué productos tienen disponibles?",
                "user_id": "user123",
                "session_id": "session456",
                "metadata": {"channel": "web", "locale": "es"},
            }
        }


class ChatStreamEvent(BaseModel):
    """Modelo para eventos de streaming en tiempo real"""

    event_type: StreamEventType = Field(..., description="Tipo de evento de streaming")
    message: str = Field(..., description="Mensaje del evento")
    agent_current: Optional[str] = Field(None, description="Agente actualmente procesando")
    progress: Optional[float] = Field(None, description="Progreso del procesamiento (0.0-1.0)", ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos del evento")
    timestamp: Optional[str] = Field(None, description="Timestamp del evento")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "thinking",
                "message": "Analizando tu consulta sobre productos...",
                "agent_current": "product_agent",
                "progress": 0.3,
                "metadata": {"step": "analysis"},
                "timestamp": "2024-01-15T10:30:00Z",
            }
        }


class ChatStreamComplete(BaseModel):
    """Modelo para evento final de streaming con respuesta completa"""

    event_type: Literal["complete"] = Field("complete", description="Tipo de evento (siempre 'complete')")
    response: str = Field(..., description="Respuesta final del bot")
    agent_used: str = Field(..., description="Agente que procesó el mensaje")
    session_id: str = Field(..., description="ID de sesión usado")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos finales")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "complete",
                "response": "¡Hola! Tenemos una gran variedad de productos. ¿Buscas algo en particular?",
                "agent_used": "product_agent",
                "session_id": "session456",
                "metadata": {
                    "requires_human": False,
                    "is_complete": True,
                    "processing_time_ms": 2450,
                    "total_events": 5,
                },
            }
        }