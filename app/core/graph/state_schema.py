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


def take_latest_non_none(left: Optional[str], right: Optional[str]) -> Optional[str]:
    """Reducer for next_agent: keep the latest non-None value.

    This prevents next_agent from being lost during state merges when
    some nodes don't explicitly set it.
    """
    return right if right is not None else left


def add_cache_keys(left: List[str], right: List[str]) -> List[str]:
    """Reducer personalizado para claves de cache sin duplicados"""
    return list(set(left + right))


def update_conversation_context(
    left: Dict[str, Any], right: Dict[str, Any]
) -> Dict[str, Any]:
    """Reducer para contexto de conversación - merge con valores más recientes"""
    if not right:
        return left
    return {**left, **right}


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

    # Dominio de negocio (ecommerce, hospital, credit, excelencia)
    business_domain: Optional[str]

    # Dominios habilitados para el tenant (para filtrar servicios en saludos)
    enabled_domains: Optional[List[str]]

    # Detected language for response generation (es, en, pt)
    detected_language: Optional[str]

    # Información de intención y routing
    current_intent: Optional[Dict[str, Any]]
    intent_history: Annotated[List[Dict[str, Any]], add_intent_history]

    # Estado del flujo de agentes
    current_agent: Optional[str]
    next_agent: Annotated[Optional[str], take_latest_non_none]  # Agente al que debe enrutarse a continuación
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
    orchestrator_analysis: Optional[Dict[str, Any]]
    supervisor_analysis: Optional[Dict[str, Any]]
    supervisor_evaluation: Optional[Dict[str, Any]]
    conversation_flow: Optional[Dict[str, Any]]

    # Nuevos campos para manejo de re-routing y calidad
    needs_re_routing: Optional[bool]
    routing_attempts: int
    supervisor_retry_count: int

    # Metadatos y optimización
    conversation_checkpoint_id: Optional[str]
    cache_keys: Annotated[List[str], add_cache_keys]
    total_processing_time_ms: float

    # Historial de conversación (conversation history management)
    conversation_context: Annotated[Dict[str, Any], update_conversation_context]
    conversation_summary: Optional[str]  # Resumen para inyectar en prompts
    history_loaded: bool  # Flag para indicar si el historial fue cargado

    # Identification fields (must be preserved across nodes for flow continuity)
    conversation_id: Optional[str]
    user_phone: Optional[str]
    sender: Optional[str]  # Alias for WhatsApp user identification

    # BYPASS ROUTING: Target agent from bypass rules (for direct routing)
    # When a bypass rule matches, this field holds the agent to route to directly,
    # skipping LLM intent analysis. Used by orchestrator._check_bypass_routing()
    bypass_target_agent: Optional[str]

    # RAG metrics for frontend visualization
    rag_metrics: Optional[Dict[str, Any]]  # {used, query, results_count, duration_ms, sources}

    # PHARMACY DOMAIN: Customer identification state (must persist across messages)
    customer_identified: Optional[bool]
    plex_customer_id: Optional[str]
    plex_customer: Optional[Dict[str, Any]]
    whatsapp_phone: Optional[str]
    customer_name: Optional[str]

    # PHARMACY DOMAIN: Pharmacy configuration (must persist for personalized responses)
    pharmacy_id: Optional[str]
    pharmacy_name: Optional[str]
    pharmacy_phone: Optional[str]

    # MULTI-TENANT: Organization identifier (must persist for tenant isolation)
    organization_id: Optional[str]


GraphState = LangGraphState
