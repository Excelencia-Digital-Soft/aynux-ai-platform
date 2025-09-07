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
    OrchestratorAgent,
    ProductAgent,
    PromotionsAgent,
    SupervisorAgent,
    SupportAgent,
    TrackingAgent,
)
from .utils.tracing import trace_async_method, trace_context, trace_sync_method

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

        # Add orchestrator and supervisor
        workflow.add_node(AgentType.ORCHESTRATOR.value, self._orchestrator_node)
        workflow.add_node(AgentType.SUPERVISOR.value, self._supervisor_node)

        # Add all other agents dynamically using the generated node methods
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value
            node_method = getattr(self, f"_{agent_name}_node")
            workflow.add_node(agent_name, node_method)

        # Definir punto de entrada: ahora es el orchestrator
        workflow.set_entry_point(AgentType.ORCHESTRATOR.value)

        # Añadir aristas condicionales desde orchestrator usando AgentType
        orchestrator_edges_mapping = {agent_type.value: agent_type.value for agent_type in get_non_supervisor_agents()}
        orchestrator_edges_mapping["__end__"] = END

        workflow.add_conditional_edges(AgentType.ORCHESTRATOR.value, self._route_to_agent, orchestrator_edges_mapping)

        # Configurar el flujo: todos los agentes especializados van al supervisor para evaluación
        for agent_type in get_non_supervisor_agents():
            agent = agent_type.value
            workflow.add_edge(agent, AgentType.SUPERVISOR.value)

        # Supervisor decide si continuar o terminar
        supervisor_edges_mapping = {
            "continue": AgentType.ORCHESTRATOR.value,  # Re-routing: volver al orchestrator
            "__end__": END,
        }
        workflow.add_conditional_edges(AgentType.SUPERVISOR.value, self._supervisor_should_continue, supervisor_edges_mapping)

        return workflow

    # Métodos de inicialización
    def _init_integrations(self):
        """Inicializa las integraciones externas"""
        # Get integrations config from dict
        integrations_config = self.config.get('integrations', {})
        # If it's a Pydantic model, convert to dict
        if hasattr(integrations_config, 'model_dump'):
            integrations_config = integrations_config.model_dump()
        
        self.ollama = OllamaIntegration(integrations_config.get("ollama", {}))
        self.chroma = ChromaDBIntegration(integrations_config.get("chromadb", {}))
        self.postgres = PostgreSQLIntegration(integrations_config.get("postgres", {}))

    def _init_agents(self):
        """Inicializa agentes especializados"""
        try:
            # Get agent configs from dict
            agent_configs = self.config.get('agents', {})
            
            # Get individual agent configs
            orchestrator_config = {}
            supervisor_config = self.config.get('supervisor', {})
            # If it's a Pydantic model, convert to dict
            if hasattr(supervisor_config, 'model_dump'):
                supervisor_config = supervisor_config.model_dump()

            # Initialize orchestrator and supervisor agents
            self.orchestrator_agent = OrchestratorAgent(ollama=self.ollama, config=orchestrator_config)
            self.supervisor_agent = SupervisorAgent(ollama=self.ollama, config=supervisor_config)

            # Initialize agents explicitly using schema for configuration
            self.product_agent = ProductAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_configs.get("product", {}).model_dump() if hasattr(agent_configs.get("product", {}), 'model_dump') else {}
            )

            self.category_agent = CategoryAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_configs.get("category", {}).model_dump() if hasattr(agent_configs.get("category", {}), 'model_dump') else {}
            )

            self.data_insights_agent = DataInsightsAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_configs.get("data_insights", {}).model_dump() if hasattr(agent_configs.get("data_insights", {}), 'model_dump') else {}
            )

            self.promotions_agent = PromotionsAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_configs.get("promotions", {}).model_dump() if hasattr(agent_configs.get("promotions", {}), 'model_dump') else {}
            )

            self.tracking_agent = TrackingAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_configs.get("tracking", {}).model_dump() if hasattr(agent_configs.get("tracking", {}), 'model_dump') else {}
            )

            self.support_agent = SupportAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_configs.get("support", {}).model_dump() if hasattr(agent_configs.get("support", {}), 'model_dump') else {}
            )

            self.invoice_agent = InvoiceAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_configs.get("invoice", {}).model_dump() if hasattr(agent_configs.get("invoice", {}), 'model_dump') else {}
            )

            self.fallback_agent = FallbackAgent(
                ollama=self.ollama, postgres=self.postgres, config={}
            )

            self.farewell_agent = FarewellAgent(
                ollama=self.ollama, postgres=self.postgres, config={}
            )

            logger.info("Agents initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise

    # Métodos de nodos del graph
    @trace_async_method(
        name="orchestrator_node",
        run_type="langgraph_node",
        metadata={"node_type": "orchestrator", "role": "intent_routing"},
        extract_state=True,
    )
    async def _orchestrator_node(self, state: LangGraphState) -> Dict[str, Any]:
        """
        Nodo del orchestrator que analiza el mensaje y decide el routing inicial.

        Args:
            state: Estado actual del graph

        Returns:
            Actualizaciones al estado con decisión de routing
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
                user_message = messages[-1].content if messages else ""

            logger.info(f"Orchestrator processing: {user_message[:100] if user_message else 'Empty message'}...")

            # Convertir messages para el state_dict
            messages_dict = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    messages_dict.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages_dict.append({"role": "assistant", "content": msg.content})

            # Crear state_dict para el orchestrator
            state_dict = {
                "messages": messages_dict,
                "customer_data": state.get("customer_data", {}),
                "current_agent": state.get("current_agent"),
                "agent_history": state.get("agent_history", []),
                "routing_attempts": state.get("routing_attempts", 0),
            }

            # Procesar con el orchestrator agent
            result = await self.orchestrator_agent._process_internal(message=user_message, state_dict=state_dict)

            # El orchestrator devuelve el siguiente agente y análisis
            next_agent = result.get("next_agent", "fallback_agent")

            # Actualizar el estado con la decisión del orchestrator
            updates = {
                "current_agent": "orchestrator",
                "next_agent": next_agent,
                "routing_decision": result.get("routing_decision", {}),
                "orchestrator_analysis": result.get("orchestrator_analysis", {}),
                "routing_attempts": result.get("routing_attempts", 0),
            }

            return updates

        except Exception as e:
            logger.error(f"Error in orchestrator node: {str(e)}")
            return {"next_agent": "fallback_agent", "error": str(e), "error_count": state.get("error_count", 0) + 1}

    @trace_async_method(
        name="supervisor_node",
        run_type="langgraph_node",
        metadata={"node_type": "supervisor", "role": "response_evaluation"},
        extract_state=True,
    )
    async def _supervisor_node(self, state: LangGraphState) -> Dict[str, Any]:
        """
        Nodo del supervisor que evalúa la respuesta del agente anterior y decide el flujo.

        Args:
            state: Estado actual del graph

        Returns:
            Actualizaciones al estado
        """
        try:
            # Obtener el último mensaje del usuario (para contexto)
            messages = state.get("messages", [])
            if not messages:
                return {"is_complete": True, "error": "No messages in state"}

            # Buscar el último mensaje del usuario
            user_message = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    user_message = msg.content
                    break

            if not user_message:
                user_message = ""

            logger.info(f"Supervisor evaluating response for: {user_message[:100] if user_message else 'Empty message'}...")

            # Convertir messages para el state_dict
            messages_dict = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    messages_dict.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages_dict.append({"role": "assistant", "content": msg.content})

            # Crear state_dict para el supervisor con información completa del estado
            state_dict = {
                "messages": messages_dict,
                "customer": state.get("customer"),
                "conversation": state.get("conversation"),
                "current_agent": state.get("current_agent"),
                "agent_history": state.get("agent_history", []),
                "error_count": state.get("error_count", 0),
                "supervisor_retry_count": state.get("supervisor_retry_count", 0),
                "routing_attempts": state.get("routing_attempts", 0),
                "agent_responses": state.get("agent_responses", []),
                "retrieved_data": state.get("retrieved_data", {}),
            }

            # Procesar con el supervisor agent para evaluación de respuesta
            result = await self.supervisor_agent._process_internal(message=user_message, state_dict=state_dict)

            # El supervisor ahora evalúa calidad y decide el flujo
            updates = {
                "current_agent": "supervisor", 
                "supervisor_evaluation": result.get("supervisor_evaluation", {}),
                "conversation_flow": result.get("conversation_flow", {}),
                "supervisor_analysis": result.get("supervisor_analysis", {}),
                "is_complete": result.get("is_complete", False),
                "needs_re_routing": result.get("needs_re_routing", False),
                "human_handoff_requested": result.get("human_handoff_requested", False),
                "supervisor_retry_count": state.get("supervisor_retry_count", 0) + 1,
            }

            # Si necesita re-routing, incrementar contador de intentos de routing
            if result.get("needs_re_routing"):
                updates["routing_attempts"] = state.get("routing_attempts", 0) + 1
                updates["next_agent"] = "orchestrator"  # Volver al orchestrator para nuevo routing

            # Si necesita escalamiento humano, marcar conversación como completa
            if result.get("human_handoff_requested"):
                updates["is_complete"] = True
                updates["requires_human"] = True

            return updates

        except Exception as e:
            logger.error(f"Error in supervisor node: {str(e)}")
            return {
                "is_complete": True, 
                "error": str(e), 
                "error_count": state.get("error_count", 0) + 1
            }

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

    @trace_async_method(
        name="execute_agent_node",
        run_type="langgraph_node",
        metadata={"operation": "agent_execution"},
        extract_state=True,
    )
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
            # Track agent transition in conversation tracker
            conv_id = state.get("conversation_id")
            current_agent = state.get("current_agent")
            conv_tracker = self.conversation_tracers.get(conv_id) if conv_id else None

            if conv_tracker and current_agent:
                conv_tracker.add_agent_transition(
                    from_agent=current_agent, to_agent=agent_name, reason="Supervisor routing decision"
                )

            # Debug del estado de entrada
            logger.info(f"=== AGENT EXECUTION DEBUG: {agent_name} ===")
            logger.info(f"[AGENT EXEC] State keys: {list(state.keys())}")
            logger.info(f"[AGENT EXEC] Current agent: {state.get('current_agent')}")
            logger.info(f"[AGENT EXEC] Agent history: {state.get('agent_history', [])}")
            logger.info(f"[AGENT EXEC] Conversation ID: {conv_id}")
            logger.info(f"[AGENT EXEC] Agent transition: {current_agent} -> {agent_name}")

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
    @trace_sync_method(name="route_to_agent", run_type="routing", metadata={"operation": "agent_selection"})
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

    @trace_sync_method(name="should_continue", run_type="routing", metadata={"operation": "continuation_decision"})
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

    @trace_sync_method(name="supervisor_should_continue", run_type="routing", metadata={"operation": "supervisor_flow_decision"})
    def _supervisor_should_continue(self, state: LangGraphState) -> Literal["continue", "__end__"]:
        """
        Determina si el supervisor debe continuar o terminar la conversación basándose en su evaluación.

        Args:
            state: Estado actual

        Returns:
            "continue" para re-routing al orchestrator, "__end__" para terminar
        """
        # Verificar si la conversación está marcada como completa
        if state.get("is_complete"):
            logger.info("Supervisor: Conversation marked as complete, ending")
            return "__end__"

        # Verificar si hay handoff humano solicitado
        if state.get("human_handoff_requested"):
            logger.info("Supervisor: Human handoff requested, ending")
            return "__end__"

        # Verificar si necesita re-routing (supervisora decidió que la respuesta no fue buena)
        if state.get("needs_re_routing"):
            # Verificar si ya se intentaron demasiados re-routings
            routing_attempts = state.get("routing_attempts", 0)
            supervisor_retry_count = state.get("supervisor_retry_count", 0)
            
            if routing_attempts >= 3 or supervisor_retry_count >= 3:
                logger.warning(f"Supervisor: Too many routing attempts ({routing_attempts}) or retries ({supervisor_retry_count}), ending")
                return "__end__"
            
            logger.info("Supervisor: Needs re-routing, continuing to orchestrator")
            return "continue"

        # Verificar si hay demasiados errores generales
        error_count = state.get("error_count", 0)
        if error_count >= 3:
            logger.warning(f"Supervisor: Too many errors ({error_count}), ending conversation")
            return "__end__"

        # Verificar evaluación del supervisor
        conversation_flow = state.get("conversation_flow", {})
        
        # Si el supervisor determinó que debe terminar
        flow_decision = conversation_flow.get("decision_type")
        if flow_decision in ["conversation_complete", "conversation_end", "human_handoff", "error_end"]:
            logger.info(f"Supervisor: Flow decision '{flow_decision}', ending")
            return "__end__"

        # Si necesita re-routing según la evaluación
        if flow_decision == "re_route":
            logger.info("Supervisor: Re-route decision, continuing to orchestrator")
            return "continue"

        # Por defecto, si llegamos aquí es porque la respuesta fue satisfactoria
        logger.info("Supervisor: Response satisfactory, ending conversation")
        return "__end__"

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

    @trace_async_method(
        name="graph_invoke",
        run_type="chain",
        metadata={"component": "langgraph", "operation": "conversation_processing"},
        extract_state=False,
    )
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
            # Inicializar conversation tracker si está habilitado el tracing
            conv_id = conversation_id or "default"
            user_id = kwargs.get("user_id")

            if self.tracer.config.tracing_enabled and conv_id not in self.conversation_tracers:
                self.conversation_tracers[conv_id] = ConversationTracer(conv_id, user_id)
                logger.info(f"Started conversation tracking for {conv_id}")

            # Obtener el tracker para esta conversación
            conv_tracker = self.conversation_tracers.get(conv_id)

            if conv_tracker:
                conv_tracker.add_message("user", message, {"timestamp": datetime.now().isoformat()})

            # Preparar el estado inicial con HumanMessage
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conv_id,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                **kwargs,
            }

            # Configurar el thread_id para checkpointing
            config = {}
            if conv_id:
                config["configurable"] = {"thread_id": conv_id}

            # Usar trace context para la ejecución del graph completo
            async with trace_context(
                name=f"conversation_{conv_id}",
                metadata={
                    "conversation_id": conv_id,
                    "user_id": user_id,
                    "message_preview": message[:100],
                    "graph_type": "ecommerce_multi_agent",
                },
                tags=["langgraph", "conversation", "multi_agent"],
            ):
                # Ejecutar el graph
                result = await self.app.ainvoke(initial_state, config)

                # Registrar la respuesta en el tracker
                if conv_tracker and result.get("messages"):
                    for msg in result["messages"]:
                        if hasattr(msg, "content"):
                            conv_tracker.add_message(
                                "assistant",
                                msg.content,
                                {"agent": result.get("current_agent"), "timestamp": datetime.now().isoformat()},
                            )

                return result

        except Exception as e:
            logger.error(f"Error invoking graph: {e}")
            raise
