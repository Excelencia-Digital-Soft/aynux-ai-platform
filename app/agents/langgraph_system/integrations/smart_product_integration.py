"""
LangGraph Integration - Integración del SmartProductAgent en el sistema LangGraph.

Este módulo configura y conecta el SmartProductAgent con el grafo de agentes principal,
permitiendo enrutamiento inteligente y flujos conversacionales complejos.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.agents.langgraph_system.agents.smart_product_agent import SmartProductAgent
from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Tipos de agentes disponibles en el sistema."""

    SMART_PRODUCT = "smart_product_agent"
    DATA_INSIGHTS = "data_insights_agent"
    SUPPORT = "support_agent"
    GENERAL = "general_agent"


class ConversationState(Dict):
    """
    Estado de la conversación en LangGraph.

    Extiende Dict para compatibilidad con LangGraph mientras proporciona
    estructura tipada para los datos de conversación.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Campos requeridos con valores por defecto
        self.setdefault("messages", [])
        self.setdefault("current_agent", None)
        self.setdefault("agent_history", [])
        self.setdefault("user_id", None)
        self.setdefault("phone_number", None)
        self.setdefault("is_complete", False)
        self.setdefault("error_count", 0)
        self.setdefault("retrieved_data", {})
        self.setdefault("context", {})


class SmartProductAgentNode:
    """
    Nodo de LangGraph para el SmartProductAgent.

    Encapsula el agente para uso en el grafo de estados.
    """

    def __init__(self, ollama: Optional[OllamaIntegration] = None, postgres=None):
        self.agent = SmartProductAgent(ollama=ollama, postgres=postgres)
        self.name = "smart_product_agent"

    async def __call__(self, state: ConversationState) -> ConversationState:
        """
        Ejecuta el SmartProductAgent con el estado actual.
        """
        try:
            # Extraer último mensaje del usuario
            messages = state.get("messages", [])
            if not messages:
                return state

            last_message = messages[-1]
            user_input = last_message.content if hasattr(last_message, "content") else str(last_message)

            # Procesar con el agente
            result = await self.agent._process_internal(user_input, state)

            # Actualizar estado con resultado
            updated_state = ConversationState(**state)
            updated_state.update(result)

            # Convertir mensajes a formato LangGraph
            if result.get("messages"):
                new_messages = []
                for msg in result["messages"]:
                    if msg.get("role") == "assistant":
                        new_messages.append(AIMessage(content=msg["content"]))
                    else:
                        new_messages.append(HumanMessage(content=msg["content"]))

                updated_state["messages"] = messages + new_messages

            return updated_state

        except Exception as e:
            logger.error(f"Error in SmartProductAgentNode: {e}")

            # Estado de error
            error_state = ConversationState(**state)
            error_state.update(
                {
                    "messages": state["messages"]
                    + [AIMessage(content="Disculpa, tuve un problema procesando tu consulta de productos.")],
                    "error_count": state.get("error_count", 0) + 1,
                    "current_agent": self.name,
                }
            )

            return error_state


class AgentRouter:
    """
    Router inteligente para determinar qué agente debe manejar cada mensaje.
    """

    def __init__(self, ollama: Optional[OllamaIntegration] = None):
        self.ollama = ollama or OllamaIntegration()

        # Patrones de enrutamiento (dinámicos, no hardcodeados)
        self.agent_capabilities = {
            AgentType.SMART_PRODUCT: {
                "description": "Búsquedas y consultas de productos, inventario, categorías, marcas, precios",
                "keywords": ["producto", "buscar", "precio", "stock", "categoría", "marca"],
                "confidence_threshold": 0.7,
            },
            AgentType.DATA_INSIGHTS: {
                "description": "Análisis de datos, estadísticas, reportes, métricas del negocio",
                "keywords": ["cuántos", "total", "estadísticas", "reporte", "análisis"],
                "confidence_threshold": 0.8,
            },
            AgentType.SUPPORT: {
                "description": "Soporte técnico, problemas, quejas, devoluciones, garantías",
                "keywords": ["problema", "ayuda", "soporte", "devolver", "garantía"],
                "confidence_threshold": 0.7,
            },
            AgentType.GENERAL: {
                "description": "Conversación general, saludos, despedidas, información básica",
                "keywords": ["hola", "gracias", "adiós", "información"],
                "confidence_threshold": 0.5,
            },
        }

    async def route_message(self, message: str, state: ConversationState) -> AgentType:
        """
        Determina qué agente debe manejar el mensaje usando AI.
        """
        try:
            # Preparar contexto para el routing
            routing_context = self._build_routing_context(message, state)

            # Usar AI para determinar el mejor agente
            agent_type = await self._ai_route_decision(message, routing_context)

            # Validar y aplicar fallbacks
            if agent_type not in AgentType:
                agent_type = self._fallback_routing(message)

            logger.info(f"Routed message to {agent_type.value}: '{message[:50]}...'")
            return agent_type

        except Exception as e:
            logger.error(f"Error in message routing: {e}")
            return AgentType.GENERAL  # Fallback seguro

    def _build_routing_context(self, message: str, state: ConversationState) -> str:
        """
        Construye contexto para la decisión de enrutamiento.
        """
        context_parts = []

        # Historial de agentes usados
        agent_history = state.get("agent_history", [])
        if agent_history:
            context_parts.append(f"Agentes previos: {', '.join(agent_history[-3:])}")

        # Datos recuperados previamente
        retrieved_data = state.get("retrieved_data", {})
        if retrieved_data:
            context_parts.append(f"Contexto previo: {list(retrieved_data.keys())}")

        # Conversación reciente
        messages = state.get("messages", [])
        if len(messages) > 1:
            recent_messages = messages[-3:]
            context_parts.append("Mensajes recientes:")
            for msg in recent_messages:
                content = msg.content if hasattr(msg, "content") else str(msg)
                context_parts.append(f"- {content[:100]}")

        return "\n".join(context_parts) if context_parts else "Sin contexto previo"

    async def _ai_route_decision(self, message: str, context: str) -> AgentType:
        """
        Usa AI para decidir el enrutamiento.
        """

        # Construir descripción de agentes
        agents_description = []
        for agent_type, info in self.agent_capabilities.items():
            agents_description.append(f"- {agent_type.value}: {info['description']}")

        routing_prompt = f"""# ENRUTAMIENTO DE AGENTE

