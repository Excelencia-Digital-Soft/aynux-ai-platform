"""
Pharmacy Graph Builder

Builds and configures the LangGraph StateGraph for the pharmacy domain.
Single responsibility: graph construction and edge configuration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Hashable, cast

from langgraph.graph import END, StateGraph

from app.domains.pharmacy.agents.builders.node_factory import NodeType
from app.domains.pharmacy.agents.state import PharmacyState

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.execution.node_executor import NodeExecutor
    from app.domains.pharmacy.agents.routing.router import PharmacyRouter

logger = logging.getLogger(__name__)


class PharmacyGraphBuilder:
    """
    Builds the LangGraph StateGraph for the pharmacy domain.

    Responsibility: Construct and configure the graph topology.
    """

    def __init__(
        self,
        nodes: dict[str, Any],
        router: PharmacyRouter,
        executor: NodeExecutor,
    ):
        """
        Initialize the builder.

        Args:
            nodes: Dictionary mapping node names to node instances
            router: The pharmacy router instance
            executor: The node executor instance
        """
        self.nodes = nodes
        self.router = router
        self.executor = executor

    def build(self) -> StateGraph:
        """
        Build the complete LangGraph StateGraph.

        Returns:
            Configured StateGraph (not yet compiled)
        """
        workflow = StateGraph(PharmacyState)

        # Add all nodes
        self._add_nodes(workflow)

        # Set entry point
        workflow.set_entry_point(NodeType.CUSTOMER_IDENTIFICATION)

        # Add all edges
        self._add_edges(workflow)

        logger.info(f"Built pharmacy graph with {len(self.nodes)} nodes")
        return workflow

    def _add_nodes(self, workflow: StateGraph) -> None:
        """
        Add all nodes to the workflow.

        Args:
            workflow: The StateGraph to add nodes to
        """
        # Add node instances wrapped with executor
        for node_name, node_instance in self.nodes.items():
            wrapped_node = self.executor.create_executor(node_instance, node_name)
            workflow.add_node(node_name, wrapped_node)

        # Add router node
        workflow.add_node(NodeType.ROUTER, self.router.route)

    def _add_edges(self, workflow: StateGraph) -> None:
        """
        Add all edges to the workflow.

        Args:
            workflow: The StateGraph to add edges to
        """
        # Customer Identification edges
        workflow.add_conditional_edges(
            NodeType.CUSTOMER_IDENTIFICATION,
            self._route_after_identification,
            {
                "router": NodeType.ROUTER,
                "identification": NodeType.CUSTOMER_IDENTIFICATION,
                "registration": NodeType.CUSTOMER_REGISTRATION,
                "__end__": END,
            },
        )

        # Customer Registration edges
        workflow.add_conditional_edges(
            NodeType.CUSTOMER_REGISTRATION,
            self._route_after_registration,
            {
                "router": NodeType.ROUTER,
                "registration": NodeType.CUSTOMER_REGISTRATION,
                "__end__": END,
            },
        )

        # Router edges
        routing_map: dict[Hashable, str] = {
            NodeType.DEBT_CHECK: NodeType.DEBT_CHECK,
            NodeType.CONFIRMATION: NodeType.CONFIRMATION,
            NodeType.INVOICE: NodeType.INVOICE,
            NodeType.PAYMENT_LINK: NodeType.PAYMENT_LINK,
            "__end__": END,
        }
        workflow.add_conditional_edges(
            NodeType.ROUTER,
            self._get_next_node,
            cast(dict[Hashable, str], routing_map),
        )

        # Operation nodes edges (debt_check, confirmation -> router or end)
        for node in [NodeType.DEBT_CHECK, NodeType.CONFIRMATION]:
            workflow.add_conditional_edges(
                node,
                self._route_after_operation,
                {
                    "router": NodeType.ROUTER,
                    "payment_link": NodeType.PAYMENT_LINK,
                    "__end__": END,
                },
            )

        # Terminal edges
        workflow.add_edge(NodeType.INVOICE, END)
        workflow.add_edge(NodeType.PAYMENT_LINK, END)

    def _route_after_identification(self, state: PharmacyState) -> str:
        """
        Route based on customer identification result.

        Args:
            state: Current state

        Returns:
            Next node key
        """
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "router"
        if state.get("requires_disambiguation") or state.get("awaiting_document_input"):
            return "__end__"
        if state.get("pharmacy_intent_type") == "register_prompt":
            return "registration"
        # Route to registration when in registration flow
        if state.get("awaiting_registration_data"):
            return "registration"
        if self._check_termination(state):
            return "__end__"
        # Prevent looping after out-of-scope response was given
        if state.get("out_of_scope_handled"):
            return "__end__"
        return "identification"

    def _route_after_registration(self, state: PharmacyState) -> str:
        """
        Route based on customer registration result.

        Args:
            state: Current state

        Returns:
            Next node key
        """
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "router"
        if state.get("awaiting_registration_data"):
            return "__end__"
        if self._check_termination(state):
            return "__end__"
        return "registration"

    def _route_after_operation(self, state: PharmacyState) -> str:
        """
        Route after debt check or confirmation.

        Args:
            state: Current state

        Returns:
            Next node key
        """
        # Check for explicit next_agent routing
        next_agent = state.get("next_agent")
        if next_agent == "payment_link_node":
            return "payment_link"

        if state.get("is_complete") or state.get("awaiting_confirmation"):
            return "__end__"

        # If debt is confirmed but not awaiting payment, continue flow
        if state.get("debt_status") == "confirmed" and not state.get("awaiting_payment"):
            return "payment_link"

        return "router"

    def _get_next_node(self, state: PharmacyState) -> str:
        """
        Get the next node from state for conditional routing.

        Args:
            state: Current state

        Returns:
            Next node key
        """
        next_node = state.get("next_agent")
        if next_node and next_node in self.nodes:
            return next_node
        if next_node == "__end__" or state.get("is_complete"):
            return "__end__"
        return NodeType.DEBT_CHECK

    def _check_termination(self, state: PharmacyState) -> bool:
        """
        Check common termination conditions.

        Args:
            state: Current state

        Returns:
            True if should terminate
        """
        if state.get("is_complete"):
            return True
        if state.get("error_count", 0) >= state.get("max_errors", 3):
            return True
        return False
