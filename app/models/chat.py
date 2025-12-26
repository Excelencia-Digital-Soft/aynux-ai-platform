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
            "example": {
                "error": "Error procesando el mensaje",
                "status": "error",
                "detail": "Servicio temporalmente no disponible",
            }
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


# ============================================================
# CHAT ADMIN MODELS (for Chat Visualizer)
# ============================================================


class ChatTestRequest(BaseModel):
    """Request model for testing the chat agent."""

    message: str = Field(..., description="Test message to send", min_length=1, max_length=5000)
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    debug: bool = Field(False, description="Enable debug mode for detailed execution info")
    user_id: str = Field("test_user", description="User ID for the test")
    session_id: Optional[str] = Field(None, description="Existing session ID to continue")


class ExecutionStepModel(BaseModel):
    """Model for a single execution step in agent processing."""

    id: str = Field(..., description="Unique step ID")
    step_number: int = Field(..., description="Step sequence number")
    node_type: str = Field(..., description="Type: start, tool_call, llm_call, decision, end, error")
    name: str = Field(..., description="Step name or agent name")
    description: Optional[str] = Field(None, description="Step description")
    input: Optional[Dict[str, Any]] = Field(None, description="Step input data")
    output: Optional[Dict[str, Any]] = Field(None, description="Step output data")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    status: str = Field("completed", description="Status: pending, running, completed, error")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    timestamp: str = Field(..., description="ISO timestamp")


class ChatTestResponse(BaseModel):
    """Response model for chat agent test."""

    session_id: str = Field(..., description="Session ID")
    response: str = Field(..., description="Agent response text")
    agent_used: str = Field(..., description="Agent that processed the message")
    execution_steps: Optional[list[ExecutionStepModel]] = Field(None, description="Execution trace")
    debug_info: Optional[Dict[str, Any]] = Field(None, description="Debug information")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChatMetricsResponse(BaseModel):
    """Response model for chat metrics."""

    total_messages: int = Field(0, description="Total messages processed")
    total_sessions: int = Field(0, description="Total unique sessions")
    total_tokens: int = Field(0, description="Total tokens used")
    avg_response_time_ms: float = Field(0.0, description="Average response time in ms")
    tool_calls_count: int = Field(0, description="Total tool calls made")
    error_count: int = Field(0, description="Total errors encountered")
    error_rate: float = Field(0.0, description="Error rate percentage")
    agents_used: Dict[str, int] = Field(default_factory=dict, description="Message count by agent")
    period_days: int = Field(7, description="Metrics period in days")


class ChatAgentConfigResponse(BaseModel):
    """Response model for agent configuration."""

    model: str = Field(..., description="LLM model being used")
    temperature: float = Field(..., description="Model temperature")
    max_tokens: int = Field(..., description="Maximum tokens in response")
    tools: list[str] = Field(default_factory=list, description="Available tools")
    system_prompt: Optional[str] = Field(None, description="System prompt (truncated)")
    rag_enabled: bool = Field(True, description="Whether RAG is enabled")
    rag_max_results: int = Field(5, description="Max RAG results")


class ChatGraphNode(BaseModel):
    """Node in the execution graph."""

    id: str = Field(..., description="Node ID")
    type: str = Field(..., description="Node type")
    label: str = Field(..., description="Display label")
    data: Optional[Dict[str, Any]] = Field(None, description="Node data")


class ChatGraphEdge(BaseModel):
    """Edge in the execution graph."""

    id: str = Field(..., description="Edge ID")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")


class ChatGraphResponse(BaseModel):
    """Response model for execution graph visualization."""

    nodes: list[ChatGraphNode] = Field(default_factory=list, description="Graph nodes")
    edges: list[ChatGraphEdge] = Field(default_factory=list, description="Graph edges")
    current_node: Optional[str] = Field(None, description="Currently active node")
    visited_nodes: list[str] = Field(default_factory=list, description="Nodes visited in execution")
