"""
Graph principal del sistema multi-agente LangGraph
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from app.agents.langgraph_system.integrations.postgres_checkpointer import (
    get_checkpointer_manager,
    initialize_checkpointer,
)

from .agents import (
    CategoryAgent,
    InvoiceAgent,
    ProductAgent,
    PromotionsAgent,
    SupportAgent,
    TrackingAgent,
)
from .agents.base_agent import BaseAgent
from .integrations import (
    ChromaDBIntegration,
    OllamaIntegration,
    PostgreSQLIntegration,
)
from .intelligence.intent_router import IntentRouter
from .models import ConversationContext, CustomerContext, IntentInfo
from .router import SupervisorAgent
from .state_manager import StateManager
from .state_schema import LangGraphState

logger = logging.getLogger(__name__)


class EcommerceAssistantGraph:
    """Graph principal del asistente e-commerce multi-agente"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.state_manager = StateManager()

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

    def _build_graph(self) -> StateGraph:
        """Construye el StateGraph de LangGraph"""
        # Crear StateGraph con el schema TypedDict
        workflow = StateGraph(state_schema=LangGraphState)

        # Añadir nodos
        workflow.add_node("supervisor", self._supervisor_node)
        workflow.add_node("category_agent", self._category_agent_node)
        workflow.add_node("product_agent", self._product_agent_node)
        workflow.add_node("promotions_agent", self._promotions_agent_node)
        workflow.add_node("tracking_agent", self._tracking_agent_node)
        workflow.add_node("support_agent", self._support_agent_node)
        workflow.add_node("invoice_agent", self._invoice_agent_node)

        # Definir punto de entrada
        workflow.set_entry_point("supervisor")

        # Añadir aristas condicionales desde supervisor
        workflow.add_conditional_edges(
            "supervisor",
            self._route_to_agent,
            {
                "category_agent": "category_agent",
                "product_agent": "product_agent",
                "promotions_agent": "promotions_agent",
                "tracking_agent": "tracking_agent",
                "support_agent": "support_agent",
                "invoice_agent": "invoice_agent",
                "__end__": END,
            },
        )

        # Todos los agentes vuelven al supervisor para posible re-routing
        for agent in [
            "category_agent",
            "product_agent",
            "promotions_agent",
            "tracking_agent",
            "support_agent",
            "invoice_agent",
        ]:
            workflow.add_conditional_edges(
                agent,
                self._should_continue,
                {
                    "continue": "supervisor",
                    "__end__": END,
                },
            )

        return workflow

    async def process_message(
        self,
        message: str,
        customer_data: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        session_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje usando la arquitectura refactorizada.

        Args:
            message: Mensaje del usuario
            customer_data: Datos del cliente (opcional)
            conversation_id: ID de conversación para checkpointing
            session_config: Configuración adicional de sesión

        Returns:
            Diccionario con la respuesta procesada
        """
        if not self.app:
            raise RuntimeError("Graph not compiled. Call initialize() first.")

        try:
            # Crear contextos usando modelos Pydantic para validación
            customer = None
            if customer_data:
                customer = CustomerContext(**customer_data)

            conversation = None
            if conversation_id:
                conversation = ConversationContext(
                    conversation_id=conversation_id, session_id=f"session_{conversation_id}"
                )

            # Crear estado inicial usando StateManager
            initial_state = self.state_manager.create_initial_state(
                message=message, customer=customer, conversation=conversation, conversation_id=conversation_id
            )

            # Validar estado antes de procesar
            if not self.state_manager.validate_state(initial_state):
                raise ValueError("Invalid initial state created")

            logger.info(f"Processing message for conversation {conversation_id}")

            # Procesar con el graph
            final_state = await self.app.ainvoke(initial_state)

            # Configurar checkpointing si está disponible
            config = {}
            if self.checkpointer_manager and conversation_id:
                config = {"configurable": {"thread_id": conversation_id, **(session_config or {})}}

                try:
                    # Intentar obtener estado previo
                    current_state = await self.app.aget_state(config)

                    if current_state.values:
                        # Actualizar estado existente con nuevo mensaje
                        state_dict = current_state.values
                        # state_dict.update(self.state_manager.add_human_message(state_dict, message))

                        # Resetear completado si era final
                        if state_dict.get("is_complete"):
                            state_dict["is_complete"] = False

                        initial_state = state_dict

                except Exception as e:
                    logger.warning(f"Could not retrieve previous state: {e}")
                    # Continuar con estado inicial

            # Procesar con el graph
            logger.debug(f"State keys before processing: {list(initial_state.keys())}")
            final_state = await self.app.ainvoke(initial_state, config)

            # Extraer respuesta usando StateManager
            response_text = self.state_manager.get_last_ai_message(final_state)

            if not response_text:
                response_text = "Lo siento, no pude procesar tu mensaje correctamente."

            return {
                "response": response_text,
                "agent_used": final_state.get("current_agent"),
                "requires_human": final_state.get("requires_human", False),
                "is_complete": final_state.get("is_complete", False),
                "conversation_id": conversation_id,
            }

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "response": "Lo siento, ocurrió un error al procesar tu mensaje.",
                "error": str(e),
                "conversation_id": conversation_id,
            }

    async def _supervisor_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del supervisor que coordina el flujo"""
        try:
            logger.debug(f"Processing supervisor node with state type: {type(state)}")
            # Obtener último mensaje del usuario
            user_message = self.state_manager.get_last_user_message(state)

            if not user_message:
                return self.state_manager.mark_complete(state, requires_human=True)

            # Determinar intención usando el router (llamada asíncrona)
            intent_result = await self.intent_router.analyze_intent_with_llm(
                user_message, {
                    "customer_data": state.get("customer"),
                    "conversation_data": state.get("conversation")
                }
            )

            # Crear objeto IntentInfo y añadirlo al estado
            intent_info = IntentInfo(**intent_result)
            updates = self.state_manager.add_intent_info(state, intent_info)

            logger.info(f"Supervisor routed to: {intent_info.target_agent}")
            return updates

        except Exception as e:
            logger.error(f"Error in supervisor node: {e}")
            error_updates = self.state_manager.increment_error_count(state)
            error_updates.update(
                self.state_manager.add_ai_message(state, "Disculpa, tuve un problema entendiendo tu mensaje.")
            )
            return error_updates

    def _route_to_agent(self, state: LangGraphState) -> str:
        """Determina a qué agente dirigir el flujo"""
        current_intent = state.get("current_intent")

        if not current_intent:
            return "__end__"

        target_agent = current_intent.get("target_agent")

        # Validar que el agente objetivo existe
        valid_agents = [
            "category_agent",
            "product_agent",
            "promotions_agent",
            "tracking_agent",
            "support_agent",
            "invoice_agent",
        ]

        if target_agent in valid_agents:
            return target_agent

        # Si no hay agente válido, terminar
        return "__end__"

    def _should_continue(self, state: LangGraphState) -> str:
        """Determina si la conversación debe continuar"""
        if not self.state_manager.should_continue(state):
            return "__end__"

        # Si está marcado como completo, terminar
        if state.get("is_complete", False):
            return "__end__"

        # Verificar si requiere intervención humana
        if state.get("requires_human", False):
            return "__end__"

        # Por defecto, continuar
        return "continue"

    # Nodos de agentes (ejemplo para product_agent)
    def _product_agent_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del agente de productos"""
        try:
            user_message = self.state_manager.get_last_user_message(state)

            # Procesar con el agente especializado
            result = self.product_agent._process_internal(user_message, dict(state))

            # Extraer contenido de la respuesta
            if "messages" in result and result["messages"]:
                message_content = result["messages"][0]
                if isinstance(message_content, dict):
                    content = message_content.get("content", "Sin respuesta")
                else:
                    content = str(message_content)

                # Marcar como completo usando el resultado del agente
                updates = self.state_manager.add_ai_message(state, content)
                updates["is_complete"] = result.get("is_complete", True)
                updates["current_agent"] = "product_agent"
                return updates

            # Si no hay respuesta, marcar como completo con mensaje de error
            updates = self.state_manager.add_ai_message(state, "No pude procesar tu consulta de productos.")
            updates["is_complete"] = True
            updates["current_agent"] = "product_agent"
            return updates

        except Exception as e:
            logger.error(f"Error in product agent: {e}")
            error_updates = self.state_manager.increment_error_count(state)
            error_updates.update(
                self.state_manager.add_ai_message(
                    state, "Disculpa, tuve un problema consultando información de productos."
                )
            )
            error_updates["is_complete"] = True
            return error_updates

    def _category_agent_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del agente de categorías"""
        try:
            user_message = self.state_manager.get_last_user_message(state)
            if not user_message:
                updates = self.state_manager.add_ai_message(state, "No pude obtener tu mensaje.")
                updates["is_complete"] = True
                return updates

            result = self.category_agent._process_internal(user_message, dict(state))

            if "messages" in result and result["messages"]:
                message_content = result["messages"][0]
                if isinstance(message_content, dict):
                    content = message_content.get("content", "Sin respuesta")
                else:
                    content = str(message_content)

                updates = self.state_manager.add_ai_message(state, content)
                updates["is_complete"] = result.get("is_complete", True)
                updates["current_agent"] = "category_agent"
                return updates

            updates = self.state_manager.add_ai_message(state, "No pude procesar tu consulta de categorías.")
            updates["is_complete"] = True
            updates["current_agent"] = "category_agent"
            return updates

        except Exception as e:
            logger.error(f"Error in category agent node: {str(e)}")
            updates = self.state_manager.add_ai_message(state, "Disculpa, tuve un problema con las categorías.")
            updates["is_complete"] = True
            return updates

    def _promotions_agent_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del agente de promociones"""
        try:
            user_message = self.state_manager.get_last_user_message(state)
            if not user_message:
                updates = self.state_manager.add_ai_message(state, "No pude obtener tu mensaje.")
                updates["is_complete"] = True
                return updates

            result = self.promotions_agent._process_internal(user_message, dict(state))

            if "messages" in result and result["messages"]:
                message_content = result["messages"][0]
                if isinstance(message_content, dict):
                    content = message_content.get("content", "Sin respuesta")
                else:
                    content = str(message_content)

                updates = self.state_manager.add_ai_message(state, content)
                updates["is_complete"] = result.get("is_complete", True)
                updates["current_agent"] = "promotions_agent"
                return updates

            updates = self.state_manager.add_ai_message(state, "No pude procesar tu consulta de promociones.")
            updates["is_complete"] = True
            updates["current_agent"] = "promotions_agent"
            return updates

        except Exception as e:
            logger.error(f"Error in promotions agent node: {str(e)}")
            updates = self.state_manager.add_ai_message(state, "Disculpa, tuve un problema con las promociones.")
            updates["is_complete"] = True
            return updates

    def _tracking_agent_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del agente de seguimiento"""
        try:
            user_message = self.state_manager.get_last_user_message(state)
            if not user_message:
                updates = self.state_manager.add_ai_message(state, "No pude obtener tu mensaje.")
                updates["is_complete"] = True
                return updates

            result = self.tracking_agent._process_internal(user_message, dict(state))

            if "messages" in result and result["messages"]:
                message_content = result["messages"][0]
                if isinstance(message_content, dict):
                    content = message_content.get("content", "Sin respuesta")
                else:
                    content = str(message_content)

                updates = self.state_manager.add_ai_message(state, content)
                updates["is_complete"] = result.get("is_complete", True)
                updates["current_agent"] = "tracking_agent"
                return updates

            updates = self.state_manager.add_ai_message(state, "No pude procesar tu consulta de seguimiento.")
            updates["is_complete"] = True
            updates["current_agent"] = "tracking_agent"
            return updates

        except Exception as e:
            logger.error(f"Error in tracking agent node: {str(e)}")
            updates = self.state_manager.add_ai_message(state, "Disculpa, tuve un problema con el seguimiento.")
            updates["is_complete"] = True
            return updates

    def _support_agent_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del agente de soporte"""
        try:
            user_message = self.state_manager.get_last_user_message(state)
            if not user_message:
                updates = self.state_manager.add_ai_message(state, "No pude obtener tu mensaje.")
                updates["is_complete"] = True
                return updates

            result = self.support_agent._process_internal(user_message, dict(state))

            if "messages" in result and result["messages"]:
                message_content = result["messages"][0]
                if isinstance(message_content, dict):
                    content = message_content.get("content", "Sin respuesta")
                else:
                    content = str(message_content)

                updates = self.state_manager.add_ai_message(state, content)
                updates["is_complete"] = result.get("is_complete", True)
                updates["current_agent"] = "support_agent"
                return updates

            updates = self.state_manager.add_ai_message(state, "¿En qué puedo ayudarte?")
            updates["is_complete"] = True
            updates["current_agent"] = "support_agent"
            return updates

        except Exception as e:
            logger.error(f"Error in support agent node: {str(e)}")
            updates = self.state_manager.add_ai_message(state, "Estoy aquí para ayudarte. ¿Cuál es tu consulta?")
            updates["is_complete"] = True
            return updates

    def _invoice_agent_node(self, state: LangGraphState) -> Dict[str, Any]:
        """Nodo del agente de facturación"""
        try:
            user_message = self.state_manager.get_last_user_message(state)
            if not user_message:
                updates = self.state_manager.add_ai_message(state, "No pude obtener tu mensaje.")
                updates["is_complete"] = True
                return updates

            result = self.invoice_agent._process_internal(user_message, dict(state))

            if "messages" in result and result["messages"]:
                message_content = result["messages"][0]
                if isinstance(message_content, dict):
                    content = message_content.get("content", "Sin respuesta")
                else:
                    content = str(message_content)

                updates = self.state_manager.add_ai_message(state, content)
                updates["is_complete"] = result.get("is_complete", True)
                updates["current_agent"] = "invoice_agent"
                return updates

            updates = self.state_manager.add_ai_message(state, "No pude procesar tu consulta de facturación.")
            updates["is_complete"] = True
            updates["current_agent"] = "invoice_agent"
            return updates

        except Exception as e:
            logger.error(f"Error in invoice agent node: {str(e)}")
            updates = self.state_manager.add_ai_message(state, "Disculpa, tuve un problema con la facturación.")
            updates["is_complete"] = True
            return updates

    # Métodos de inicialización (mantenidos del código original)
    def _init_integrations(self):
        """Inicializa las integraciones externas"""
        self.ollama = OllamaIntegration(self.config.get("ollama", {}))
        self.chroma = ChromaDBIntegration(self.config.get("chromadb", {}))
        self.postgres = PostgreSQLIntegration(self.config.get("postgres", {}))

    def _init_core_components(self):
        """Inicializa componentes principales"""
        self.intent_router = IntentRouter(ollama=self.ollama, config=self.config.get("router", {}))
        self.supervisor = SupervisorAgent(router=self.intent_router)

    def _init_agents(self):
        """Inicializa agentes especializados"""
        try:
            agent_config = self.config.get("agents", {})

            # Inicializar agentes de forma segura
            self.product_agent = ProductAgent(
                ollama=self.ollama, postgres=self.postgres, config=agent_config.get("product", {})
            )

            # Inicializar agentes reales
            self.category_agent = CategoryAgent(
                ollama=self.ollama, chroma=self.chroma, config=agent_config.get("category", {})
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

            logger.info("Agents initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise

    def _create_placeholder_agent(self, agent_name: str) -> BaseAgent:
        """Crea un agente placeholder para evitar errores"""

        class PlaceholderAgent(BaseAgent):
            def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
                response_text = f"Agente {self.name} está en mantenimiento. Por favor, contacta soporte."
                return {
                    "messages": [{"role": "assistant", "content": response_text}],
                    "current_agent": self.name,
                    "is_complete": True,
                }

        return PlaceholderAgent(agent_name, {})

    async def initialize(self):
        """Inicializa el sistema de forma asíncrona"""
        try:
            # Inicializar checkpointer PostgreSQL si está habilitado
            if self.use_postgres_checkpointer:
                try:
                    self.checkpointer_manager = get_checkpointer_manager()
                    checkpointer_healthy = await initialize_checkpointer()

                    if checkpointer_healthy:
                        checkpointer = await self.checkpointer_manager.get_async_checkpointer()
                        self.app = self.graph.compile(checkpointer=checkpointer)
                        logger.info("Graph compiled with PostgreSQL checkpointer")
                    else:
                        self.app = self.graph.compile()
                        logger.warning("PostgreSQL checkpointer unhealthy, using in-memory")

                except Exception as e:
                    logger.error(f"Error setting up PostgreSQL checkpointer: {e}")
                    self.app = self.graph.compile()
            else:
                # Compilar sin checkpointer
                self.app = self.graph.compile()
                logger.info("Graph compiled without persistent checkpointer")

            logger.info("EcommerceAssistantGraph initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing graph: {e}")
            raise

    async def health_check(self) -> Dict[str, Any]:
        """
        Verificación de salud del sistema LangGraph
        
        Returns:
            Dict con el estado de salud de todos los componentes
        """
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "errors": []
        }
        
        try:
            # Verificar que el grafo esté compilado
            if not self.app:
                health_status["components"]["graph"] = {"status": "not_compiled", "error": "Graph not compiled"}
                health_status["overall_status"] = "unhealthy"
                health_status["errors"].append("Graph not compiled")
            else:
                health_status["components"]["graph"] = {"status": "healthy", "compiled": True}
            
            # Verificar agentes
            agents_status = {}
            agent_names = ["category_agent", "product_agent", "promotions_agent", 
                          "tracking_agent", "support_agent", "invoice_agent"]
            for agent_name in agent_names:
                try:
                    agent = getattr(self, agent_name, None)
                    if agent:
                        agents_status[agent_name] = {"status": "healthy", "initialized": True}
                    else:
                        agents_status[agent_name] = {"status": "not_initialized", "initialized": False}
                        health_status["errors"].append(f"Agent {agent_name} not initialized")
                        if health_status["overall_status"] == "healthy":
                            health_status["overall_status"] = "degraded"
                except Exception as e:
                    agents_status[agent_name] = {"status": "error", "error": str(e)}
                    health_status["errors"].append(f"Agent {agent_name} error: {str(e)}")
                    health_status["overall_status"] = "unhealthy"
            
            health_status["components"]["agents"] = agents_status
            
            # Verificar componentes principales
            try:
                if hasattr(self, 'intent_router') and self.intent_router:
                    health_status["components"]["intent_router"] = {"status": "healthy"}
                else:
                    health_status["components"]["intent_router"] = {"status": "not_initialized"}
                    health_status["errors"].append("Intent router not initialized")
                    if health_status["overall_status"] == "healthy":
                        health_status["overall_status"] = "degraded"
                
                if hasattr(self, 'state_manager') and self.state_manager:
                    health_status["components"]["state_manager"] = {"status": "healthy"}
                else:
                    health_status["components"]["state_manager"] = {"status": "not_initialized"}
                    health_status["errors"].append("State manager not initialized")
                    if health_status["overall_status"] == "healthy":
                        health_status["overall_status"] = "degraded"
                        
            except Exception as e:
                health_status["components"]["core_components"] = {"status": "error", "error": str(e)}
                health_status["errors"].append(f"Core components error: {str(e)}")
                health_status["overall_status"] = "unhealthy"
            
            # Verificar integraciones
            integrations_status = {}
            
            # Ollama
            try:
                if hasattr(self, 'ollama') and self.ollama:
                    url = getattr(self.ollama, 'url', 'unknown')
                    integrations_status["ollama"] = {"status": "healthy", "url": url}
                else:
                    integrations_status["ollama"] = {"status": "not_initialized"}
            except Exception as e:
                integrations_status["ollama"] = {"status": "error", "error": str(e)}
            
            # ChromaDB
            try:
                if hasattr(self, 'chroma') and self.chroma:
                    integrations_status["chromadb"] = {"status": "healthy"}
                else:
                    integrations_status["chromadb"] = {"status": "not_initialized"}
            except Exception as e:
                integrations_status["chromadb"] = {"status": "error", "error": str(e)}
            
            # PostgreSQL
            try:
                if hasattr(self, 'postgres') and self.postgres:
                    integrations_status["postgresql"] = {"status": "healthy"}
                else:
                    integrations_status["postgresql"] = {"status": "not_initialized"}
            except Exception as e:
                integrations_status["postgresql"] = {"status": "error", "error": str(e)}
            
            health_status["components"]["integrations"] = integrations_status
            
            # Verificar checkpointer
            try:
                if hasattr(self, 'checkpointer_manager') and self.checkpointer_manager:
                    health_status["components"]["checkpointer"] = {"status": "healthy", "type": "postgresql"}
                else:
                    health_status["components"]["checkpointer"] = {"status": "in_memory", "type": "memory"}
            except Exception as e:
                health_status["components"]["checkpointer"] = {"status": "error", "error": str(e)}
            
            # Agregar métricas básicas
            health_status["metrics"] = {
                "agents_count": len([a for a in agents_status.values() if a.get("status") == "healthy"]),
                "total_agents": len(agents_status),
                "graph_compiled": bool(self.app),
                "use_postgres_checkpointer": getattr(self, 'use_postgres_checkpointer', False)
            }
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            health_status["overall_status"] = "unhealthy"
            health_status["errors"].append(f"Health check error: {str(e)}")
            health_status["components"]["health_check"] = {"status": "error", "error": str(e)}
        
        return health_status
