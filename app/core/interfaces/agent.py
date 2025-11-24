"""
Interfaces para agentes LangGraph

Define contratos para todos los agentes del sistema multi-dominio.
"""
from typing import Protocol, Dict, Any, Optional, List, runtime_checkable
from abc import abstractmethod
from enum import Enum


class AgentStatus(str, Enum):
    """Estados posibles de un agente"""
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


class AgentType(str, Enum):
    """Tipos de agentes en el sistema"""
    SUPERVISOR = "supervisor"
    PRODUCT_SEARCH = "product_search"
    ORDER_TRACKING = "order_tracking"
    PROMOTIONS = "promotions"
    SUPPORT = "support"
    GREETING = "greeting"
    FAREWELL = "farewell"
    FALLBACK = "fallback"
    # Credit domain
    CREDIT_BALANCE = "credit_balance"
    PAYMENT = "payment"
    # Healthcare domain
    APPOINTMENT = "appointment"
    CONSULTATION = "consultation"


@runtime_checkable
class IAgent(Protocol):
    """
    Interface base para todos los agentes LangGraph.

    Todos los agentes (nodes) del sistema deben implementar esta interface.
    Permite ejecutar agentes de forma uniforme sin conocer su implementación.

    Example:
        ```python
        class ProductSearchAgent(IAgent):
            async def execute(self, state: dict) -> dict:
                # Implementación específica
                products = await self.search_products(state["query"])
                return {"products": products, "status": AgentStatus.COMPLETED}
        ```
    """

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Tipo de agente"""
        ...

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Nombre legible del agente"""
        ...

    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta el agente con el estado dado.

        Args:
            state: Estado actual del grafo (LangGraph state)

        Returns:
            Diccionario con actualizaciones al estado

        Raises:
            AgentExecutionError: Si hay error en la ejecución
        """
        ...

    @abstractmethod
    async def validate_input(self, state: Dict[str, Any]) -> bool:
        """
        Valida que el estado de entrada tenga los campos requeridos.

        Args:
            state: Estado a validar

        Returns:
            True si el estado es válido

        Raises:
            ValidationError: Si el estado no es válido
        """
        ...


@runtime_checkable
class ISupervisorAgent(Protocol):
    """
    Interface para agentes supervisores.

    Los supervisores deciden a qué agente especializado enrutar la conversación.
    """

    @abstractmethod
    async def route(self, state: Dict[str, Any]) -> str:
        """
        Determina el próximo agente a ejecutar.

        Args:
            state: Estado actual

        Returns:
            Nombre del próximo nodo/agente a ejecutar

        Example:
            ```python
            async def route(self, state: dict) -> str:
                intent = state.get("user_intent")
                if "product" in intent:
                    return "product_search"
                elif "order" in intent:
                    return "order_tracking"
                return "fallback"
            ```
        """
        ...

    @abstractmethod
    async def analyze_intent(self, message: str) -> Dict[str, Any]:
        """
        Analiza la intención del mensaje de usuario.

        Args:
            message: Mensaje del usuario

        Returns:
            Diccionario con intent, entities, confidence, etc.
        """
        ...


@runtime_checkable
class IConversationalAgent(Protocol):
    """
    Interface para agentes que generan respuestas conversacionales.

    Agentes que interactúan directamente con usuarios vía chat.
    """

    @abstractmethod
    async def generate_response(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Genera una respuesta natural para el usuario.

        Args:
            query: Mensaje/pregunta del usuario
            context: Contexto adicional de la conversación

        Returns:
            Respuesta en lenguaje natural
        """
        ...

    @abstractmethod
    async def format_results(
        self,
        results: List[Any],
        language: str = "es"
    ) -> str:
        """
        Formatea resultados en una respuesta legible.

        Args:
            results: Resultados a formatear (productos, órdenes, etc.)
            language: Idioma de la respuesta

        Returns:
            Texto formateado para mostrar al usuario
        """
        ...


# Excepciones específicas de agentes
class AgentError(Exception):
    """Error base para agentes"""
    pass


class AgentExecutionError(AgentError):
    """Error durante la ejecución de un agente"""
    pass


class AgentValidationError(AgentError):
    """Error de validación de entrada"""
    pass


class AgentTimeoutError(AgentError):
    """Timeout ejecutando agente"""
    pass
