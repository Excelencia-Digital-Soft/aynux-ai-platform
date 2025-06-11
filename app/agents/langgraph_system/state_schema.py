"""
Schema de estado para LangGraph usando TypedDict
"""
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class GraphState(TypedDict, total=False):
    """Estado para el graph de LangGraph"""
    # Campo requerido por LangGraph
    messages: List[BaseMessage]
    
    # Contextos principales
    customer: Optional[Dict[str, Any]]
    conversation: Optional[Dict[str, Any]]
    
    # Información de intención y routing
    current_intent: Optional[Dict[str, Any]]
    intent_history: List[Dict[str, Any]]
    
    # Estado del flujo de agentes
    current_agent: Optional[str]
    agent_history: List[str]
    
    # Respuestas y datos recopilados
    agent_responses: List[Dict[str, Any]]
    retrieved_data: Dict[str, Any]
    
    # Control de flujo
    requires_human: bool
    is_complete: bool
    error_count: int
    max_errors: int
    
    # Metadatos
    conversation_checkpoint_id: Optional[str]
    cache_keys: List[str]
    total_processing_time_ms: float