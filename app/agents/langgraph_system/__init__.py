"""
Sistema Multi-Agente con LangGraph para E-commerce
"""

from .graph import EcommerceAssistantGraph
from .models import AgentResponse, ConversationContext, CustomerContext, IntentInfo
from .router import IntentRouter, SupervisorAgent
from .state_manager import StateManager
from .state_schema import LangGraphState

__all__ = [
    # Modelos de datos (Pydantic)
    "CustomerContext",
    "ConversationContext",
    "IntentInfo",
    "AgentResponse",
    # Estado de LangGraph (TypedDict)
    "LangGraphState",
    # Gestor de estado
    "StateManager",
    # Componentes principales
    "EcommerceAssistantGraph",
    "IntentRouter",
    "SupervisorAgent",
]

