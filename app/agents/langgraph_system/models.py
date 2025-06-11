"""
Modelos de estado compartido para el sistema multi-agente
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState
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


class SharedState(MessagesState):
    """Estado compartido entre todos los agentes del sistema"""
    
    # Contextos principales
    customer: Optional[CustomerContext] = None
    conversation: Optional[ConversationContext] = None
    
    # Información de intención y routing
    current_intent: Optional[IntentInfo] = None
    intent_history: List[IntentInfo] = Field(default_factory=list)
    
    # Estado del flujo de agentes
    current_agent: Optional[str] = None
    agent_history: List[str] = Field(default_factory=list)
    
    # Respuestas y datos recopilados
    agent_responses: List[AgentResponse] = Field(default_factory=list)
    retrieved_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Control de flujo
    requires_human: bool = False
    is_complete: bool = False
    error_count: int = 0
    max_errors: int = 3
    
    # Metadatos y optimización
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    conversation_checkpoint_id: Optional[str] = None  # Renombrado para evitar conflicto con LangGraph
    cache_keys: List[str] = Field(default_factory=list)
    
    # Métricas de rendimiento
    total_processing_time_ms: float = 0.0
    
    def add_agent_response(self, response: AgentResponse):
        """Añade una respuesta de agente al estado"""
        self.agent_responses.append(response)
        if response.processing_time_ms:
            self.total_processing_time_ms += response.processing_time_ms
        self.updated_at = datetime.now()
    
    def update_intent(self, intent: IntentInfo):
        """Actualiza la intención actual y guarda en historial"""
        if self.current_intent:
            self.intent_history.append(self.current_intent)
        self.current_intent = intent
        self.updated_at = datetime.now()
    
    def set_current_agent(self, agent_name: str):
        """Establece el agente actual y actualiza historial"""
        self.current_agent = agent_name
        if agent_name not in self.agent_history:
            self.agent_history.append(agent_name)
        self.updated_at = datetime.now()
    
    def increment_error(self):
        """Incrementa el contador de errores"""
        self.error_count += 1
        if self.error_count >= self.max_errors:
            self.requires_human = True
        self.updated_at = datetime.now()
    
    def add_cache_key(self, key: str):
        """Añade una clave de caché utilizada"""
        if key not in self.cache_keys:
            self.cache_keys.append(key)
    
    def get_last_user_message(self) -> Optional[str]:
        """Obtiene el último mensaje del usuario"""
        for message in reversed(self.messages):
            if message.type == "human":
                return message.content
        return None
    
    def get_last_agent_response(self) -> Optional[AgentResponse]:
        """Obtiene la última respuesta de agente"""
        return self.agent_responses[-1] if self.agent_responses else None
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen del contexto actual"""
        return {
            "customer_id": self.customer.customer_id if self.customer else None,
            "conversation_id": self.conversation.conversation_id if self.conversation else None,
            "current_intent": self.current_intent.primary_intent if self.current_intent else None,
            "current_agent": self.current_agent,
            "message_count": len(self.messages),
            "agent_responses_count": len(self.agent_responses),
            "error_count": self.error_count,
            "requires_human": self.requires_human,
            "is_complete": self.is_complete,
            "total_processing_time_ms": self.total_processing_time_ms,
            "duration_seconds": self.conversation.duration_seconds() if self.conversation else 0
        }
    
    def should_handoff_to_human(self) -> bool:
        """Determina si se debe transferir a un humano"""
        if self.requires_human:
            return True
        
        if self.error_count >= self.max_errors:
            return True
        
        if self.current_intent and self.current_intent.requires_handoff:
            return True
        
        # Si la conversación es muy larga sin resolución
        if len(self.messages) > 20 and not self.is_complete:
            return True
        
        return False
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de rendimiento"""
        avg_response_time = 0.0
        if self.agent_responses:
            response_times = [r.processing_time_ms for r in self.agent_responses if r.processing_time_ms]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return {
            "total_processing_time_ms": self.total_processing_time_ms,
            "average_agent_response_time_ms": avg_response_time,
            "total_agents_invoked": len(self.agent_history),
            "unique_agents_invoked": len(set(self.agent_history)),
            "cache_hits": len(self.cache_keys),
            "error_rate": self.error_count / max(len(self.agent_responses), 1)
        }