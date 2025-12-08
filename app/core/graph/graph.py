"""
Graph principal del sistema multi-agente LangGraph (Simplified)

Supports DUAL-MODE operation:
- Global mode (no tenant): Agents use Python defaults
- Multi-tenant mode (with token): Agents configured from database per-request

The set_tenant_registry() method propagates tenant configuration to all agents.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Hashable, Optional, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.config.langsmith_config import ConversationTracer, get_tracer

from app.core.graph.execution.node_executor import NodeExecutor
from app.core.graph.factories.agent_factory import AgentFactory
from app.integrations.llm import OllamaLLM
from app.integrations.databases import PostgreSQLIntegration
from app.core.graph.routing.graph_router import GraphRouter
from app.core.schemas import AgentType, get_non_supervisor_agents
from app.core.graph.state_schema import LangGraphState
from app.core.utils.tracing import trace_async_method, trace_context
from app.domains.shared.agents.history_agent import HistoryAgent
from app.models.conversation_context import ConversationContextModel

if TYPE_CHECKING:
    from app.core.schemas.tenant_agent_config import TenantAgentRegistry

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
        self.ollama = OllamaLLM()
        self.postgres = PostgreSQLIntegration(integrations_config.get("postgres", {}))

        # Initialize factory and create agents
        self.agent_factory = AgentFactory(
            ollama=self.ollama, postgres=self.postgres, config=self.config
        )
        self.agents = self.agent_factory.initialize_all_agents()

        # Initialize history agent for conversation context management
        history_config = self.config.get("history", {})
        self.history_agent = HistoryAgent(
            ollama=self.ollama,
            postgres=self.postgres,
            config={
                "summary_interval": history_config.get("summary_interval", 5),
                "max_summary_tokens": history_config.get("max_summary_tokens", 300),
            },
        )

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

        workflow.add_conditional_edges(
            AgentType.ORCHESTRATOR.value,
            self.router.route_to_agent,
            cast(dict[Hashable, str], orchestrator_edges),
        )

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
        supervisor_edges: dict[str, str] = {
            "continue": AgentType.ORCHESTRATOR.value,
            "__end__": END,
        }

        workflow.add_conditional_edges(
            AgentType.SUPERVISOR.value,
            self.router.supervisor_should_continue,
            cast(dict[Hashable, str], supervisor_edges),
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
        Process a message through the graph with conversation history middleware.

        MIDDLEWARE PATTERN:
        1. LOAD: Load conversation context before execution
        2. INJECT: Add context to initial state
        3. EXECUTE: Run graph as normal
        4. UPDATE: Update context with new exchange

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

            # ================================================================
            # MIDDLEWARE: Load conversation context
            # ================================================================
            context: ConversationContextModel | None = None
            try:
                context = await self.history_agent.load_context(
                    conversation_id=conv_id,
                    organization_id=kwargs.get("organization_id"),
                    user_phone=kwargs.get("user_phone"),
                )
                logger.debug(f"Loaded context for {conv_id}: turns={context.total_turns if context else 0}")
            except Exception as e:
                logger.warning(f"Error loading conversation context: {e}")
                context = None

            # Prepare initial state with conversation context
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conv_id,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                # MIDDLEWARE: Inject conversation context
                "conversation_context": context.model_dump() if context else {},
                "conversation_summary": context.to_prompt_context() if context else "",
                "history_loaded": context is not None,
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
                    "history_turns": context.total_turns if context else 0,
                },
                tags=["langgraph", "conversation", "multi_agent"],
            ):
                result = await self.app.ainvoke(initial_state, cast(RunnableConfig, config))

                # Track response
                if conv_tracker and result.get("messages"):
                    for msg in result["messages"]:
                        if hasattr(msg, "content"):
                            conv_tracker.add_message(
                                "assistant",
                                msg.content,
                                {"agent": result.get("current_agent"), "timestamp": datetime.now().isoformat()},
                            )

                # ================================================================
                # MIDDLEWARE: Update conversation context
                # ================================================================
                bot_response = self._extract_bot_response(result)
                if bot_response:
                    try:
                        await self.history_agent.update_context(
                            conversation_id=conv_id,
                            user_message=message,
                            bot_response=bot_response,
                            current_context=context,
                            agent_name=result.get("current_agent"),
                        )
                    except Exception as e:
                        logger.warning(f"Error updating conversation context: {e}")

                return result

        except Exception as e:
            logger.error(f"Error invoking graph: {e}")
            raise

    async def astream(self, message: str, conversation_id: Optional[str] = None, **kwargs):
        """
        Process a message through the graph with streaming support and history middleware.

        MIDDLEWARE PATTERN (same as invoke):
        1. LOAD: Load conversation context before execution
        2. INJECT: Add context to initial state
        3. EXECUTE: Stream graph execution
        4. UPDATE: Update context with new exchange (after final result)

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

            # ================================================================
            # MIDDLEWARE: Load conversation context
            # ================================================================
            context: ConversationContextModel | None = None
            try:
                context = await self.history_agent.load_context(
                    conversation_id=conv_id,
                    organization_id=kwargs.get("organization_id"),
                    user_phone=kwargs.get("user_phone"),
                )
            except Exception as e:
                logger.warning(f"Error loading conversation context: {e}")
                context = None

            # Prepare initial state with conversation context
            initial_state = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conv_id,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                # MIDDLEWARE: Inject conversation context
                "conversation_context": context.model_dump() if context else {},
                "conversation_summary": context.to_prompt_context() if context else "",
                "history_loaded": context is not None,
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
                async for chunk in app.astream(initial_state, cast(RunnableConfig, config)):
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

                # ================================================================
                # MIDDLEWARE: Update conversation context
                # ================================================================
                if final_result:
                    bot_response = self._extract_bot_response(final_result)
                    if bot_response:
                        try:
                            await self.history_agent.update_context(
                                conversation_id=conv_id,
                                user_message=message,
                                bot_response=bot_response,
                                current_context=context,
                                agent_name=final_result.get("current_agent"),
                            )
                        except Exception as e:
                            logger.warning(f"Error updating conversation context: {e}")

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

    def _extract_bot_response(self, result: Dict[str, Any]) -> str | None:
        """Extract the last bot response from graph result."""
        try:
            messages = result.get("messages", [])
            if not messages:
                return None

            # Find last AI/assistant message
            for msg in reversed(messages):
                if hasattr(msg, "content"):
                    # Check if it's an AI message (not human)
                    msg_type = getattr(msg, "type", None)
                    if msg_type in ("ai", "assistant") or not msg_type:
                        return msg.content

            # Fallback: return last message content
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                return last_msg.content

            return None
        except Exception as e:
            logger.warning(f"Error extracting bot response: {e}")
            return None

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

    # =========================================================================
    # Dual-Mode Methods (Global vs Multi-Tenant)
    # =========================================================================

    def set_tenant_registry(self, registry: "TenantAgentRegistry") -> None:
        """
        Set tenant registry and apply configuration to all agents.

        Called per-request in multi-tenant mode to configure agents
        with tenant-specific settings from database.

        Args:
            registry: TenantAgentRegistry loaded from database

        Example:
            >>> # In webhook before processing
            >>> registry = await service.get_agent_registry(org_id)
            >>> graph.set_tenant_registry(registry)
            >>> result = await graph.invoke(message, ...)
        """
        if registry is None:
            logger.debug("No tenant registry provided, using global defaults")
            return

        # Update factory's registry
        self.agent_factory.set_tenant_registry(registry)

        # Apply tenant config to all agents
        self.agent_factory.apply_tenant_config_to_agents(registry)

        logger.info(f"Graph configured for tenant: {registry.organization_id}")

    def reset_tenant_config(self) -> None:
        """
        Reset all agents to global default configuration.

        Called after request processing to clean up tenant-specific
        configuration and prepare for next request.
        """
        self.agent_factory.reset_agents_to_defaults()
        logger.debug("Graph reset to global defaults")

    def get_mode_info(self) -> Dict[str, Any]:
        """
        Get information about current graph operation mode.

        Returns:
            Dict with mode info (global vs multi-tenant) and configuration state
        """
        factory_info = self.agent_factory.get_mode_info()

        return {
            **factory_info,
            "graph_initialized": self.app is not None,
            "enabled_agents_config": self.enabled_agents,
        }
