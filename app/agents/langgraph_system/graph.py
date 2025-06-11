"""
Graph principal del sistema multi-agente LangGraph
"""

import logging
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.agents.langgraph_system.agents import (
    CategoryAgent,
    InvoiceAgent,
    ProductAgent,
    PromotionsAgent,
    SupportAgent,
    TrackingAgent,
)
from app.agents.langgraph_system.integrations import (
    ChromaDBIntegration,
    OllamaIntegration,
    PostgreSQLIntegration,
)
from app.agents.langgraph_system.integrations.postgres_checkpointer import (
    get_checkpointer_manager,
    initialize_checkpointer,
)
from app.agents.langgraph_system.models import (
    AgentResponse,
    SharedState,
)
from app.agents.langgraph_system.router import IntentRouter, SupervisorAgent
from app.agents.langgraph_system.state_schema import GraphState

logger = logging.getLogger(__name__)


class EcommerceAssistantGraph:
    """Graph principal del asistente e-commerce multi-agente"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

        # Inicializar integraciones
        self._init_integrations()

        # Inicializar componentes principales
        self._init_core_components()

        # Inicializar agentes especializados
        self._init_agents()

        # Construir el graph
        self.graph = self._build_graph()

        # Compilar el graph (checkpointer se configura en initialize si está disponible)
        self.app = None
        self.checkpointer_manager = None
        self.use_postgres_checkpointer = False  # Set to False for now due to setup issues

        logger.info("EcommerceAssistantGraph initialized successfully")

    async def initialize(self):
        """Inicializa el sistema de forma asíncrona"""
        try:
            # Inicializar checkpointer PostgreSQL
            if self.use_postgres_checkpointer:
                try:
                    self.checkpointer_manager = get_checkpointer_manager()

                    # Verificar salud del checkpointer
                    checkpointer_healthy = await initialize_checkpointer()

                    if checkpointer_healthy:
                        # Obtener checkpointer asíncrono para compilación
                        logger.info("Compiling graph with PostgreSQL checkpointer")

                        # Crear checkpointer temporal para compilación
                        async with self.checkpointer_manager.get_async_checkpointer() as temp_checkpointer:
                            # Store the checkpointer manager for later use
                            self.postgres_checkpointer = temp_checkpointer

                        # Compilar con un checkpointer nuevo pero de la misma configuración
                        async with self.checkpointer_manager.get_async_checkpointer() as checkpointer:
                            self.app = self.graph.compile(checkpointer=checkpointer)
                            logger.info("Graph compiled successfully with PostgreSQL checkpointer")
                    else:
                        logger.warning("PostgreSQL checkpointer unhealthy, falling back to no checkpointer")
                        self.app = self.graph.compile()

                except Exception as e:
                    logger.error(f"Error initializing PostgreSQL checkpointer: {e}")
                    logger.info("Falling back to no checkpointer")
                    self.app = self.graph.compile()
            else:
                # Compilar sin checkpointer
                logger.info("Compiling graph without checkpointer (testing mode)")
                self.app = self.graph.compile()

            logger.info("Graph compilation completed successfully")

        except Exception as e:
            logger.error(f"Error during graph initialization: {e}")
            raise

    def _init_integrations(self):
        """Inicializa las integraciones con servicios externos"""
        # Ollama para LLMs
        self.ollama = OllamaIntegration()
        self.llm = self.ollama.get_llm(temperature=0.7)

        # ChromaDB para vectores
        self.chroma = ChromaDBIntegration()
        self.vector_store = self.chroma.get_langchain_vectorstore("products")

        # PostgreSQL para checkpointing
        self.postgres = PostgreSQLIntegration()

        logger.info("Integrations initialized")

    def _init_core_components(self):
        """Inicializa componentes principales del sistema"""
        # Router de intenciones
        self.router = IntentRouter(self.llm)

        # Supervisor
        self.supervisor = SupervisorAgent(self.router)

        logger.info("Core components initialized")

    def _init_agents(self):
        """Inicializa todos los agentes especializados"""
        self.agents = {
            "category_agent": CategoryAgent(
                vector_store=self.vector_store, llm=self.llm, db_connection=self.config.get("db_connection")
            ),
            "product_agent": ProductAgent(
                vector_store=self.vector_store, db_connection=self.config.get("db_connection"), llm=self.llm
            ),
            "promotions_agent": PromotionsAgent(
                db_connection=self.config.get("db_connection"),
                cache_service=self.config.get("cache_service"),
                llm=self.llm,
            ),
            "tracking_agent": TrackingAgent(
                db_connection=self.config.get("db_connection"),
                shipping_apis=self.config.get("shipping_apis"),
                llm=self.llm,
            ),
            "support_agent": SupportAgent(
                vector_store=self.vector_store, knowledge_base=self.config.get("knowledge_base"), llm=self.llm
            ),
            "invoice_agent": InvoiceAgent(
                db_connection=self.config.get("db_connection"), invoice_api=self.config.get("invoice_api"), llm=self.llm
            ),
        }

        logger.info(f"Initialized {len(self.agents)} specialized agents")

    def _build_graph(self) -> StateGraph:
        """Construye el StateGraph de LangGraph"""
        # Crear el StateGraph con el schema TypedDict
        workflow = StateGraph(GraphState)

        # Añadir nodo supervisor
        workflow.add_node("supervisor", self._supervisor_node)

        # Añadir agentes especializados
        for agent_name, agent in self.agents.items():
            workflow.add_node(agent_name, self._create_agent_node(agent))

        # Añadir generador de respuesta
        workflow.add_node("response_generator", self._response_generator_node)

        # Añadir nodo de transferencia humana
        workflow.add_node("human_handoff", self._human_handoff_node)

        # Definir punto de entrada
        workflow.set_entry_point("supervisor")

        # Routing desde supervisor
        workflow.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "category_agent": "category_agent",
                "product_agent": "product_agent",
                "promotions_agent": "promotions_agent",
                "tracking_agent": "tracking_agent",
                "support_agent": "support_agent",
                "invoice_agent": "invoice_agent",
                "human_handoff": "human_handoff",
                "end": END,
            },
        )

        # Todos los agentes van al generador de respuesta
        for agent_name in self.agents.keys():
            workflow.add_edge(agent_name, "response_generator")

        # Generador de respuesta puede continuar o terminar
        workflow.add_conditional_edges(
            "response_generator", self._check_completion, {"continue": "supervisor", "end": END}
        )

        # Handoff humano termina el flujo
        workflow.add_edge("human_handoff", END)

        return workflow

    def _dict_to_shared_state(self, state_dict: Dict[str, Any]) -> SharedState:
        """Convierte un diccionario a SharedState manejando campos faltantes"""
        if not isinstance(state_dict, dict):
            return state_dict

        # Asegurarse de que messages existe
        if "messages" not in state_dict:
            state_dict["messages"] = []

        # Crear SharedState con valores por defecto para campos faltantes
        init_kwargs = {}
        for field in [
            "messages",
            "customer",
            "conversation",
            "current_intent",
            "intent_history",
            "current_agent",
            "agent_history",
            "agent_responses",
            "retrieved_data",
            "requires_human",
            "is_complete",
            "error_count",
            "max_errors",
            "conversation_checkpoint_id",
            "cache_keys",
            "total_processing_time_ms",
        ]:
            if field in state_dict:
                init_kwargs[field] = state_dict[field]

        return SharedState(**init_kwargs)

    async def _supervisor_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Nodo del supervisor que coordina el flujo"""
        try:
            logger.debug(f"Processing supervisor node with state type: {type(state)}")
            logger.debug(f"State keys: {list(state.keys()) if isinstance(state, dict) else 'Not a dict'}")

            # Log para verificar qué campos están llegando
            if isinstance(state, dict):
                logger.debug(f"State has requires_human: {'requires_human' in state}")
                logger.debug(f"State has error_count: {'error_count' in state}")
                logger.debug(f"State has max_errors: {'max_errors' in state}")

            # Procesar directamente con el supervisor usando el diccionario
            updated_state = await self.supervisor.process(state)

            # Retornar el diccionario actualizado
            return updated_state

        except Exception as e:
            logger.error(f"Error in supervisor node: {e}")
            logger.error(f"State type was: {type(state)}")
            if isinstance(state, dict):
                logger.error(f"State keys: {list(state.keys())}")

            # Crear estado de error directamente en el diccionario
            error_count = state.get("error_count", 0) + 1
            state["error_count"] = error_count

            # Fallback a agente de categorías
            state["current_agent"] = "category_agent"
            agent_history = state.get("agent_history", [])
            if "category_agent" not in agent_history:
                agent_history.append("category_agent")
                state["agent_history"] = agent_history

            return state

    def _create_agent_node(self, agent):
        """Crea un nodo para un agente específico"""

        async def agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
            try:
                logger.debug(f"Processing {agent.name} node")

                # Convertir dict a SharedState si es necesario
                shared_state = self._dict_to_shared_state(state)

                # Procesar con el agente
                updated_state = await agent.process(shared_state)

                # Retornar como dict para LangGraph
                return updated_state.model_dump()

            except Exception as e:
                logger.error(f"Error in {agent.name} node: {e}")

                # Crear estado de error
                shared_state = self._dict_to_shared_state(state)

                shared_state.increment_error()

                # Crear respuesta de error
                error_response = AgentResponse(
                    agent_name=agent.name,
                    response_text="Disculpa, tuve un problema procesando tu solicitud. ¿Podrías intentar de nuevo?",
                    success=False,
                    error=str(e),
                )
                shared_state.add_agent_response(error_response)

                return shared_state.model_dump()

        return agent_node

    async def _response_generator_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Genera la respuesta final consolidada"""
        try:
            logger.debug("Processing response generator node")

            # Convertir dict a SharedState si es necesario
            shared_state = self._dict_to_shared_state(state)

            # Obtener la última respuesta de agente
            last_response = shared_state.get_last_agent_response()

            if last_response and last_response.success:
                # Añadir como mensaje del asistente
                shared_state.messages.append(AIMessage(content=last_response.response_text))

                # Determinar si la conversación está completa
                shared_state.is_complete = self._is_conversation_complete(shared_state)

                logger.info(f"Generated response from {last_response.agent_name}")
            else:
                # Respuesta de error
                error_msg = "Lo siento, no pude procesar tu solicitud en este momento."
                shared_state.messages.append(AIMessage(content=error_msg))
                shared_state.is_complete = True

                logger.warning("Generated error response")

            return shared_state.model_dump()

        except Exception as e:
            logger.error(f"Error in response generator: {e}")

            # Crear estado de error
            if isinstance(state, dict):
                shared_state = SharedState(**state)
            else:
                shared_state = state

            # Respuesta de fallback
            fallback_msg = "Disculpa, tuve un problema interno. ¿Podrías intentar de nuevo?"
            shared_state.messages.append(AIMessage(content=fallback_msg))
            shared_state.is_complete = True

            return shared_state.model_dump()

    async def _human_handoff_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Nodo para transferencia a agente humano"""
        try:
            logger.info("Processing human handoff")

            # Convertir dict a SharedState si es necesario
            if isinstance(state, dict):
                shared_state = SharedState(**state)
            else:
                shared_state = state

            # Preparar información para el agente humano
            handoff_info = self._prepare_handoff_info(shared_state)

            # Crear mensaje de transferencia
            handoff_message = (
                "Te estoy transfiriendo con un agente especializado que podrá "
                "ayudarte mejor con tu consulta. En un momento se comunicará contigo."
            )

            shared_state.messages.append(AIMessage(content=handoff_message))
            shared_state.requires_human = True
            shared_state.is_complete = True

            # Aquí se integraría con sistema de tickets o chat humano
            # Por ahora solo loggeamos
            logger.info(f"Human handoff prepared: {handoff_info}")

            return shared_state.model_dump()

        except Exception as e:
            logger.error(f"Error in human handoff: {e}")

            # Crear estado de error
            if isinstance(state, dict):
                shared_state = SharedState(**state)
            else:
                shared_state = state

            # Mensaje de error en transferencia
            error_msg = "Hubo un problema con la transferencia. Te contactaremos pronto."
            shared_state.messages.append(AIMessage(content=error_msg))
            shared_state.is_complete = True

            return shared_state.model_dump()

    def _route_from_supervisor(self, state: Dict[str, Any]) -> str:
        """Determina el routing desde el supervisor"""
        # Trabajar directamente con el diccionario
        # Verificar si requiere transferencia humana
        if state.get("requires_human", False):
            return "human_handoff"

        # Verificar si está completo
        if state.get("is_complete", False):
            return "end"

        # Dirigir al agente determinado
        return state.get("current_agent") or "end"

    def _check_completion(self, state: Dict[str, Any]) -> str:
        """Verifica si la conversación está completa"""
        # Trabajar directamente con el diccionario
        if state.get("is_complete", False) or state.get("requires_human", False):
            return "end"

        # Si hay demasiados intercambios, terminar
        messages = state.get("messages", [])
        if len(messages) > 20:
            return "end"

        # Si hay demasiados errores, terminar
        error_count = state.get("error_count", 0)
        max_errors = state.get("max_errors", 3)
        if error_count >= max_errors:
            return "end"

        # Continuar si hay una respuesta que requiere seguimiento
        agent_responses = state.get("agent_responses", [])
        if agent_responses:
            last_response = agent_responses[-1]
            if last_response and last_response.get("response_text", "").count("?") > 0:
                return "continue"

        return "end"

    def _is_conversation_complete(self, state: SharedState) -> bool:
        """Determina si la conversación está completa"""
        last_response = state.get_last_agent_response()

        if not last_response:
            return True

        # Si hay preguntas, no está completo
        if "?" in last_response.response_text:
            return False

        # Si es una respuesta informativa completa, está completo
        if last_response.success and len(last_response.response_text) > 50:
            return True

        return False

    def _prepare_handoff_info(self, state: SharedState) -> Dict[str, Any]:
        """Prepara información para transferencia humana"""
        return {
            "customer_id": state.customer.customer_id if state.customer else None,
            "conversation_id": state.conversation.conversation_id if state.conversation else None,
            "last_intent": state.current_intent.primary_intent if state.current_intent else None,
            "error_count": state.error_count,
            "agents_involved": state.agent_history,
            "conversation_summary": state.get_context_summary(),
            "last_message": state.get_last_user_message(),
        }

    async def process_message(
        self, message: str, conversation_id: str, customer_data: Dict[str, Any], session_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario a través del graph

        Args:
            message: Mensaje del usuario
            conversation_id: ID de la conversación
            customer_data: Datos del cliente
            session_config: Configuración de sesión

        Returns:
            Respuesta procesada del sistema
        """
        try:
            # Verificar si el app está inicializado
            if not self.app:
                raise RuntimeError("Graph not initialized. Call initialize() first.")

            # Crear estado inicial usando TypedDict
            state_dict: GraphState = {
                "messages": [HumanMessage(content=message)],
                "customer": customer_data,
                "conversation": {"conversation_id": conversation_id, "session_id": f"session_{conversation_id}"},
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
                "conversation_checkpoint_id": None,
                "cache_keys": [],
                "total_processing_time_ms": 0.0,
            }

            logger.info(f"Processing message for conversation {conversation_id}")

            # Si tenemos checkpointer, intentar obtener estado previo
            if self.checkpointer_manager:
                config = {"configurable": {"thread_id": conversation_id, **(session_config or {})}}

                try:
                    # Obtener estado actual
                    current_state = await self.app.aget_state(config)

                    if current_state.values:
                        # Estado existente - actualizar con nuevo mensaje
                        state_dict = current_state.values
                        state_dict["messages"].append(HumanMessage(content=message))

                        # Resetear estado de completado si era final
                        if state_dict.get("is_complete"):
                            state_dict["is_complete"] = False
                except Exception as e:
                    logger.warning(f"Could not retrieve state from checkpointer: {e}")
                    # Continuar con estado nuevo
            else:
                # Sin checkpointer, usar configuración vacía
                config = {}

            # Procesar con el graph
            logger.debug(f"State dict keys before invoke: {list(state_dict.keys())}")
            logger.debug(f"State dict has requires_human: {'requires_human' in state_dict}")
            final_state = await self.app.ainvoke(state_dict, config)

            # Extraer respuesta
            last_message = final_state["messages"][-1]

            # Preparar respuesta
            # final_state es un dict, no un objeto
            response = {
                "success": True,
                "response": last_message.content,
                "conversation_id": conversation_id,
                "state_summary": {
                    "message_count": len(final_state.get("messages", [])),
                    "agent_history": final_state.get("agent_history", []),
                    "current_agent": final_state.get("current_agent"),
                },
                "requires_human": final_state.get("requires_human", False),
                "is_complete": final_state.get("is_complete", False),
                "performance_metrics": {"total_processing_time_ms": final_state.get("total_processing_time_ms", 0)},
            }

            logger.info(f"Message processed successfully for {conversation_id}")
            return response

        except Exception as e:
            logger.error(f"Error processing message for {conversation_id}: {e}")

            return {
                "success": False,
                "response": "Lo siento, tuve un problema procesando tu mensaje. ¿Podrías intentar de nuevo?",
                "conversation_id": conversation_id,
                "error": str(e),
            }

    async def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de una conversación

        Args:
            conversation_id: ID de la conversación
            limit: Número máximo de mensajes

        Returns:
            Lista de mensajes del historial
        """
        try:
            config = {"configurable": {"thread_id": conversation_id}}

            # Obtener checkpoints
            checkpoints = await self.postgres.get_conversation_checkpoints(conversation_id, limit)

            messages = []
            for checkpoint in checkpoints:
                if checkpoint.get("values", {}).get("messages"):
                    for msg in checkpoint["values"]["messages"]:
                        messages.append(
                            {"type": msg.type, "content": msg.content, "timestamp": checkpoint.get("created_at")}
                        )

            return messages[-limit:] if messages else []

        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica el estado de salud del sistema completo

        Returns:
            Estado de salud de todos los componentes
        """
        health_status = {"overall_status": "healthy", "components": {}, "timestamp": "now"}

        try:
            # Verificar Ollama
            ollama_status = await self.ollama.comprehensive_test()
            health_status["components"]["ollama"] = {
                "status": "healthy" if all(ollama_status.values()) else "unhealthy",
                "details": ollama_status,
            }

            # Verificar ChromaDB
            chroma_status = await self.chroma.health_check()
            health_status["components"]["chromadb"] = {"status": "healthy" if chroma_status else "unhealthy"}

            # Verificar PostgreSQL
            postgres_status = await self.postgres.health_check()
            health_status["components"]["postgresql"] = {"status": "healthy" if postgres_status else "unhealthy"}

            # Estado general
            component_statuses = [comp["status"] for comp in health_status["components"].values()]

            if "unhealthy" in component_statuses:
                health_status["overall_status"] = "degraded"

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            health_status["overall_status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    async def initialize_all_systems(self):
        """Inicializa todas las conexiones y dependencias"""
        try:
            # Inicializar checkpointer PostgreSQL primero
            if self.use_postgres_checkpointer and not self.checkpointer_manager:
                self.checkpointer_manager = get_checkpointer_manager()
                await initialize_checkpointer()
                logger.info("PostgreSQL checkpointer initialized")

            # Inicializar PostgreSQL
            await self.postgres.initialize()
            logger.info("PostgreSQL initialized")

            # Verificar y descargar modelos de Ollama si es necesario
            await self.ollama.ensure_models_available()
            logger.info("Ollama models verified")

            # Inicializar colecciones de ChromaDB si es necesario
            collections_config = {
                "products": {"metadata": {"description": "Product catalog"}},
                "categories": {"metadata": {"description": "Product categories"}},
                "support_kb": {"metadata": {"description": "Support knowledge base"}},
            }
            await self.chroma.initialize_collections(collections_config)
            logger.info("ChromaDB collections initialized")

            logger.info("EcommerceAssistantGraph fully initialized")

        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            raise

    async def cleanup(self):
        """Limpia recursos y conexiones"""
        try:
            # Limpiar checkpointer PostgreSQL
            if self.checkpointer_manager:
                await self.checkpointer_manager.close()
                logger.info("PostgreSQL checkpointer closed")

            # Limpiar PostgreSQL
            await self.postgres.close()

            # Limpiar caches
            self.ollama.clear_cache()
            self.chroma.clear_cache()

            logger.info("Cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def __aenter__(self):
        """Context manager entry"""
        await self.initialize()
        await self.initialize_all_systems()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.cleanup()

