"""
Graph principal del sistema multi-agente LangGraph
"""

import logging
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph

from app.config.langsmith_config import ConversationTracer, get_tracer

from .integrations.chroma_integration import ChromaDBIntegration
from .integrations.ollama_integration import OllamaIntegration
from .integrations.postgres_integration import PostgreSQLIntegration
from .schemas import AgentType, get_agent_routing_literal, get_non_supervisor_agents
from .state_schema import LangGraphState
from .subagent import (
    CategoryAgent,
    DataInsightsAgent,
    FallbackAgent,
    FarewellAgent,
    InvoiceAgent,
    ProductAgent,
    PromotionsAgent,
    SupervisorAgent,
    SupportAgent,
    TrackingAgent,
)

logger = logging.getLogger(__name__)


class EcommerceAssistantGraph:
    """Graph principal del asistente e-commerce multi-agente"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Initialize LangSmith tracing
        self.tracer = get_tracer()

        # Track conversation tracers by conversation_id
        self.conversation_tracers: Dict[str, ConversationTracer] = {}

        # Inicializar integraciones
        self._init_integrations()

        # Inicializar agentes especializados
        self._init_agents()

        # Construir el graph
        self.graph = self._build_graph()

        # Compilar el graph (checkpointer se configura en initialize si está disponible)
        self.app = None
        self.checkpointer_manager = None
        self.persistent_checkpointer = None
        self.use_postgres_checkpointer = True  # Enable PostgreSQL checkpointing

        logger.info("EcommerceAssistantGraph initialized successfully")

    def _build_graph(self) -> StateGraph:
        """Construye el StateGraph de LangGraph"""
        # Crear StateGraph con el schema TypedDict
        workflow = StateGraph(LangGraphState)

        # Crear dinámicamente todos los métodos de nodos de agentes
        self._create_agent_nodes()

        # Add supervisor
        workflow.add_node(AgentType.SUPERVISOR.value, self._supervisor_node)

        # Add all other agents dynamically using the generated node methods
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value
            node_method = getattr(self, f"_{agent_name}_node")
            workflow.add_node(agent_name, node_method)

        # Definir punto de entrada
        workflow.set_entry_point(AgentType.SUPERVISOR.value)

        # Añadir aristas condicionales desde supervisor usando AgentType
        edges_mapping = {agent_type.value: agent_type.value for agent_type in get_non_supervisor_agents()}
        edges_mapping["__end__"] = END

        workflow.add_conditional_edges("supervisor", self._route_to_agent, edges_mapping)

        # Configurar el flujo de retorno de los agentes
        # Solo algunos agentes pueden volver al supervisor para re-routing
        # Los demás terminan directamente para evitar loops
        for agent_type in get_non_supervisor_agents():
            agent = agent_type.value
            if agent in [AgentType.FALLBACK_AGENT.value, AgentType.SUPPORT_AGENT.value]:
                # Estos agentes pueden necesitar re-routing
                workflow.add_conditional_edges(
                    agent,
                    self._should_continue,
                    {
                        "continue": AgentType.SUPERVISOR.value,
                        "__end__": END,
                    },
                )
            else:
                # Los demás agentes terminan directamente después de procesar
                workflow.add_edge(agent, END)

        return workflow

    # Métodos de inicialización
    def _init_integrations(self):
        """Inicializa las integraciones externas"""
        self.ollama = OllamaIntegration(self.config.get("ollama", {}))
        self.chroma = ChromaDBIntegration(self.config.get("chromadb", {}))
        self.postgres = PostgreSQLIntegration(self.config.get("postgres", {}))

    def _init_agents(self):
        """Inicializa agentes especializados"""
        try:
            agent_config = self.config.get("agents", {})

            # Initialize supervisor agent
            self.supervisor_agent = SupervisorAgent(ollama=self.ollama, config=agent_config.get("supervisor", {}))

            # Initialize agents explicitly using schema for configuration
            self.product_agent = ProductAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_config.get("product", {})
            )

            self.category_agent = CategoryAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_config.get("category", {})
            )

            self.data_insights_agent = DataInsightsAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_config.get("data_insights", {})
            )

            self.promotions_agent = PromotionsAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_config.get("promotions", {})
            )

            self.tracking_agent = TrackingAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_config.get("tracking", {})
            )

            self.support_agent = SupportAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_config.get("support", {})
            )

            self.invoice_agent = InvoiceAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_config.get("invoice", {})
            )

            self.fallback_agent = FallbackAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_config.get("fallback", {})
            )

            self.farewell_agent = FarewellAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_config.get("farewell", {})
            )

            logger.info("Agents initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise

    # Métodos de nodos del graph
    async def _supervisor_node(self, state: LangGraphState) -> Dict[str, Any]:
        """
        Nodo del supervisor que analiza el mensaje y decide el routing.

        Args:
            state: Estado actual del graph

        Returns:
            Actualizaciones al estado
        """
        try:
            # Obtener el último mensaje del usuario
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "fallback_agent", "error": "No messages in state"}

            # Buscar el último mensaje del usuario
            user_message = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content
                    break

            if not user_message:
                # Si no hay mensaje de usuario, usar el último mensaje disponible
                user_message = messages[-1].content if messages else ""

            logger.info(f"Supervisor processing: {user_message[:100] if user_message else 'Empty message'}...")

            # Convertir messages para el state_dict
            messages_dict = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    messages_dict.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages_dict.append({"role": "assistant", "content": msg.content})

            # Crear state_dict para el supervisor
            state_dict = {
                "messages": messages_dict,
                "customer_data": state.get("customer_data", {}),
                "current_agent": state.get("current_agent"),
                "agent_history": state.get("agent_history", []),
            }

            # Procesar con el supervisor agent
            result = await self.supervisor_agent._process_internal(message=user_message, state_dict=state_dict)

            # El supervisor devuelve el siguiente agente y análisis
            next_agent = result.get("next_agent", "fallback_agent")

            # Actualizar el estado con la decisión del supervisor
            updates = {
                "current_agent": "supervisor",
                "next_agent": next_agent,
                "routing_decision": result.get("routing_decision", {}),
                "supervisor_analysis": result.get("supervisor_analysis", {}),
            }

            # Si hay escalamiento humano solicitado
            if result.get("human_handoff_requested"):
                updates["human_handoff_requested"] = True
                updates["is_complete"] = True
                # Convertir mensajes del resultado a AIMessage
                if "messages" in result:
                    for msg_dict in result["messages"]:
                        if msg_dict.get("role") == "assistant":
                            updates["messages"] = [AIMessage(content=msg_dict["content"])]

            return updates

        except Exception as e:
            logger.error(f"Error in supervisor node: {str(e)}")
            return {"next_agent": "fallback_agent", "error": str(e), "error_count": state.get("error_count", 0) + 1}

    def _get_agent_mapping(self) -> Dict[str, Any]:
        """
        Mapea nombres de agentes a sus instancias.

        Returns:
            Diccionario mapping agent_name -> agent_instance
        """
        return {
            AgentType.PRODUCT_AGENT.value: self.product_agent,
            AgentType.CATEGORY_AGENT.value: self.category_agent,
            AgentType.DATA_INSIGHTS_AGENT.value: self.data_insights_agent,
            AgentType.PROMOTIONS_AGENT.value: self.promotions_agent,
            AgentType.TRACKING_AGENT.value: self.tracking_agent,
            AgentType.SUPPORT_AGENT.value: self.support_agent,
            AgentType.INVOICE_AGENT.value: self.invoice_agent,
            AgentType.FALLBACK_AGENT.value: self.fallback_agent,
            AgentType.FAREWELL_AGENT.value: self.farewell_agent,
        }

    def _create_standard_node(self, agent_instance: Any, agent_name: str):
        """
        Crea un método de nodo estándar para un agente.

        Args:
            agent_instance: Instancia del agente
            agent_name: Nombre del agente

        Returns:
            Método async que ejecuta el agente
        """

        async def agent_node(state: LangGraphState) -> Dict[str, Any]:
            return await self._execute_agent_node(state, agent_instance, agent_name)

        return agent_node

    def _create_farewell_node(self, agent_instance: Any, agent_name: str):
        """
        Crea un método de nodo especial para el agente de despedida.

        Args:
            agent_instance: Instancia del agente farewell
            agent_name: Nombre del agente

        Returns:
            Método async que ejecuta el agente y marca la conversación como completa
        """

        async def farewell_node(state: LangGraphState) -> Dict[str, Any]:
            result = await self._execute_agent_node(state, agent_instance, agent_name)
            # Marcar la conversación como completa cuando es despedida
            result["is_complete"] = True
            return result

        return farewell_node

    def _create_agent_nodes(self):
        """
        Crea dinámicamente todos los métodos de nodos de agentes.
        Este método elimina la necesidad de definir manualmente cada método _*_agent_node.
        """
        agent_mapping = self._get_agent_mapping()

        for agent_name, agent_instance in agent_mapping.items():
            method_name = f"_{agent_name}_node"

            # Caso especial para farewell_agent
            if agent_name == AgentType.FAREWELL_AGENT.value:
                node_method = self._create_farewell_node(agent_instance, agent_name)
            else:
                node_method = self._create_standard_node(agent_instance, agent_name)

            # Asignar el método dinámicamente a la instancia
            setattr(self, method_name, node_method)
            logger.debug(f"Created dynamic node method: {method_name}")

    async def _execute_agent_node(self, state: LangGraphState, agent: Any, agent_name: str) -> Dict[str, Any]:
        """
        Ejecuta un agente especializado y actualiza el estado.

        Args:
            state: Estado actual
            agent: Instancia del agente a ejecutar
            agent_name: Nombre del agente

        Returns:
            Actualizaciones al estado
        """
        try:
            # Debug del estado de entrada
            logger.info(f"=== AGENT EXECUTION DEBUG: {agent_name} ===")
            logger.info(f"[AGENT EXEC] State keys: {list(state.keys())}")
            logger.info(f"[AGENT EXEC] Current agent: {state.get('current_agent')}")
            logger.info(f"[AGENT EXEC] Agent history: {state.get('agent_history', [])}")

            # Obtener el último mensaje
            messages = state.get("messages", [])
            if not messages:
                logger.error(f"[AGENT EXEC] No messages to process for {agent_name}")
                return {"error": "No messages to process", "current_agent": agent_name}

            # Buscar el último mensaje del usuario
            user_message = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content
                    break

            if not user_message:
                # Si no hay mensaje de usuario, usar el último mensaje disponible
                user_message = messages[-1].content if messages else ""

            logger.info(f"[AGENT EXEC] Processing message: {user_message[:100] if user_message else 'Empty'}...")
            logger.info(f"[AGENT EXEC] About to execute {agent_name} agent")

            # Convertir messages para el state_dict
            messages_dict = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    messages_dict.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages_dict.append({"role": "assistant", "content": msg.content})

            # Crear state_dict para el agente
            state_dict = {
                "messages": messages_dict,
                "customer_data": state.get("customer_data", {}),
                "current_agent": state.get("current_agent"),
                "agent_history": state.get("agent_history", []),
                "error_count": state.get("error_count", 0),
            }

            # Ejecutar el agente
            result = await agent._process_internal(message=user_message, state_dict=state_dict)
            logger.info(f"[AGENT EXEC] Agent {agent_name} returned result keys: {list(result.keys())}")
            logger.info(f"[AGENT EXEC] Agent response preview: {str(result)[:200]}...")

            # Preparar actualizaciones
            updates = {
                "current_agent": agent_name,
                "agent_history": state.get("agent_history", []) + [agent_name],
            }

            # Añadir mensaje de respuesta si existe
            if "messages" in result:
                new_messages = []
                for msg_dict in result["messages"]:
                    if msg_dict.get("role") == "assistant":
                        new_messages.append(AIMessage(content=msg_dict["content"]))
                    elif msg_dict.get("role") == "user":
                        new_messages.append(HumanMessage(content=msg_dict["content"]))
                if new_messages:
                    updates["messages"] = new_messages

            # Copiar otros campos del resultado
            for key in ["retrieved_data", "is_complete", "error_count"]:
                if key in result:
                    updates[key] = result[key]

            logger.info(f"[AGENT EXEC] Final updates from {agent_name}: {list(updates.keys())}")
            logger.info(f"[AGENT EXEC] is_complete: {updates.get('is_complete', False)}")
            logger.info(f"=== AGENT EXECUTION COMPLETE: {agent_name} ===")
            return updates

        except Exception as e:
            logger.error(f"Error in {agent_name} node: {str(e)}")
            return {
                "error": str(e),
                "error_count": state.get("error_count", 0) + 1,
                "current_agent": agent_name,
                "messages": [
                    AIMessage(content="Disculpa, tuve un problema procesando tu solicitud. ¿Podrías intentar de nuevo?")
                ],
            }

    # Métodos de routing
    def _route_to_agent(self, state: LangGraphState) -> str:
        """
        Determina a qué agente enviar el mensaje basándose en el análisis del supervisor.

        Args:
            state: Estado actual del graph

        Returns:
            Nombre del siguiente nodo o "__end__"
        """
        # Debugging completo del estado
        logger.info("=== ROUTING DEBUG START ===")
        logger.info(f"State keys present: {list(state.keys())}")
        logger.info(f"next_agent from state: '{state.get('next_agent')}'")
        logger.info(f"current_agent: '{state.get('current_agent')}'")
        logger.info(f"is_complete: {state.get('is_complete')}")
        logger.info(f"human_handoff_requested: {state.get('human_handoff_requested')}")
        logger.info(f"agent_history: {state.get('agent_history', [])}")

        # Si la conversación está completa o hay handoff humano, terminar
        if state.get("is_complete") or state.get("human_handoff_requested"):
            logger.info("[ROUTING] Ending due to is_complete or human_handoff")
            return "__end__"

        # Obtener el siguiente agente del estado
        next_agent = state.get("next_agent")
        logger.info(f"[ROUTING] next_agent value: '{next_agent}', type: {type(next_agent)}")

        if not next_agent:
            logger.warning("[ROUTING] No next_agent in state, routing to fallback")
            return AgentType.FALLBACK_AGENT.value

        # Verificar que el agente existe en los nodos válidos
        valid_agents = get_agent_routing_literal()
        logger.info(f"[ROUTING] Valid agents: {valid_agents}")
        logger.info(f"[ROUTING] Is '{next_agent}' in valid agents? {next_agent in valid_agents}")

        if next_agent not in valid_agents:
            logger.warning(f"[ROUTING] Invalid agent '{next_agent}', routing to fallback")
            return AgentType.FALLBACK_AGENT.value

        logger.info(f"[ROUTING SUCCESS] Routing to agent: {next_agent}")
        logger.info("=== ROUTING DEBUG END ===")
        return next_agent

    def _should_continue(self, state: LangGraphState) -> Literal["continue", "__end__"]:
        """
        Determina si continuar la conversación o terminar.

        Args:
            state: Estado actual

        Returns:
            "continue" para volver al supervisor, "__end__" para terminar
        """
        # Terminar si la conversación está completa
        if state.get("is_complete"):
            logger.info("Conversation marked as complete, ending")
            return "__end__"

        # Terminar si hay handoff humano
        if state.get("human_handoff_requested"):
            logger.info("Human handoff requested, ending")
            return "__end__"

        # Terminar si hay demasiados errores
        error_count = state.get("error_count", 0)
        if error_count >= 3:
            logger.warning(f"Too many errors ({error_count}), ending conversation")
            return "__end__"

        # Por defecto, volver al supervisor para posible re-routing
        return "continue"

    # Métodos públicos
    def initialize(self, db_url: Optional[str] = None):
        """
        Inicializa y compila el graph con checkpointer opcional.

        Args:
            db_url: URL de la base de datos para checkpointing (opcional)
        """
        try:
            # Configurar checkpointer si está disponible
            checkpointer = None
            if db_url and self.use_postgres_checkpointer:
                try:
                    checkpointer = PostgresSaver.from_conn_string(db_url)
                    logger.info("PostgreSQL checkpointer configured")
                except Exception as e:
                    logger.warning(f"Could not setup PostgreSQL checkpointer: {e}")

            # Compilar el graph
            self.app = self.graph.compile(checkpointer=checkpointer)
            logger.info("Graph compiled successfully")

        except Exception as e:
            logger.error(f"Error initializing graph: {e}")
            raise

    async def invoke(self, message: str, conversation_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Procesa un mensaje a través del graph.

        Args:
            message: Mensaje del usuario
            conversation_id: ID de la conversación para checkpointing
            **kwargs: Parámetros adicionales

        Returns:
            Respuesta del graph
        """
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        try:
            # Preparar el estado inicial con HumanMessage
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id or "default",
                "timestamp": datetime.now().isoformat(),
                **kwargs,
            }

            # Configurar el thread_id para checkpointing
            config = {}
            if conversation_id:
                config["configurable"] = {"thread_id": conversation_id}

            # Ejecutar el graph
            result = await self.app.ainvoke(initial_state, config)

            return result

        except Exception as e:
            logger.error(f"Error invoking graph: {e}")
            raise
