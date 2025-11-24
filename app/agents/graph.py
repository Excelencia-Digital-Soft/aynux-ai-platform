"""
Graph principal del sistema multi-agente LangGraph (Simplified)
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage
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


class AynuxGraph:
    """Graph principal del asistente multi-dominio (simplified)"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracer = get_tracer()
        self.conversation_tracers: Dict[str, ConversationTracer] = {}

        # Store enabled agents configuration
        self.enabled_agents = config.get("enabled_agents", [])
        logger.info(f"Graph initialized with enabled agents: {self.enabled_agents}")

        # Initialize components
        self._init_components()

        # Build and compile graph
        self.graph = self._build_graph()
        self.app = None
        self.checkpointer_manager = None
        self.persistent_checkpointer = None
        self.use_postgres_checkpointer = True

        logger.info("AynuxGraph initialized successfully")

    def _init_components(self):
        """Initialize all graph components"""
        # Initialize integrations
        integrations_config = self._get_integrations_config()
        self.ollama = OllamaIntegration(integrations_config.get("ollama", {}))
        self.chroma = ChromaDBIntegration(integrations_config.get("chromadb", {}))
        self.postgres = PostgreSQLIntegration(integrations_config.get("postgres", {}))

        # Initialize factory and create agents
        self.agent_factory = AgentFactory(
            ollama=self.ollama, chroma=self.chroma, postgres=self.postgres, config=self.config
        )
        self.agents = self.agent_factory.initialize_all_agents()

        # Initialize router with enabled agents configuration
        self.router = GraphRouter(enabled_agents=self.enabled_agents)
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
        """Add only enabled agent nodes to the workflow"""
        # Add orchestrator and supervisor nodes (always enabled)
        workflow.add_node(AgentType.ORCHESTRATOR.value, self.executor.execute_orchestrator)
        workflow.add_node(AgentType.SUPERVISOR.value, self.executor.execute_supervisor)

        # Add specialized agent nodes (only if enabled)
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value

            # Only add node if agent is enabled
            if agent_name in self.enabled_agents and agent_name in self.agents:
                # Create async wrapper function for each agent
                async def agent_executor(state, name=agent_name):
                    return await self.executor.execute_agent(state, name)

                workflow.add_node(agent_name, agent_executor)
                logger.debug(f"Added graph node for enabled agent: {agent_name}")
            else:
                logger.debug(f"Skipped graph node for disabled agent: {agent_name}")

    def _add_edges(self, workflow: StateGraph):
        """Configure edges only for enabled agents"""
        # Orchestrator routing - only include enabled agents
        orchestrator_edges = {}
        for agent in get_non_supervisor_agents():
            if agent.value in self.enabled_agents and agent.value in self.agents:
                orchestrator_edges[agent.value] = agent.value
        orchestrator_edges["__end__"] = END

        workflow.add_conditional_edges(AgentType.ORCHESTRATOR.value, self.router.route_to_agent, orchestrator_edges)

        # Add edges only for enabled agents
        for agent_type in get_non_supervisor_agents():
            agent_name = agent_type.value

            # Only add edges for enabled agents
            if agent_name in self.enabled_agents and agent_name in self.agents:
                if agent_name == AgentType.GREETING_AGENT.value:
                    # Greeting agent goes directly to END (no supervisor needed)
                    workflow.add_edge(agent_name, END)
                else:
                    # Other agents route to supervisor
                    workflow.add_edge(agent_name, AgentType.SUPERVISOR.value)

        # Supervisor routing
        supervisor_edges = {
            "continue": AgentType.ORCHESTRATOR.value,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            AgentType.SUPERVISOR.value, self.router.supervisor_should_continue, supervisor_edges
        )

    def initialize(self, db_url: Optional[str] = None):
        """Initialize and compile the graph with optional checkpointer"""
        try:
            checkpointer = None
            if db_url and self.use_postgres_checkpointer:
                try:
                    # PostgresSaver.from_conn_string returns a synchronous checkpointer
                    # For async operations, we create it differently or disable it
                    logger.info("Skipping PostgreSQL checkpointer for now - using memory checkpointer")
                    # checkpointer = PostgresSaver.from_conn_string(db_url)
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
                                {"agent": result.get("current_agent"), "timestamp": datetime.now().isoformat()},
                            )

                return result

        except Exception as e:
            logger.error(f"Error invoking graph: {e}")
            raise

    async def astream(self, message: str, conversation_id: Optional[str] = None, **kwargs):
        """
        Process a message through the graph with streaming support.

        Args:
            message: User message
            conversation_id: Conversation ID for checkpointing
            **kwargs: Additional parameters

        Yields:
            Dict containing streaming events and final result
        """
        app = self.app
        if not app:
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

            # Execute graph with streaming (removed tracing context to prevent async generator issues)
            final_result = None
            step_count = 0

            try:
                # Stream through the graph execution
                async for chunk in app.astream(initial_state, config):
                    step_count += 1

                    # Emit progress events based on graph steps
                    if chunk:
                        # Extract current node/agent from chunk
                        current_node = None

                        # LangGraph astream yields dict with node names as keys
                        for node_name, node_state in chunk.items():
                            current_node = node_name

                            # Yield streaming event
                            yield {
                                "type": "stream_event",
                                "data": {
                                    "current_node": current_node,
                                    "step_count": step_count,
                                    "state_preview": self._create_state_preview(node_state),
                                    "timestamp": datetime.now().isoformat(),
                                },
                            }

                            # Keep track of final result
                            final_result = node_state

                # Track final response
                if conv_tracker and final_result and final_result.get("messages"):
                    for msg in final_result["messages"]:
                        if hasattr(msg, "content"):
                            conv_tracker.add_message(
                                "assistant",
                                msg.content,
                                {"agent": final_result.get("current_agent"), "timestamp": datetime.now().isoformat()},
                            )

                # Yield final result
                yield {"type": "final_result", "data": final_result or {}}
                
            except GeneratorExit:
                # Handle generator cleanup gracefully
                logger.debug(f"Stream generator for conversation {conv_id} was closed")
                return
            except Exception as e:
                # Handle other exceptions and yield error
                logger.error(f"Error streaming graph: {e}")
                yield {"type": "error", "data": {"error": str(e), "timestamp": datetime.now().isoformat()}}
                raise

        except Exception as e:
            logger.error(f"Error in conversation stream setup: {e}")
            yield {"type": "error", "data": {"error": str(e), "timestamp": datetime.now().isoformat()}}
            raise

    def _create_state_preview(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create a safe preview of the current state for streaming events"""
        try:
            return {
                "current_agent": state.get("current_agent"),
                "message_count": len(state.get("messages", [])),
                "conversation_id": state.get("conversation_id"),
                "has_error": "error" in state,
                "is_complete": state.get("is_complete", False),
            }
        except Exception as e:
            logger.warning(f"Error creating state preview: {e}")
            return {"error": "Could not create state preview"}

    def is_agent_enabled(self, agent_name: str) -> bool:
        """
        Check if an agent is enabled in the graph.

        Args:
            agent_name: Name of the agent to check

        Returns:
            True if agent is enabled, False otherwise
        """
        return agent_name in self.enabled_agents and agent_name in self.agents

    def get_enabled_agents(self) -> list[str]:
        """
        Get list of enabled agent names.

        Returns:
            List of enabled agent names (excluding orchestrator and supervisor)
        """
        return self.agent_factory.get_enabled_agent_names()

    def get_disabled_agents(self) -> list[str]:
        """
        Get list of disabled agent names.

        Returns:
            List of disabled agent names
        """
        return self.agent_factory.get_disabled_agent_names()

    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get complete agent status information.

        Returns:
            Dictionary with enabled/disabled agents and statistics
        """
        enabled = self.get_enabled_agents()
        disabled = self.get_disabled_agents()

        return {
            "enabled_agents": enabled,
            "disabled_agents": disabled,
            "enabled_count": len(enabled),
            "disabled_count": len(disabled),
            "total_possible_agents": len(enabled) + len(disabled),
        }
