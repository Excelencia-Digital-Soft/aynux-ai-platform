"""
Schema de estado usando TypedDict para máximo rendimiento con LangGraph
"""

from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def add_agent_responses(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reducer personalizado para respuestas de agentes"""
    return left + right


def merge_retrieved_data(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Reducer personalizado para datos recuperados"""
    return {**left, **right}


def add_intent_history(left: List[Dict[str, Any]], right: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reducer personalizado para historial de intenciones"""
    return left + right


def add_agent_history(left: List[str], right: List[str]) -> List[str]:
    """Reducer personalizado para historial de agentes"""
    return left + right


def add_cache_keys(left: List[str], right: List[str]) -> List[str]:
    """Reducer personalizado para claves de cache sin duplicados"""
    return list(set(left + right))


class LangGraphState(TypedDict):
    """
    Estado principal para LangGraph usando TypedDict para máximo rendimiento.

    Este es el único estado que debe usarse con LangGraph.
    Usa reducers personalizados para manejar actualizaciones complejas.
    """

    # Campo requerido por LangGraph con reducer incorporado
    messages: Annotated[List[BaseMessage], add_messages]

    # Contextos principales (como diccionarios planos)
    customer: Optional[Dict[str, Any]]
    conversation: Optional[Dict[str, Any]]

    # Información de intención y routing
    current_intent: Optional[Dict[str, Any]]
    intent_history: Annotated[List[Dict[str, Any]], add_intent_history]

    # Estado del flujo de agentes
    current_agent: Optional[str]
    next_agent: Optional[str]  # Agente al que debe enrutarse a continuación
    agent_history: Annotated[List[str], add_agent_history]

    # Respuestas y datos recopilados
    agent_responses: Annotated[List[Dict[str, Any]], add_agent_responses]
    retrieved_data: Annotated[Dict[str, Any], merge_retrieved_data]

    # Control de flujo
    requires_human: bool
    is_complete: bool
    error_count: int
    max_errors: int
    human_handoff_requested: Optional[bool]
    
    # Información de routing y análisis
    routing_decision: Optional[Dict[str, Any]]
    supervisor_analysis: Optional[Dict[str, Any]]

    # Metadatos y optimización
    conversation_checkpoint_id: Optional[str]
    cache_keys: Annotated[List[str], add_cache_keys]
    total_processing_time_ms: float


GraphState = LangGraphState
