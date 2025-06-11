"""
Gestor de estado que actúa como puente entre modelos Pydantic y TypedDict
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage

from .models import AgentResponse, ConversationContext, CustomerContext, IntentInfo
from .state_schema import LangGraphState

logger = logging.getLogger(__name__)


class StateManager:
    """
    Gestor de estado que proporciona una interfaz limpia entre
    los modelos Pydantic y el estado TypedDict de LangGraph.

    Principios SOLID aplicados:
    - SRP: Solo responsable de gestión de estado
    - OCP: Extensible para nuevos tipos de estado
    - LSP: Interfaces consistentes
    - ISP: Métodos específicos por responsabilidad
    - DIP: Depende de abstracciones, no implementaciones
    """

    @staticmethod
    def create_initial_state(
        message: str,
        customer: Optional[CustomerContext] = None,
        conversation: Optional[ConversationContext] = None,
        conversation_id: Optional[str] = None,
    ) -> LangGraphState:
        """
        Crea el estado inicial para LangGraph con tipos seguros.

        Args:
            message: Mensaje inicial del usuario
            customer: Contexto del cliente (opcional)
            conversation: Contexto de conversación (opcional)
            conversation_id: ID de conversación para checkpointing

        Returns:
            Estado inicial compatible con LangGraph
        """
        state: LangGraphState = {
            "messages": [HumanMessage(content=message)],
            "customer": customer.to_dict() if customer else None,
            "conversation": conversation.to_dict() if conversation else None,
            "current_intent": None,
            "intent_history": [],
            "current_agent": None,
            "agent_history": [],
            "agent_responses": [],
            "retrieved_data": {},
            "requires_human": False,
            "is_complete": False,
            "error_count": 0,
            "max_errors": 3,
            "conversation_checkpoint_id": conversation_id,
            "cache_keys": [],
            "total_processing_time_ms": 0.0,
        }

        logger.debug(f"Created initial state with {len(state)} fields")
        return state

    @staticmethod
    def update_customer_context(state: LangGraphState, customer: CustomerContext) -> Dict[str, Any]:
        """
        Actualiza el contexto del cliente en el estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"customer": customer.to_dict(), "state": state}

    @staticmethod
    def update_conversation_context(state: LangGraphState, conversation: ConversationContext) -> Dict[str, Any]:
        """
        Actualiza el contexto de conversación en el estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"conversation": conversation.to_dict(), "state": state}

    @staticmethod
    def add_intent_info(state: LangGraphState, intent: IntentInfo) -> Dict[str, Any]:
        """
        Añade información de intención al estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        intent_dict = intent.to_dict()
        return {"current_intent": intent_dict, "intent_history": [intent_dict], "state": state}

    @staticmethod
    def add_agent_response(state: LangGraphState, response: AgentResponse) -> Dict[str, Any]:
        """
        Añade respuesta de agente al estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        response_dict = response.to_dict()
        return {"agent_responses": [response_dict], "current_agent": response.agent_name, "state": state}

    @staticmethod
    def set_current_agent(state: LangGraphState, agent_name: str) -> Dict[str, Any]:
        """
        Establece el agente actual y actualiza el historial.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"current_agent": agent_name, "agent_history": [agent_name], "state": state}

    @staticmethod
    def add_ai_message(state: LangGraphState, content: str) -> Dict[str, Any]:
        """
        Añade un mensaje de IA al estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"messages": [AIMessage(content=content)], "state": state}

    @staticmethod
    def mark_complete(state: LangGraphState, requires_human: bool = False) -> Dict[str, Any]:
        """
        Marca la conversación como completa.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"is_complete": True, "requires_human": requires_human, "state": state}

    @staticmethod
    def increment_error_count(state: LangGraphState) -> Dict[str, Any]:
        """
        Incrementa el contador de errores.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        current_errors = state.get("error_count", 0)
        return {"error_count": current_errors + 1}

    @staticmethod
    def add_retrieved_data(state: LangGraphState, key: str, data: Any) -> Dict[str, Any]:
        """
        Añade datos recuperados al estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"retrieved_data": {key: data}, "state": state}

    @staticmethod
    def add_cache_key(state: LangGraphState, cache_key: str) -> Dict[str, Any]:
        """
        Añade una clave de cache al estado.

        Returns:
            Diccionario con las actualizaciones para el estado
        """
        return {"cache_keys": [cache_key], "state": state}

    @staticmethod
    def get_last_user_message(state: LangGraphState) -> Optional[str | list[str | dict]]:
        """
        Obtiene el último mensaje del usuario.

        Returns:
            Contenido del último mensaje del usuario o None
        """
        messages = state.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content or ""
        return None

    @staticmethod
    def get_last_ai_message(state: LangGraphState) -> Optional[str | list[str | dict]]:
        """
        Obtiene el último mensaje de IA.

        Returns:
            Contenido del último mensaje de IA o None
        """
        messages = state.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return message.content
        return None

    @staticmethod
    def should_continue(state: LangGraphState) -> bool:
        """
        Determina si la conversación debe continuar.

        Returns:
            True si debe continuar, False si debe terminar
        """
        if state.get("is_complete", False):
            return False

        error_count = state.get("error_count", 0)
        max_errors = state.get("max_errors", 3)

        if error_count >= max_errors:
            logger.warning(f"Maximum errors reached: {error_count}/{max_errors}")
            return False

        return True

    @staticmethod
    def validate_state(state: LangGraphState) -> bool:
        """
        Valida que el estado tenga la estructura requerida.

        Returns:
            True si el estado es válido, False en caso contrario
        """
        required_fields = ["messages"]

        for field in required_fields:
            if field not in state:
                logger.error(f"Missing required field in state: {field}")
                return False

        state = state["messages"]  # type: ignore
        if not isinstance(state, list):
            logger.error("Messages field must be a list")
            return False

        return True