MENSAJE DEL USUARIO: "{message}"

CONTEXTO DE CONVERSACIÓN:
{context}

AGENTES DISPONIBLES:
{chr(10).join(agents_description)}

INSTRUCCIONES:
Determina qué agente debe manejar este mensaje.
Considera:
1. El contenido y intención del mensaje
2. El contexto de la conversación
3. Las capacidades de cada agente

Responde ÚNICAMENTE con el nombre del agente:
- smart_product_agent
- data_insights_agent  
- support_agent
- general_agent

Respuesta:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto router de agentes para sistemas conversacionales de e-commerce.",
                user_prompt=routing_prompt,
                temperature=0.2,
            )

            # Limpiar y validar respuesta
            agent_name = response.strip().lower()

            # Mapear nombre a enum
            for agent_type in AgentType:
                if agent_type.value == agent_name:
                    return agent_type

            # Si no se encuentra coincidencia exacta, buscar parcial
            for agent_type in AgentType:
                if agent_name in agent_type.value or agent_type.value in agent_name:
                    return agent_type

            # Fallback
            return self._fallback_routing(message)

        except Exception as e:
            logger.error(f"Error in AI routing: {e}")
            return self._fallback_routing(message)

    def _fallback_routing(self, message: str) -> AgentType:
        """
        Enrutamiento de fallback basado en palabras clave.
        """
        message_lower = message.lower()

        # Calcular scores para cada agente
        scores = {}
        for agent_type, info in self.agent_capabilities.items():
            score = 0
            for keyword in info["keywords"]:
                if keyword in message_lower:
                    score += 1
            scores[agent_type] = score

        # Seleccionar agente con mayor score
        if scores:
            best_agent = max(scores, key=scores.get)
            if scores[best_agent] > 0:
                return best_agent

        # Fallback final
        return AgentType.GENERAL


