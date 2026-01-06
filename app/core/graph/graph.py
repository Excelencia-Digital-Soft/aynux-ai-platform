"""
Graph principal del sistema multi-agente LangGraph (Simplified)

Supports DUAL-MODE operation:
- Global mode (no tenant): Agents use Python defaults
- Multi-tenant mode (with token): Agents configured from database per-request

The set_tenant_registry() method propagates tenant configuration to all agents.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.langsmith_config import ConversationTracer, get_tracer
from app.core.graph.execution.context_middleware import ConversationContextMiddleware
from app.core.graph.execution.node_executor import NodeExecutor
from app.core.graph.execution.response_processor import ResponseProcessor
from app.core.graph.execution.tenant_config_manager import TenantConfigManager
from app.core.graph.factories.agent_factory import AgentFactory
from app.core.graph.factories.agent_status_manager import AgentStatusManager
from app.core.graph.factories.graph_builder import GraphBuilder
from app.core.graph.routing.graph_router import GraphRouter
from app.core.utils.tracing import trace_async_method, trace_context
from app.domains.shared.agents.history_agent import HistoryAgent
from app.integrations.databases import PostgreSQLIntegration
from app.integrations.llm import VllmLLM

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

        # Build graph using GraphBuilder
        builder = GraphBuilder(
            enabled_agents=self.enabled_agents,
            agents=self.agents,
            executor=self.executor,
            router=self.router,
        )
        self.graph = builder.build()

        self.app = None
        self.checkpointer_manager = None
        self.persistent_checkpointer = None
        self.use_postgres_checkpointer = True

        logger.info("AynuxGraph initialized successfully")

    def _init_components(self) -> None:
        """Initialize all graph components"""
        # Initialize integrations
        self.llm = VllmLLM()
        # PostgreSQLIntegration uses settings.database_url by default
        self.postgres = PostgreSQLIntegration()

        # Initialize factory and create agents
        self.agent_factory = AgentFactory(
            llm=self.llm, postgres=self.postgres, config=self.config
        )
        self.agents = self.agent_factory.initialize_all_agents()

        # Initialize history agent for conversation context management
        history_config = self.config.get("history", {})
        self.history_agent = HistoryAgent(
            llm=self.llm,
            postgres=self.postgres,
            config={
                "summary_interval": history_config.get("summary_interval", 5),
                "max_summary_tokens": history_config.get("max_summary_tokens", 300),
            },
        )

        # Initialize router with enabled agents configuration
        self.router = GraphRouter(enabled_agents=self.enabled_agents)
        self.executor = NodeExecutor(self.agents, self.conversation_tracers)

        # Initialize extracted components
        self.context_middleware = ConversationContextMiddleware(self.history_agent)
        self.response_processor = ResponseProcessor()
        self.status_manager = AgentStatusManager(
            enabled_agents=self.enabled_agents,
            agents=self.agents,
            agent_factory=self.agent_factory,
        )
        self.tenant_manager = TenantConfigManager(self.agent_factory)

    async def initialize(self, db_url: Optional[str] = None) -> None:
        """Initialize and compile the graph with PostgreSQL async checkpointer"""
        try:
            checkpointer = None
            if self.use_postgres_checkpointer:
                try:
                    # Inicializar PostgreSQL integration si no está inicializado
                    if not self.postgres._checkpointer:
                        await self.postgres.initialize()

                    # Obtener checkpointer async
                    checkpointer = self.postgres.get_checkpointer()
                    logger.info("PostgreSQL async checkpointer enabled")
                except Exception as e:
                    logger.warning(f"Could not setup PostgreSQL checkpointer: {e}")
                    checkpointer = None

            self.app = self.graph.compile(checkpointer=checkpointer)
            logger.info(
                f"Graph compiled with checkpointer={'enabled' if checkpointer else 'disabled'}"
            )

        except Exception as e:
            logger.error(f"Error initializing graph: {e}")
            raise

    @trace_async_method(
        name="graph_invoke",
        run_type="chain",
        metadata={"component": "langgraph", "operation": "conversation_processing"},
        extract_state=False,
    )
    async def invoke(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        db_session: AsyncSession | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
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
            db_session: Optional database session for persistence
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

            if (
                self.tracer.config.tracing_enabled
                and conv_id not in self.conversation_tracers
            ):
                self.conversation_tracers[conv_id] = ConversationTracer(
                    conv_id, user_id
                )
                logger.info(f"Started conversation tracking for {conv_id}")

            conv_tracker = self.conversation_tracers.get(conv_id)

            if conv_tracker:
                conv_tracker.add_message(
                    "user", message, {"timestamp": datetime.now().isoformat()}
                )

            # MIDDLEWARE: Prepare execution context using extracted components
            self.context_middleware.prepare_db_session(db_session)
            context = await self.context_middleware.load_context(conv_id, **kwargs)
            initial_state = self.context_middleware.build_initial_state(
                message, conv_id, user_id, context, **kwargs
            )
            config = self.context_middleware.build_checkpointer_config(conv_id)

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
                result = await self.app.ainvoke(
                    initial_state, cast(RunnableConfig, config)
                )

                # Track response
                if conv_tracker and result.get("messages"):
                    for msg in result["messages"]:
                        if hasattr(msg, "content"):
                            conv_tracker.add_message(
                                "assistant",
                                msg.content,
                                {
                                    "agent": result.get("current_agent"),
                                    "timestamp": datetime.now().isoformat(),
                                },
                            )

                # MIDDLEWARE: Update conversation context
                await self.context_middleware.update_context(
                    result, message, context, conv_id, self.response_processor
                )

                return result

        except Exception as e:
            logger.error(f"Error invoking graph: {e}")
            raise

    async def astream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        db_session: AsyncSession | None = None,
        **kwargs: Any,
    ):
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
            db_session: Optional database session for persistence
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

            if (
                self.tracer.config.tracing_enabled
                and conv_id not in self.conversation_tracers
            ):
                self.conversation_tracers[conv_id] = ConversationTracer(
                    conv_id, user_id
                )
                logger.info(f"Started conversation tracking for {conv_id}")

            conv_tracker = self.conversation_tracers.get(conv_id)
            if conv_tracker:
                conv_tracker.add_message(
                    "user", message, {"timestamp": datetime.now().isoformat()}
                )

            # MIDDLEWARE: Prepare execution context using extracted components
            self.context_middleware.prepare_db_session(db_session)
            context = await self.context_middleware.load_context(conv_id, **kwargs)
            initial_state = self.context_middleware.build_initial_state(
                message, conv_id, user_id, context, **kwargs
            )
            config = self.context_middleware.build_checkpointer_config(conv_id)

            # Execute graph with streaming
            final_result = None
            step_count = 0

            try:
                # Stream through the graph execution
                async for chunk in app.astream(
                    initial_state, cast(RunnableConfig, config)
                ):
                    step_count += 1

                    # Emit progress events based on graph steps
                    if chunk:
                        # LangGraph astream yields dict with node names as keys
                        for node_name, node_state in chunk.items():
                            # Yield streaming event
                            yield {
                                "type": "stream_event",
                                "data": {
                                    "current_node": node_name,
                                    "step_count": step_count,
                                    "state_preview": self.response_processor.create_state_preview(
                                        node_state
                                    ),
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
                                {
                                    "agent": final_result.get("current_agent"),
                                    "timestamp": datetime.now().isoformat(),
                                },
                            )

                # MIDDLEWARE: Update conversation context
                if final_result:
                    await self.context_middleware.update_context(
                        final_result, message, context, conv_id, self.response_processor
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
                yield {
                    "type": "error",
                    "data": {"error": str(e), "timestamp": datetime.now().isoformat()},
                }
                raise

        except Exception as e:
            logger.error(f"Error in conversation stream setup: {e}")
            yield {
                "type": "error",
                "data": {"error": str(e), "timestamp": datetime.now().isoformat()},
            }
            raise

    # =========================================================================
    # Agent Status Methods (delegated to AgentStatusManager)
    # =========================================================================

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled in the graph."""
        return self.status_manager.is_agent_enabled(agent_name)

    def get_enabled_agents(self) -> list[str]:
        """Get list of enabled agent names."""
        return self.status_manager.get_enabled_agents()

    def get_disabled_agents(self) -> list[str]:
        """Get list of disabled agent names."""
        return self.status_manager.get_disabled_agents()

    def get_agent_status(self) -> Dict[str, Any]:
        """Get complete agent status information."""
        return self.status_manager.get_agent_status()

    # =========================================================================
    # Dual-Mode Methods (delegated to TenantConfigManager)
    # =========================================================================

    def set_tenant_registry(self, registry: "TenantAgentRegistry") -> None:
        """
        Set tenant registry and apply configuration to all agents.

        Called per-request in multi-tenant mode to configure agents
        with tenant-specific settings from database.

        Args:
            registry: TenantAgentRegistry loaded from database
        """
        self.tenant_manager.set_tenant_registry(registry)

    def reset_tenant_config(self) -> None:
        """Reset all agents to global default configuration."""
        self.tenant_manager.reset_tenant_config()

    def get_mode_info(self) -> Dict[str, Any]:
        """Get information about current graph operation mode."""
        return self.tenant_manager.get_mode_info(
            app_initialized=self.app is not None,
            enabled_agents=self.enabled_agents,
        )
