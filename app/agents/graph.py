"""
Graph principal del sistema multi-agente LangGraph (Simplified)
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph

from app.config.langsmith_config import ConversationTracer, get_tracer

from .execution.node_executor import NodeExecutor
from .factories.agent_factory import AgentFactory
from .integrations.chroma_integration import ChromaDBIntegration
from .integrations.ollama_integration import OllamaIntegration
from .integrations.postgres_integration import PostgreSQLIntegration
from .routing.graph_router import GraphRouter
from .schemas import AgentType, get_non_supervisor_agents
from .state_schema import LangGraphState
from .utils.tracing import trace_async_method, trace_context

logger = logging.getLogger(__name__)


class EcommerceAssistantGraph:
    """Graph principal del asistente e-commerce multi-agente (simplified)"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracer = get_tracer()
        self.conversation_tracers: Dict[str, ConversationTracer] = {}
        
        # Initialize components
        self._init_components()
        
        # Build and compile graph
        self.graph = self._build_graph()
        self.app = None
        self.checkpointer_manager = None
        self.persistent_checkpointer = None
        self.use_postgres_checkpointer = True
        
        logger.info("EcommerceAssistantGraph initialized successfully")

    def _init_components(self):
        """Initialize all graph components"""
        # Initialize integrations
        integrations_config = self._get_integrations_config()
        self.ollama = OllamaIntegration(integrations_config.get("ollama", {}))
        self.chroma = ChromaDBIntegration(integrations_config.get("chromadb", {}))
        self.postgres = PostgreSQLIntegration(integrations_config.get("postgres", {}))
        
        # Initialize factory and create agents
        self.agent_factory = AgentFactory(
            ollama=self.ollama,
            chroma=self.chroma,
            postgres=self.postgres,
            config=self.config
        )
        self.agents = self.agent_factory.initialize_all_agents()
        
        # Initialize router and executor
        self.router = GraphRouter()
        self.executor = NodeExecutor(self.agents, self.conversation_tracers)

    def _get_integrations_config(self) -> Dict[str, Any]:
        """Get integrations configuration"""
        integrations_config = self.config.get("integrations", {})
        if hasattr(integrations_config, "model_dump"):
            return integrations_config.model_dump()
        return integrations_config

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph"""
        workflow = StateGraph(LangGraphState)
        
        # Add nodes
        self._add_nodes(workflow)
        
        # Configure entry point
        workflow.set_entry_point(AgentType.ORCHESTRATOR.value)
        
        # Add edges
        self._add_edges(workflow)
        
        return workflow

    def _add_nodes(self, workflow: StateGraph):
        """Add all nodes to the workflow"""
        # Add orchestrator and supervisor nodes
        workflow.add_node(AgentType.ORCHESTRATOR.value, self.executor.execute_orchestrator)
        workflow.add_node(AgentType.SUPERVISOR.value, self.executor.execute_supervisor)
        
        # Add specialized agent nodes
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value
            workflow.add_node(
                agent_name,
                lambda state, name=agent_name: self.executor.execute_agent(state, name)
            )

    def _add_edges(self, workflow: StateGraph):
        """Configure all edges and conditional routing"""
        # Orchestrator routing
        orchestrator_edges = {
            agent.value: agent.value for agent in get_non_supervisor_agents()
        }
        orchestrator_edges["__end__"] = END
        
        workflow.add_conditional_edges(
            AgentType.ORCHESTRATOR.value,
            self.router.route_to_agent,
            orchestrator_edges
        )
        
        # All specialized agents route to supervisor
        for agent_type in get_non_supervisor_agents():
            workflow.add_edge(agent_type.value, AgentType.SUPERVISOR.value)
        
        # Supervisor routing
        supervisor_edges = {
            "continue": AgentType.ORCHESTRATOR.value,
            "__end__": END,
        }
        
        workflow.add_conditional_edges(
            AgentType.SUPERVISOR.value,
            self.router.supervisor_should_continue,
            supervisor_edges
        )

    def initialize(self, db_url: Optional[str] = None):
        """Initialize and compile the graph with optional checkpointer"""
        try:
            checkpointer = None
            if db_url and self.use_postgres_checkpointer:
                try:
                    checkpointer = PostgresSaver.from_conn_string(db_url)
                    logger.info("PostgreSQL checkpointer configured")
                except Exception as e:
                    logger.warning(f"Could not setup PostgreSQL checkpointer: {e}")
            
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
        Process a message through the graph.
        
        Args:
            message: User message
            conversation_id: Conversation ID for checkpointing
            **kwargs: Additional parameters
            
        Returns:
            Graph response
        """
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")
        
        try:
            # Initialize conversation tracker
            conv_id = conversation_id or "default"
            user_id = kwargs.get("user_id")
            
            if self.tracer.config.tracing_enabled and conv_id not in self.conversation_tracers:
                self.conversation_tracers[conv_id] = ConversationTracer(conv_id, user_id)
                logger.info(f"Started conversation tracking for {conv_id}")
            
            conv_tracker = self.conversation_tracers.get(conv_id)
            
            if conv_tracker:
                conv_tracker.add_message("user", message, {"timestamp": datetime.now().isoformat()})
            
            # Prepare initial state
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conv_id,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                **kwargs,
            }
            
            # Configure thread for checkpointing
            config = {}
            if conv_id:
                config["configurable"] = {"thread_id": conv_id}
            
            # Execute graph with tracing
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
                result = await self.app.ainvoke(initial_state, config)
                
                # Track response
                if conv_tracker and result.get("messages"):
                    for msg in result["messages"]:
                        if hasattr(msg, "content"):
                            conv_tracker.add_message(
                                "assistant",
                                msg.content,
                                {
                                    "agent": result.get("current_agent"),
                                    "timestamp": datetime.now().isoformat()
                                },
                            )
                
                return result
                
        except Exception as e:
            logger.error(f"Error invoking graph: {e}")
            raise