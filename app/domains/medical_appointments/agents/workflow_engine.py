# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Configurable workflow engine that builds graphs from DB config.
# ============================================================================
"""Configurable Workflow Engine.

Builds and executes LangGraph StateGraphs from database workflow configuration.
Supports dynamic node composition, conditional transitions, and routing rules.

Usage:
    # Load workflow from database
    workflow_def = await workflow_service.get_active_workflow(institution_config_id)

    # Build engine
    engine = ConfigurableWorkflowEngine(
        workflow_def=workflow_def,
        node_instances=nodes,
        transitions=transitions,
        routing_rules=rules,
        medical_client=soap_client,
        notification_service=notification,
        base_config=config,
    )

    # Build and compile
    engine.build()
    compiled = engine.compile()

    # Execute
    result = await engine.invoke(state)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .nodes import BaseNode, get_node_registry
from .state import MedicalAppointmentsState

if TYPE_CHECKING:
    from app.models.db.workflow import (
        NodeInstance,
        RoutingRule,
        WorkflowDefinition,
        WorkflowTransition,
    )

    from ..application.ports import IMedicalSystemClient, INotificationService


logger = logging.getLogger(__name__)


class ConfigurableWorkflowEngine:
    """Engine that builds and executes configurable workflows.

    Reads workflow configuration from database and constructs a LangGraph
    StateGraph with the specified nodes, transitions, and routing rules.
    """

    def __init__(
        self,
        workflow_def: "WorkflowDefinition",
        node_instances: list["NodeInstance"],
        transitions: list["WorkflowTransition"],
        routing_rules: list["RoutingRule"],
        medical_client: "IMedicalSystemClient",
        notification_service: "INotificationService | None" = None,
        base_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize workflow engine.

        Args:
            workflow_def: Workflow definition from database.
            node_instances: List of node instances in the workflow.
            transitions: List of transitions between nodes.
            routing_rules: List of routing rules to apply.
            medical_client: Medical system client for API calls.
            notification_service: Optional notification service for WhatsApp.
            base_config: Base configuration dict (institution settings).
        """
        self._workflow_def = workflow_def
        self._node_instances = node_instances
        self._transitions = transitions
        self._routing_rules = routing_rules
        self._medical_client = medical_client
        self._notification_service = notification_service
        self._base_config = base_config or {}

        # Registry for node instantiation
        self._registry = get_node_registry()

        # Built artifacts
        self._graph: StateGraph | None = None
        self._compiled: CompiledStateGraph | None = None
        self._nodes: dict[str, BaseNode] = {}

        # Index structures for efficient lookup
        self._instance_by_id: dict[str, "NodeInstance"] = {
            str(ni.id): ni for ni in node_instances
        }
        self._transitions_by_source: dict[str, list["WorkflowTransition"]] = {}
        for t in transitions:
            source_id = str(t.source_node_id)
            if source_id not in self._transitions_by_source:
                self._transitions_by_source[source_id] = []
            self._transitions_by_source[source_id].append(t)

        # Sort transitions by priority
        for source_id in self._transitions_by_source:
            self._transitions_by_source[source_id].sort(
                key=lambda t: t.priority
            )

    @property
    def workflow_id(self) -> str:
        """Get workflow ID."""
        return str(self._workflow_def.id)

    @property
    def workflow_key(self) -> str:
        """Get workflow key."""
        return self._workflow_def.workflow_key

    def build(self) -> "ConfigurableWorkflowEngine":
        """Build the StateGraph from configuration.

        Returns:
            Self for chaining.

        Raises:
            ValueError: If configuration is invalid.
        """
        logger.info(f"Building workflow: {self.workflow_key}")

        # Instantiate all nodes
        self._instantiate_nodes()

        # Build graph
        self._graph = StateGraph(MedicalAppointmentsState)

        # Add nodes to graph
        for instance_key, node in self._nodes.items():
            self._graph.add_node(instance_key, node)

        # Set entry point
        entry_node = self._get_entry_node()
        if entry_node:
            self._graph.set_entry_point(entry_node)
        else:
            # Fallback to router if no entry point specified
            if "router" in self._nodes:
                self._graph.set_entry_point("router")
            else:
                raise ValueError("No entry point defined and no router node found")

        # Add edges based on transitions
        self._add_edges()

        logger.info(
            f"Built workflow with {len(self._nodes)} nodes, "
            f"{len(self._transitions)} transitions"
        )

        return self

    def compile(self) -> CompiledStateGraph:
        """Compile the graph.

        Returns:
            Compiled graph ready for execution.

        Raises:
            ValueError: If graph not built yet.
        """
        if self._graph is None:
            raise ValueError("Graph not built. Call build() first.")

        self._compiled = self._graph.compile()
        return self._compiled

    async def invoke(
        self,
        state: MedicalAppointmentsState | dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke the workflow with state.

        Args:
            state: Initial or current state.
            config: Optional LangGraph config.

        Returns:
            Updated state after workflow execution.

        Raises:
            ValueError: If workflow not compiled.
        """
        if self._compiled is None:
            self.compile()

        if self._compiled is None:
            raise ValueError("Failed to compile workflow")

        return await self._compiled.ainvoke(state, config=config)

    # =========================================================================
    # Private Methods
    # =========================================================================

    def _instantiate_nodes(self) -> None:
        """Instantiate all nodes from configuration."""
        for instance in self._node_instances:
            node_def = instance.node_definition
            if not node_def:
                logger.warning(f"Node instance {instance.id} has no definition")
                continue

            node_key = node_def.node_key

            # Check if node is in registry
            if not self._registry.has(node_key):
                logger.warning(f"Unknown node type: {node_key}")
                continue

            # Merge configs: base -> definition defaults -> instance config
            merged_config = {
                **self._base_config,
                **(node_def.default_config or {}),
                **(instance.config or {}),
            }

            # Add routing rules to config if applicable
            merged_config["routing_rules"] = [
                r for r in self._routing_rules if r.is_active
            ]

            # Instantiate node
            try:
                node = self._registry.instantiate(
                    node_key=node_key,
                    medical_client=self._medical_client,
                    notification_service=self._notification_service,
                    config=merged_config,
                )
                self._nodes[instance.instance_key] = node
                logger.debug(f"Instantiated node: {instance.instance_key}")
            except Exception as e:
                logger.error(
                    f"Failed to instantiate node {instance.instance_key}: {e}"
                )

    def _get_entry_node(self) -> str | None:
        """Get the entry node key.

        Returns:
            Instance key of entry node or None.
        """
        # Check workflow definition
        if self._workflow_def.entry_node_id:
            entry_instance = self._instance_by_id.get(
                str(self._workflow_def.entry_node_id)
            )
            if entry_instance:
                return entry_instance.instance_key

        # Find node marked as entry point
        for instance in self._node_instances:
            if instance.is_entry_point:
                return instance.instance_key

        return None

    def _add_edges(self) -> None:
        """Add edges/transitions to the graph."""
        if self._graph is None:
            return

        # Group nodes by whether they have outgoing transitions
        nodes_with_transitions: set[str] = set()

        for transition in self._transitions:
            source_instance = self._instance_by_id.get(str(transition.source_node_id))
            target_instance = self._instance_by_id.get(str(transition.target_node_id))

            if not source_instance or not target_instance:
                logger.warning(
                    f"Invalid transition: source={transition.source_node_id}, "
                    f"target={transition.target_node_id}"
                )
                continue

            source_key = source_instance.instance_key
            target_key = target_instance.instance_key

            nodes_with_transitions.add(source_key)

            # Check if this source has conditional edges
            source_transitions = self._transitions_by_source.get(
                str(transition.source_node_id), []
            )

            has_conditions = any(t.condition for t in source_transitions)

            if has_conditions:
                # Add conditional edges
                self._add_conditional_edges(source_key, source_transitions)
            else:
                # Simple edge
                if target_key in self._nodes:
                    self._graph.add_edge(source_key, target_key)

        # Nodes without outgoing transitions go to END
        for instance_key in self._nodes:
            if instance_key not in nodes_with_transitions:
                self._graph.add_edge(instance_key, END)

    def _add_conditional_edges(
        self,
        source_key: str,
        transitions: list["WorkflowTransition"],
    ) -> None:
        """Add conditional edges from a source node.

        Args:
            source_key: Source node instance key.
            transitions: List of transitions from this source.
        """
        if self._graph is None:
            return

        # Build path map and routing function
        path_map: dict[str, str] = {}

        for transition in transitions:
            target_instance = self._instance_by_id.get(str(transition.target_node_id))
            if target_instance:
                path_map[target_instance.instance_key] = target_instance.instance_key

        # Add END as option
        path_map["__end__"] = END

        def get_next(state: MedicalAppointmentsState) -> str:
            """Determine next node based on conditions and state."""
            # First check routing rules
            for rule in self._routing_rules:
                if rule.is_active and rule.evaluate_condition(dict(state)):
                    action = rule.get_action()
                    action_type = action.get("type")

                    if action_type == "human_handoff":
                        # Find human_handoff node
                        for instance_key, node in self._nodes.items():
                            if "human_handoff" in instance_key:
                                return instance_key

                    elif action_type == "redirect":
                        target = action.get("target")
                        if target in self._nodes:
                            return target

            # Then check transition conditions
            for transition in transitions:
                if transition.evaluate_condition(dict(state)):
                    target_instance = self._instance_by_id.get(
                        str(transition.target_node_id)
                    )
                    if target_instance:
                        return target_instance.instance_key

            # Check for next_node in state
            next_node = state.get("next_node")
            if next_node and next_node in self._nodes:
                return str(next_node)

            # Check default transition
            for transition in transitions:
                if transition.is_default:
                    target_instance = self._instance_by_id.get(
                        str(transition.target_node_id)
                    )
                    if target_instance:
                        return target_instance.instance_key

            return "__end__"

        self._graph.add_conditional_edges(
            source_key,
            get_next,
            path_map,  # type: ignore[arg-type]
        )


class DefaultWorkflowEngine:
    """Factory for creating default workflow with hardcoded structure.

    Used when no custom workflow is configured for an institution.
    Maintains backward compatibility with existing behavior.
    """

    @staticmethod
    def create(
        medical_client: "IMedicalSystemClient",
        notification_service: "INotificationService | None" = None,
        config: dict[str, Any] | None = None,
        routing_rules: list["RoutingRule"] | None = None,
    ) -> StateGraph:
        """Create the default medical appointments workflow.

        This is the hardcoded workflow structure used before configurable
        workflows were introduced.

        Args:
            medical_client: Medical system client.
            notification_service: Optional notification service.
            config: Base configuration.
            routing_rules: Optional routing rules to apply.

        Returns:
            Configured StateGraph.
        """
        from .nodes import (
            AppointmentManagementNode,
            BookingConfirmationNode,
            DateSelectionNode,
            FallbackNode,
            GreetingNode,
            HumanHandoffNode,
            PatientIdentificationNode,
            PatientRegistrationNode,
            ProviderSelectionNode,
            RescheduleNode,
            RouterNode,
            SpecialtySelectionNode,
            TimeSelectionNode,
        )

        config = config or {}

        # Add routing rules to config
        if routing_rules:
            config["routing_rules"] = routing_rules

        # Instantiate nodes
        nodes = {
            "router": RouterNode(medical_client, notification_service, config),
            "greeting": GreetingNode(medical_client, notification_service, config),
            "patient_identification": PatientIdentificationNode(
                medical_client, notification_service, config
            ),
            "patient_registration": PatientRegistrationNode(
                medical_client, notification_service, config
            ),
            "specialty_selection": SpecialtySelectionNode(
                medical_client, notification_service, config
            ),
            "provider_selection": ProviderSelectionNode(
                medical_client, notification_service, config
            ),
            "date_selection": DateSelectionNode(
                medical_client, notification_service, config
            ),
            "time_selection": TimeSelectionNode(
                medical_client, notification_service, config
            ),
            "booking_confirmation": BookingConfirmationNode(
                medical_client, notification_service, config
            ),
            "appointment_management": AppointmentManagementNode(
                medical_client, notification_service, config
            ),
            "reschedule": RescheduleNode(medical_client, notification_service, config),
            "fallback": FallbackNode(medical_client, notification_service, config),
            "human_handoff": HumanHandoffNode(
                medical_client, notification_service, config
            ),
        }

        # Build graph
        workflow = StateGraph(MedicalAppointmentsState)

        # Add nodes
        for name, node in nodes.items():
            workflow.add_node(name, node)

        # Set entry point
        workflow.set_entry_point("router")

        # Build path map for conditional routing
        path_map = {name: name for name in nodes if name != "router"}
        path_map["__end__"] = END

        def get_next_node(state: MedicalAppointmentsState) -> str:
            """Determine next node from router."""
            # Check routing rules first
            if routing_rules:
                for rule in routing_rules:
                    if rule.is_active and rule.evaluate_condition(dict(state)):
                        action = rule.get_action()
                        if action.get("type") == "human_handoff":
                            return "human_handoff"
                        target = action.get("target")
                        if target and target in nodes:
                            return str(target)

            # Check state's next_node
            next_node = state.get("next_node")
            if next_node and str(next_node) in nodes:
                return str(next_node)

            return "__end__"

        # Conditional edges from router
        workflow.add_conditional_edges("router", get_next_node, path_map)

        # All other nodes go to END
        for name in nodes:
            if name != "router":
                workflow.add_edge(name, END)

        return workflow
