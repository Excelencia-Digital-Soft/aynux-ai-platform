"""
Pharmacy Domain Graph

LangGraph StateGraph implementation for the pharmacy domain.
Handles customer identification, debt checking, confirmation, and receipt generation.

Refactored to use SRP-compliant components:
- PharmacyNodeFactory: Node creation with dependency injection
- PharmacyGraphBuilder: Graph topology construction
- PharmacyRouter: Intent analysis and routing coordination
- NodeExecutor: Node execution with error handling
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.clients.plex_client import PlexClient
from app.domains.pharmacy.agents.builders import (
    NodeType,
    PharmacyGraphBuilder,
    PharmacyNodeFactory,
)
from app.domains.pharmacy.agents.execution import NodeExecutor
from app.domains.pharmacy.agents.intent_analyzer import get_pharmacy_intent_analyzer
from app.domains.pharmacy.agents.nodes.fallback_handler import PharmacyFallbackHandler
from app.domains.pharmacy.agents.routing import (
    FallbackRouter,
    PharmacyRouter,
    RoutingStateBuilder,
)
from app.domains.pharmacy.agents.utils import (
    ConversationContextBuilder,
    GreetingDetector,
    MessageFormatter,
)

if TYPE_CHECKING:
    from app.integrations.databases import PostgreSQLIntegration

logger = logging.getLogger(__name__)


# Re-export NodeType for backward compatibility
PharmacyNodeType = NodeType

# Intent to node mapping (used by routing components)
INTENT_NODE_MAP: dict[str, str] = {
    "debt_query": NodeType.DEBT_CHECK,
    "confirm": NodeType.CONFIRMATION,
    "invoice": NodeType.INVOICE,
    "payment_link": NodeType.PAYMENT_LINK,
    "register": NodeType.CUSTOMER_REGISTRATION,
}

# Intents handled by fallback handler
FALLBACK_INTENTS = frozenset({"greeting", "reject", "unknown", "summary", "data_query", "info_query"})


class PharmacyGraph:
    """
    Pharmacy domain LangGraph implementation.

    Orchestrator that composes SRP-compliant components:
    - PharmacyNodeFactory: Creates node instances with dependencies
    - PharmacyGraphBuilder: Builds the LangGraph StateGraph
    - PharmacyRouter: Coordinates intent analysis and routing
    - NodeExecutor: Wraps node execution with error handling

    Flow:
    1. Customer Identification -> Identify user from WhatsApp phone
    2. (Optional) Customer Registration -> Register new customers
    3. Debt Check -> Show debt to customer
    4. Confirmation -> Customer confirms debt
    5. Invoice/Receipt Generation -> Generate receipt for payment
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize pharmacy graph with composable components.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

        # Create core dependencies
        self._plex_client = PlexClient()
        self._intent_analyzer = get_pharmacy_intent_analyzer(
            use_llm_fallback=self.config.get("use_llm_fallback", True),
        )
        self._fallback_handler = PharmacyFallbackHandler()

        # Create utility components
        self._greeting_detector = GreetingDetector()
        self._context_builder = ConversationContextBuilder()
        self._message_formatter = MessageFormatter()
        self._state_builder = RoutingStateBuilder()

        # Create routing components
        self._fallback_router = FallbackRouter(self._fallback_handler)
        self._router = PharmacyRouter(
            intent_analyzer=self._intent_analyzer,
            fallback_router=self._fallback_router,
            state_builder=self._state_builder,
            greeting_detector=self._greeting_detector,
            context_builder=self._context_builder,
        )

        # Create node executor
        self._executor = NodeExecutor(self._message_formatter)

        # Create nodes using factory
        self._node_factory = PharmacyNodeFactory(
            plex_client=self._plex_client,
            config=self.config,
        )
        enabled_nodes = self.config.get("enabled_nodes")
        self.nodes = self._node_factory.create_nodes(enabled_nodes)

        # Build the graph
        self._graph_builder = PharmacyGraphBuilder(
            nodes=self.nodes,
            router=self._router,
            executor=self._executor,
        )
        self.graph = self._graph_builder.build()

        # PostgreSQL checkpointer for state persistence
        self._postgres: PostgreSQLIntegration | None = None
        self._checkpointer = None
        self.app = None

        logger.info(f"PharmacyGraph initialized with nodes: {list(self.nodes.keys())}")

    async def initialize(self, postgres: PostgreSQLIntegration | None = None) -> None:
        """
        Initialize and compile the graph with PostgreSQL async checkpointer.

        Args:
            postgres: PostgreSQLIntegration instance for checkpointing. If provided,
                     enables state persistence across conversation turns.
        """
        try:
            checkpointer = None

            if postgres:
                self._postgres = postgres
                # Ensure PostgreSQL is initialized
                if not postgres._checkpointer:
                    await postgres.initialize()
                checkpointer = postgres.get_checkpointer()
                self._checkpointer = checkpointer
                logger.info("PharmacyGraph using PostgreSQL async checkpointer")

            self.app = self.graph.compile(checkpointer=checkpointer)
            logger.info(
                f"PharmacyGraph compiled with checkpointer={'enabled' if checkpointer else 'disabled'}"
            )
        except Exception as e:
            logger.error(f"Error compiling PharmacyGraph: {e}", exc_info=True)
            raise

    async def invoke(self, message: str, conversation_id: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        Process a message through the pharmacy graph.

        Args:
            message: User message content
            conversation_id: Optional conversation ID for state persistence
            **kwargs: Additional state fields to pass through

        Returns:
            Final state dict after graph execution
        """
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        try:
            initial_state: dict[str, Any] = {
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "is_complete": False,
                "error_count": 0,
                "max_errors": self.config.get("max_errors", 3),
                "has_debt": False,
                "awaiting_confirmation": False,
                "confirmation_received": False,
                "customer_identified": False,
                "requires_disambiguation": False,
                "awaiting_document_input": False,
                "awaiting_registration_data": False,
                "is_bypass_route": kwargs.get("is_bypass_route", False),
                "requires_human": False,
                **kwargs,
            }

            config: dict[str, Any] = {}
            if conversation_id:
                config["configurable"] = {"thread_id": conversation_id}

            result = await self.app.ainvoke(initial_state, cast(RunnableConfig, config))
            return dict(result)

        except Exception as e:
            logger.error(f"Error invoking PharmacyGraph: {e}", exc_info=True)
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check health of the pharmacy graph and its components.

        Returns:
            Health status dict with component states
        """
        health: dict[str, Any] = {
            "graph_compiled": self.app is not None,
            "nodes_enabled": list(self.nodes.keys()),
            "plex_client_configured": bool(self._plex_client.base_url),
            "intent_analyzer": self._intent_analyzer.get_model_info(),
            "components": {
                "node_factory": True,
                "graph_builder": True,
                "router": True,
                "executor": True,
            },
        }

        if self._plex_client.base_url:
            try:
                async with self._plex_client:
                    health["plex_connection"] = await self._plex_client.test_connection()
            except Exception as e:
                health["plex_connection"] = False
                health["plex_error"] = str(e)

        return health

    @property
    def enabled_nodes(self) -> list[str]:
        """Get list of enabled node types."""
        return list(self.nodes.keys())
