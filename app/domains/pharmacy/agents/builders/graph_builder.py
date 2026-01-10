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

        # Set entry point - NEW: PersonResolution is the entry point
        # Falls back to CustomerIdentification if PersonResolution not available
        if NodeType.PERSON_RESOLUTION in self.nodes:
            workflow.set_entry_point(NodeType.PERSON_RESOLUTION)
        else:
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
            workflow.add_node(node_name, wrapped_node)  # type: ignore[arg-type]

        # Add router node
        workflow.add_node(NodeType.ROUTER, self.router.route)

    def _add_edges(self, workflow: StateGraph) -> None:
        """
        Add all edges to the workflow.

        Args:
            workflow: The StateGraph to add edges to
        """
        # =========================================================================
        # NEW: Person Resolution Flow Edges
        # =========================================================================
        if NodeType.PERSON_RESOLUTION in self.nodes:
            workflow.add_conditional_edges(
                NodeType.PERSON_RESOLUTION,
                self._route_after_person_resolution,
                {
                    "person_selection": NodeType.PERSON_SELECTION,
                    "person_validation": NodeType.PERSON_VALIDATION,
                    "debt_check": NodeType.DEBT_CHECK,
                    "router": NodeType.ROUTER,
                    "__end__": END,
                },
            )

        if NodeType.PERSON_SELECTION in self.nodes:
            workflow.add_conditional_edges(
                NodeType.PERSON_SELECTION,
                self._route_after_person_selection,
                {
                    "person_validation": NodeType.PERSON_VALIDATION,
                    "debt_check": NodeType.DEBT_CHECK,
                    "person_selection": NodeType.PERSON_SELECTION,
                    "__end__": END,
                },
            )

        if NodeType.PERSON_VALIDATION in self.nodes:
            workflow.add_conditional_edges(
                NodeType.PERSON_VALIDATION,
                self._route_after_person_validation,
                {
                    "debt_check": NodeType.DEBT_CHECK,
                    "person_validation": NodeType.PERSON_VALIDATION,
                    "__end__": END,
                },
            )

        # =========================================================================
        # Existing Edges (Customer Identification - kept for backward compatibility)
        # =========================================================================
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

    # =========================================================================
    # Person Resolution Flow Routing Functions (NEW)
    # =========================================================================

    def _route_after_person_resolution(self, state: PharmacyState) -> str:
        """
        Route based on person resolution result.

        Scenarios:
        - Multiple registered persons found → person_selection
        - Phone owner detected, querying for other → person_validation
        - Phone owner detected, querying for self → debt_check
        - No detection, need validation → person_validation
        - Awaiting own/other answer → __end__ (wait for user input)

        Args:
            state: Current state

        Returns:
            Next node key
        """
        # If awaiting user response for own/other question
        if state.get("awaiting_own_or_other"):
            return "__end__"

        # If user wants to query for someone else → validate that person
        if state.get("is_querying_for_other"):
            return "person_validation"

        # If multiple registered persons available → show selection
        registered_persons = state.get("registered_persons") or []
        if len(registered_persons) > 1 or state.get("awaiting_person_selection"):
            return "person_selection"

        # If customer already identified → proceed to debt check
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "debt_check"

        # If no detection and need validation
        if not state.get("customer_identified"):
            return "person_validation"

        # Check termination conditions
        if self._check_termination(state):
            return "__end__"

        # Default to router for existing flow compatibility
        return "router"

    def _route_after_person_selection(self, state: PharmacyState) -> str:
        """
        Route based on person selection result.

        Scenarios:
        - Person selected and validated → debt_check
        - User wants to add new person → person_validation
        - Still awaiting selection → __end__ (wait for user input)
        - Invalid selection, retry → person_selection

        Args:
            state: Current state

        Returns:
            Next node key
        """
        # If user chose to add a new person
        if state.get("is_new_person_flow"):
            return "person_validation"

        # If awaiting user selection
        if state.get("awaiting_person_selection"):
            return "__end__"

        # If customer now identified after selection → proceed to debt check
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "debt_check"

        # Check termination conditions
        if self._check_termination(state):
            return "__end__"

        # Default to retry selection
        return "person_selection"

    def _route_after_person_validation(self, state: PharmacyState) -> str:
        """
        Route based on person validation result.

        Scenarios:
        - Validation complete, customer identified → debt_check
        - Awaiting DNI input → __end__ (wait for user)
        - Awaiting name input → __end__ (wait for user)
        - Multiple PLEX candidates, awaiting disambiguation → __end__
        - Validation failed, retry → person_validation

        Args:
            state: Current state

        Returns:
            Next node key
        """
        validation_step = state.get("validation_step")

        # If awaiting user input for any validation step
        if validation_step in ("dni", "name", "confirm"):
            return "__end__"

        # If there are multiple candidates awaiting disambiguation
        plex_candidates = state.get("plex_candidates") or []
        if len(plex_candidates) > 1:
            return "__end__"

        # If validation complete and customer identified → debt check
        if state.get("customer_identified") and state.get("plex_customer_id"):
            return "debt_check"

        # Check termination conditions
        if self._check_termination(state):
            return "__end__"

        # Check name mismatch retry limit (max 3 attempts)
        name_mismatch_count = state.get("name_mismatch_count", 0)
        if name_mismatch_count >= 3:
            return "__end__"

        # Default to retry validation
        return "person_validation"
