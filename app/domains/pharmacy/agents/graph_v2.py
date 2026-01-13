"""
Pharmacy Domain Graph V2 - Simplified LangGraph Implementation

This is the refactored pharmacy flow with:
- 6 main nodes (down from 15+)
- Database-driven routing
- WhatsApp buttons/lists support
- Simplified state (~30 fields)

Architecture:
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         │
                         ▼
              ┌───────────────────┐
              │ ROUTER_SUPERVISOR │
              │ DB-driven routing │
              └─────────┬─────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
  ┌───────────┐  ┌───────────┐  ┌───────────┐
  │ AUTH_PLEX │  │   DEBT    │  │  ACCOUNT  │
  │           │  │  MANAGER  │  │  SWITCHER │
  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
        │               │               │
        │               ▼               │
        │        ┌───────────┐          │
        │        │  PAYMENT  │          │
        │        │ PROCESSOR │          │
        │        └─────┬─────┘          │
        │               │               │
        └───────────────┼───────────────┘
                        │
                        ▼
              ┌───────────────────┐
              │    RESPONSE       │
              │    FORMATTER      │
              └─────────┬─────────┘
                        │
                        ▼
                   ┌──────────┐
                   │   END    │
                   └──────────┘
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from app.domains.pharmacy.agents.state_v2 import PharmacyStateV2, get_state_defaults

if TYPE_CHECKING:
    from app.integrations.databases import PostgreSQLIntegration

logger = logging.getLogger(__name__)


# =============================================================================
# Node Type Constants
# =============================================================================


class NodeType:
    """Node type constants for the simplified graph."""

    ROUTER = "router"
    AUTH_PLEX = "auth_plex"
    DEBT_MANAGER = "debt_manager"
    PAYMENT_PROCESSOR = "payment_processor"
    ACCOUNT_SWITCHER = "account_switcher"
    RESPONSE_FORMATTER = "response_formatter"
    INFO_NODE = "info_node"


# =============================================================================
# Placeholder Node Implementations
# =============================================================================
# These will be replaced with actual implementations from nodes/


async def auth_plex_node(state: PharmacyStateV2) -> dict[str, Any]:
    """
    Authentication node - handles PLEX customer identification.

    Responsibilities:
    - DNI validation
    - PLEX customer lookup
    - Name verification
    - RegisteredPerson creation/update

    TODO: Implement actual logic from person_resolution_node
    """
    logger.info("auth_plex_node called")

    # Placeholder: Just mark as authenticated for now
    # In real implementation, this would:
    # 1. Check for DNI input if awaiting_input == "dni"
    # 2. Validate DNI format
    # 3. Lookup customer in PLEX
    # 4. Request name verification if needed
    # 5. Create/update RegisteredPerson

    return {
        "is_authenticated": True,
        "awaiting_input": None,
        "next_node": "debt_manager",
    }


async def debt_manager_node(state: PharmacyStateV2) -> dict[str, Any]:
    """
    Debt management node - handles debt queries.

    Responsibilities:
    - Fetch debt from PLEX
    - Format debt display
    - Handle "no debt" case

    TODO: Implement actual logic from debt_check_node
    """
    logger.info("debt_manager_node called")

    # Placeholder: Return sample debt
    return {
        "total_debt": 15000.00,
        "has_debt": True,
        "debt_fetched_at": datetime.now().isoformat(),
        "debt_items": [
            {"invoice": "FC-001", "amount": 10000.00, "date": "2026-01-10"},
            {"invoice": "FC-002", "amount": 5000.00, "date": "2026-01-12"},
        ],
        "next_node": "response_formatter",
    }


async def payment_processor_node(state: PharmacyStateV2) -> dict[str, Any]:
    """
    Payment processing node - handles Mercado Pago payments.

    Responsibilities:
    - Validate payment amount
    - Create MP preference
    - Generate payment link
    - Handle payment confirmation

    TODO: Implement actual logic from payment_link_node
    """
    logger.info("payment_processor_node called")

    intent = state.get("intent")

    # If waiting for confirmation
    if state.get("awaiting_payment_confirmation"):
        # Check if user confirmed
        if intent == "confirm_yes":
            # Generate payment link
            return {
                "mp_payment_link": "https://www.mercadopago.com.ar/checkout/v1/...",
                "awaiting_payment_confirmation": False,
                "next_node": "response_formatter",
            }
        elif intent == "confirm_no":
            return {
                "awaiting_payment_confirmation": False,
                "intent": "show_menu",
                "next_node": "response_formatter",
            }

    # Set up for confirmation
    amount = state.get("payment_amount") or state.get("total_debt") or 0
    is_partial = intent == "pay_partial"

    return {
        "payment_amount": amount,
        "is_partial_payment": is_partial,
        "awaiting_payment_confirmation": True,
        "next_node": "response_formatter",
    }


async def account_switcher_node(state: PharmacyStateV2) -> dict[str, Any]:
    """
    Account switching node - handles multiple registered accounts.

    Responsibilities:
    - Show account selection list
    - Handle account selection
    - Handle "own vs other" question

    TODO: Implement actual logic from person_selection_node
    """
    logger.info("account_switcher_node called")

    intent = state.get("intent")

    # Handle own/other selection
    if intent == "own_debt":
        return {
            "is_self": True,
            "awaiting_input": None,
            "next_node": "debt_manager",
        }
    elif intent == "other_debt":
        return {
            "is_self": False,
            "awaiting_account_selection": True,
            "next_node": "response_formatter",
        }

    # Handle account selection
    if state.get("awaiting_account_selection"):
        # In real implementation, parse the selection
        return {
            "awaiting_account_selection": False,
            "next_node": "debt_manager",
        }

    # Ask own or other
    return {
        "awaiting_input": "own_or_other",
        "next_node": "response_formatter",
    }


async def info_node(state: PharmacyStateV2) -> dict[str, Any]:
    """
    Information node - handles pharmacy info queries.

    Responsibilities:
    - Return pharmacy info
    - Handle capability questions

    TODO: Implement actual logic from pharmacy_info_node
    """
    logger.info("info_node called")

    return {
        "next_node": "response_formatter",
    }


# =============================================================================
# Graph Builder
# =============================================================================


def build_pharmacy_graph_v2() -> StateGraph:
    """
    Build the simplified pharmacy graph with 6 main nodes.

    Returns:
        Configured StateGraph
    """
    from app.domains.pharmacy.agents.nodes.response_formatter import (
        response_formatter_node,
    )
    from app.domains.pharmacy.agents.nodes.router_supervisor import (
        router_supervisor_node,
    )

    workflow = StateGraph(PharmacyStateV2)

    # === Add Nodes ===
    workflow.add_node(NodeType.ROUTER, router_supervisor_node)
    workflow.add_node(NodeType.AUTH_PLEX, auth_plex_node)
    workflow.add_node(NodeType.DEBT_MANAGER, debt_manager_node)
    workflow.add_node(NodeType.PAYMENT_PROCESSOR, payment_processor_node)
    workflow.add_node(NodeType.ACCOUNT_SWITCHER, account_switcher_node)
    workflow.add_node(NodeType.INFO_NODE, info_node)
    workflow.add_node(NodeType.RESPONSE_FORMATTER, response_formatter_node)

    # === Entry Point ===
    workflow.set_entry_point(NodeType.ROUTER)

    # === Router Conditional Edges ===
    def route_from_router(state: PharmacyStateV2) -> str:
        """Route based on next_node from router."""
        next_node = state.get("next_node")

        if next_node == "__end__":
            return END

        # Map node names to actual nodes
        node_map = {
            "auth_plex": NodeType.AUTH_PLEX,
            "debt_manager": NodeType.DEBT_MANAGER,
            "payment_processor": NodeType.PAYMENT_PROCESSOR,
            "account_switcher": NodeType.ACCOUNT_SWITCHER,
            "info_node": NodeType.INFO_NODE,
            "response_formatter": NodeType.RESPONSE_FORMATTER,
            "main_menu_node": NodeType.RESPONSE_FORMATTER,
            "farewell_node": NodeType.RESPONSE_FORMATTER,
            "help_center_node": NodeType.RESPONSE_FORMATTER,
            "human_escalation_node": NodeType.RESPONSE_FORMATTER,
        }

        return node_map.get(next_node or "", NodeType.RESPONSE_FORMATTER)

    workflow.add_conditional_edges(
        NodeType.ROUTER,
        route_from_router,
        {
            NodeType.AUTH_PLEX: NodeType.AUTH_PLEX,
            NodeType.DEBT_MANAGER: NodeType.DEBT_MANAGER,
            NodeType.PAYMENT_PROCESSOR: NodeType.PAYMENT_PROCESSOR,
            NodeType.ACCOUNT_SWITCHER: NodeType.ACCOUNT_SWITCHER,
            NodeType.INFO_NODE: NodeType.INFO_NODE,
            NodeType.RESPONSE_FORMATTER: NodeType.RESPONSE_FORMATTER,
            END: END,
        },
    )

    # === Auth → Debt or Response ===
    def route_after_auth(state: PharmacyStateV2) -> str:
        """Route after authentication."""
        if state.get("is_authenticated"):
            next_node = state.get("next_node")
            if next_node == "debt_manager":
                return NodeType.DEBT_MANAGER
            elif next_node == "payment_processor":
                return NodeType.PAYMENT_PROCESSOR
            return NodeType.DEBT_MANAGER
        return NodeType.RESPONSE_FORMATTER

    workflow.add_conditional_edges(
        NodeType.AUTH_PLEX,
        route_after_auth,
        {
            NodeType.DEBT_MANAGER: NodeType.DEBT_MANAGER,
            NodeType.PAYMENT_PROCESSOR: NodeType.PAYMENT_PROCESSOR,
            NodeType.RESPONSE_FORMATTER: NodeType.RESPONSE_FORMATTER,
        },
    )

    # === Debt Manager → Response ===
    workflow.add_edge(NodeType.DEBT_MANAGER, NodeType.RESPONSE_FORMATTER)

    # === Payment Processor → Response ===
    workflow.add_edge(NodeType.PAYMENT_PROCESSOR, NodeType.RESPONSE_FORMATTER)

    # === Account Switcher → Conditional ===
    def route_after_account_switch(state: PharmacyStateV2) -> str:
        """Route after account switch decision."""
        if state.get("current_account_id"):
            return NodeType.DEBT_MANAGER
        return NodeType.RESPONSE_FORMATTER

    workflow.add_conditional_edges(
        NodeType.ACCOUNT_SWITCHER,
        route_after_account_switch,
        {
            NodeType.DEBT_MANAGER: NodeType.DEBT_MANAGER,
            NodeType.RESPONSE_FORMATTER: NodeType.RESPONSE_FORMATTER,
        },
    )

    # === Info Node → Response ===
    workflow.add_edge(NodeType.INFO_NODE, NodeType.RESPONSE_FORMATTER)

    # === Response Formatter → END ===
    workflow.add_edge(NodeType.RESPONSE_FORMATTER, END)

    return workflow


# =============================================================================
# Graph Class (Compatible with existing PharmacyGraph interface)
# =============================================================================


class PharmacyGraphV2:
    """
    Pharmacy domain LangGraph V2 implementation.

    Simplified version with 6 main nodes and database-driven routing.
    Compatible with the existing PharmacyGraph interface.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize pharmacy graph V2.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.graph = build_pharmacy_graph_v2()
        self._postgres: PostgreSQLIntegration | None = None
        self._checkpointer = None
        self.app = None

        logger.info("PharmacyGraphV2 initialized")

    async def initialize(self, postgres: "PostgreSQLIntegration | None" = None) -> None:
        """
        Initialize and compile the graph with PostgreSQL checkpointer.

        Args:
            postgres: PostgreSQLIntegration instance for checkpointing
        """
        try:
            checkpointer = None

            if postgres:
                self._postgres = postgres
                if not postgres._checkpointer:
                    await postgres.initialize()
                checkpointer = postgres.get_checkpointer()
                self._checkpointer = checkpointer
                logger.info("PharmacyGraphV2 using PostgreSQL async checkpointer")

            self.app = self.graph.compile(checkpointer=checkpointer)
            logger.info(f"PharmacyGraphV2 compiled with checkpointer=" f"{'enabled' if checkpointer else 'disabled'}")
        except Exception as e:
            logger.error(f"Error compiling PharmacyGraphV2: {e}", exc_info=True)
            raise

    async def invoke(
        self,
        message: str,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Process a message through the pharmacy graph.

        Args:
            message: User message content
            conversation_id: Optional conversation ID for state persistence
            **kwargs: Additional state fields

        Returns:
            Final state dict after graph execution
        """
        if not self.app:
            raise RuntimeError("Graph not initialized. Call initialize() first")

        logger.info(f"[PHARMACY_GRAPH_V2] invoke with conversation_id={conversation_id}")

        try:
            # Filter None values to preserve checkpoint state
            filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

            # Start with defaults, then apply kwargs
            initial_state: dict[str, Any] = {
                **get_state_defaults(),
                "messages": [HumanMessage(content=message)],
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "is_complete": False,
                **filtered_kwargs,
            }

            config: dict[str, Any] = {}
            if conversation_id:
                pharmacy_thread_id = f"pharmacy_v2:{conversation_id}"
                config["configurable"] = {"thread_id": pharmacy_thread_id}

            result = await self.app.ainvoke(initial_state, cast(RunnableConfig, config))
            return dict(result)

        except Exception as e:
            logger.error(f"Error invoking PharmacyGraphV2: {e}", exc_info=True)
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check health of the graph."""
        return {
            "graph_compiled": self.app is not None,
            "version": 2,
            "nodes": [
                NodeType.ROUTER,
                NodeType.AUTH_PLEX,
                NodeType.DEBT_MANAGER,
                NodeType.PAYMENT_PROCESSOR,
                NodeType.ACCOUNT_SWITCHER,
                NodeType.INFO_NODE,
                NodeType.RESPONSE_FORMATTER,
            ],
        }


# =============================================================================
# Factory Function
# =============================================================================


def create_pharmacy_graph_v2(
    config: dict[str, Any] | None = None,
) -> PharmacyGraphV2:
    """
    Factory function to create PharmacyGraphV2.

    Args:
        config: Optional configuration

    Returns:
        Configured PharmacyGraphV2 instance
    """
    return PharmacyGraphV2(config)