def create_smart_product_graph(ollama: Optional[OllamaIntegration] = None, postgres=None) -> StateGraph:
    """
    Crea el grafo de LangGraph con el SmartProductAgent integrado.
    """

    # Inicializar componentes
    router = AgentRouter(ollama)
    smart_product_node = SmartProductAgentNode(ollama, postgres)

    # Crear grafo
    workflow = StateGraph(ConversationState)

    # Agregar nodos
    workflow.add_node("router", router_node)
    workflow.add_node("smart_product_agent", smart_product_node)
    workflow.add_node("data_insights_agent", placeholder_agent_node("data_insights_agent"))
    workflow.add_node("support_agent", placeholder_agent_node("support_agent"))
    workflow.add_node("general_agent", placeholder_agent_node("general_agent"))

    # Definir punto de entrada
    workflow.set_entry_point("router")

    # Definir rutas condicionales
    workflow.add_conditional_edges(
        "router",
        lambda state: determine_next_agent(state),
        {
            "smart_product_agent": "smart_product_agent",
            "data_insights_agent": "data_insights_agent",
            "support_agent": "support_agent",
            "general_agent": "general_agent",
        },
    )

    # Todas las rutas de agentes van al final
    for agent in ["smart_product_agent", "data_insights_agent", "support_agent", "general_agent"]:
        workflow.add_edge(agent, END)

    return workflow.compile()


async def router_node(state: ConversationState) -> ConversationState:
    """
    Nodo router que determina qué agente usar.
    """
    try:
        messages = state.get("messages", [])
        if not messages:
            state["next_agent"] = AgentType.GENERAL.value
            return state

        last_message = messages[-1]
        user_input = last_message.content if hasattr(last_message, "content") else str(last_message)

        # Usar router para determinar agente
        router = AgentRouter()
        agent_type = await router.route_message(user_input, state)

        state["next_agent"] = agent_type.value
        state["routing_reason"] = f"AI routing selected {agent_type.value}"

        return state

    except Exception as e:
        logger.error(f"Error in router node: {e}")
        state["next_agent"] = AgentType.GENERAL.value
        state["routing_reason"] = f"Fallback due to error: {str(e)}"
        return state


def determine_next_agent(state: ConversationState) -> str:
    """
    Función para determinar el próximo agente basado en el estado.
    """
    return state.get("next_agent", "general_agent")


def placeholder_agent_node(agent_name: str):
    """
    Crea un nodo placeholder para agentes no implementados.
    """

    async def placeholder_node(state: ConversationState) -> ConversationState:
        """Nodo placeholder que responde con mensaje genérico."""

        state["messages"] = state.get("messages", []) + [
            AIMessage(content=f"El agente {agent_name} aún no está implementado. ¿Puedo ayudarte con algo más?")
        ]
        state["current_agent"] = agent_name
        state["is_complete"] = True

        return state

    return placeholder_node


# Función principal para ejecutar el grafo
async def process_conversation(
    message: str,
    user_id: Optional[str] = None,
    phone_number: Optional[str] = None,
    conversation_history: Optional[List] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Procesa una conversación completa usando el grafo de agentes.
    """
    try:
        # Crear grafo
        graph = create_smart_product_graph()

        # Preparar estado inicial
        initial_state = ConversationState(
            messages=[HumanMessage(content=message)],
            user_id=user_id,
            phone_number=phone_number,
            context=context or {},
            conversation_history=conversation_history or [],
        )

        # Ejecutar grafo
        result = await graph.ainvoke(initial_state)

        # Extraer respuesta final
        final_messages = result.get("messages", [])
        response_message = ""

        if final_messages:
            last_message = final_messages[-1]
            response_message = last_message.content if hasattr(last_message, "content") else str(last_message)

        return {
            "success": True,
            "response": response_message,
            "agent_used": result.get("current_agent"),
            "routing_reason": result.get("routing_reason"),
            "metadata": {
                "agent_history": result.get("agent_history", []),
                "retrieved_data": result.get("retrieved_data", {}),
                "error_count": result.get("error_count", 0),
            },
        }

    except Exception as e:
        logger.error(f"Error processing conversation: {e}")
        return {
            "success": False,
            "response": "Disculpa, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
            "error": str(e),
        }


# Configuración para diferentes entornos
class GraphConfig:
    """Configuración del grafo para diferentes entornos."""

    @staticmethod
    def development_config() -> Dict[str, Any]:
        """Configuración para desarrollo."""
        return {"debug": True, "verbose_logging": True, "enable_fallbacks": True, "timeout_seconds": 30}

    @staticmethod
    def production_config() -> Dict[str, Any]:
        """Configuración para producción."""
        return {
            "debug": False,
            "verbose_logging": False,
            "enable_fallbacks": True,
            "timeout_seconds": 10,
            "enable_metrics": True,
            "enable_caching": True,
        }

    @staticmethod
    def testing_config() -> Dict[str, Any]:
        """Configuración para testing."""
        return {
            "debug": True,
            "verbose_logging": True,
            "enable_fallbacks": False,  # Para detectar errores
            "timeout_seconds": 5,
            "mock_agents": True,
        }
