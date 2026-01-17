"""Medical Appointments LangGraph Implementation.

LangGraph StateGraph for managing the medical appointment booking conversation flow.

IMPORTANT: This graph requires institution configuration to be provided.
All institution-specific text should come from the config or templates.

The graph supports two modes:
1. Default mode: Hardcoded workflow structure (backward compatible)
2. Configurable mode: Workflow loaded from database configuration

Usage:
    # Default mode
    graph = MedicalAppointmentsGraph(config=config, db_session=session)

    # Configurable mode (with workflow from database)
    graph = await MedicalAppointmentsGraph.from_config(
        institution_config_id=uuid,
        config=config,
        db_session=session,
    )
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..infrastructure.external import HCWebSOAPClient
from ..infrastructure.services import AppointmentNotificationService
from .nodes import (
    AppointmentManagementNode,
    BaseNode,
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
from .state import MedicalAppointmentsState, get_initial_state
from .workflow_engine import ConfigurableWorkflowEngine, DefaultWorkflowEngine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.db.workflow import RoutingRule

logger = logging.getLogger(__name__)

# Template directory for medical appointments
TEMPLATES_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "templates" / "medical_appointments"


class NodeType(str, Enum):
    """Nodos del grafo de turnos médicos."""

    ROUTER = "router"
    GREETING = "greeting"
    PATIENT_IDENTIFICATION = "patient_identification"
    PATIENT_REGISTRATION = "patient_registration"
    SPECIALTY_SELECTION = "specialty_selection"
    PROVIDER_SELECTION = "provider_selection"
    DATE_SELECTION = "date_selection"
    TIME_SELECTION = "time_selection"
    BOOKING_CONFIRMATION = "booking_confirmation"
    APPOINTMENT_MANAGEMENT = "appointment_management"
    RESCHEDULE = "reschedule"
    FALLBACK = "fallback"
    HUMAN_HANDOFF = "human_handoff"


class MedicalAppointmentsGraph:
    """LangGraph StateGraph para el flujo de turnos médicos.

    Manages the conversation flow for booking, confirming, and
    cancelling medical appointments.
    """

    def __init__(
        self,
        config: dict[str, Any],
        soap_client: HCWebSOAPClient | None = None,
        notification_service: AppointmentNotificationService | None = None,
        db_session: Any | None = None,
    ):
        """Inicializar grafo.

        Args:
            config: Configuration dictionary. REQUIRED - must contain:
                - institution: Institution key (e.g., "patologia_digestiva")
                - institution_name: Human-readable institution name
                - base_url or soap_url: API URL
                - did: WhatsApp Business DID (for notifications)
            soap_client: Optional pre-configured SOAP client.
            notification_service: Optional pre-configured notification service.
            db_session: Database session (required if notification_service is None).

        Raises:
            ValueError: If required config fields are missing.
        """
        if not config:
            raise ValueError("config is required for MedicalAppointmentsGraph")

        self.config = config
        self.institution = self.config.get("institution")
        self.institution_name = self.config.get("institution_name", "la institución")
        self.institution_id = self.config.get("institution_id", self.institution or "")
        self.did = self.config.get("did", "")

        if not self.institution:
            raise ValueError(
                "institution is required in config. "
                "Ensure bypass rule injects institution_config with institution key."
            )

        # External clients
        self._soap_client = soap_client
        self._soap_client_owned = soap_client is None

        # Notification service for WhatsApp interactive messages
        self._notification_service = notification_service
        self._notification_service_owned = notification_service is None
        self._db_session = db_session

        # Node instances (created lazily)
        self._nodes: dict[NodeType, BaseNode] = {}

        # Build graph
        self.graph = self._build_graph()
        self.app = None

    async def _get_soap_client(self) -> HCWebSOAPClient:
        """Get or create SOAP client."""
        if self._soap_client is None:
            soap_url = self.config.get("soap_url", "")
            self._soap_client = HCWebSOAPClient(
                base_url=soap_url,
                institution_id=self.institution_id,
            )
        return self._soap_client

    async def _get_notification_service(self) -> AppointmentNotificationService | None:
        """Get or create notification service.

        Returns None if no DID configured or no db session available.
        """
        if self._notification_service is None:
            if not self.did or not self._db_session:
                logger.debug(
                    "Notification service not available: " f"did={bool(self.did)}, db_session={bool(self._db_session)}"
                )
                return None
            self._notification_service = AppointmentNotificationService(
                db=self._db_session,
                did=self.did,
            )
        return self._notification_service

    async def _ensure_nodes_initialized(self) -> None:
        """Ensure all node instances are created with dependencies."""
        if self._nodes:
            return

        soap = await self._get_soap_client()
        notification = await self._get_notification_service()

        # Create node instances with dependencies
        self._nodes = {
            NodeType.ROUTER: RouterNode(soap, notification, self.config),
            NodeType.GREETING: GreetingNode(soap, notification, self.config),
            NodeType.PATIENT_IDENTIFICATION: PatientIdentificationNode(soap, notification, self.config),
            NodeType.PATIENT_REGISTRATION: PatientRegistrationNode(soap, notification, self.config),
            NodeType.SPECIALTY_SELECTION: SpecialtySelectionNode(soap, notification, self.config),
            NodeType.PROVIDER_SELECTION: ProviderSelectionNode(soap, notification, self.config),
            NodeType.DATE_SELECTION: DateSelectionNode(soap, notification, self.config),
            NodeType.TIME_SELECTION: TimeSelectionNode(soap, notification, self.config),
            NodeType.BOOKING_CONFIRMATION: BookingConfirmationNode(soap, notification, self.config),
            NodeType.APPOINTMENT_MANAGEMENT: AppointmentManagementNode(soap, notification, self.config),
            NodeType.RESCHEDULE: RescheduleNode(soap, notification, self.config),
            NodeType.FALLBACK: FallbackNode(soap, notification, self.config),
            NodeType.HUMAN_HANDOFF: HumanHandoffNode(soap, notification, self.config),
        }

    def _build_graph(self) -> StateGraph:
        """Construir el StateGraph de LangGraph.

        Note: Node functions are wrapped to ensure async initialization.
        """
        workflow = StateGraph(MedicalAppointmentsState)

        # Add nodes with wrapper functions that ensure initialization
        for node_type in NodeType:
            workflow.add_node(node_type, self._create_node_wrapper(node_type))

        # Set entry point
        workflow.set_entry_point(NodeType.ROUTER)

        # Conditional edges from router
        # Build path map with string keys for LangGraph compatibility
        path_map: dict[str, str] = {str(node): str(node) for node in NodeType if node != NodeType.ROUTER}
        path_map["__end__"] = END
        workflow.add_conditional_edges(
            NodeType.ROUTER,
            self._get_next_node,
            path_map,  # type: ignore[arg-type]
        )

        # All processing nodes go to END
        for node in NodeType:
            if node != NodeType.ROUTER:
                workflow.add_edge(node, END)

        return workflow

    def _create_node_wrapper(self, node_type: NodeType):
        """Create a wrapper function for a node that ensures initialization.

        Args:
            node_type: The type of node to wrap.

        Returns:
            Async function that processes the state.
        """

        async def node_wrapper(state: MedicalAppointmentsState) -> dict[str, Any]:
            await self._ensure_nodes_initialized()
            node = self._nodes[node_type]
            return await node(state)

        return node_wrapper

    def _get_next_node(self, state: MedicalAppointmentsState) -> str:
        """Determinar siguiente nodo basado en el estado."""
        next_node = state.get("next_node")
        if next_node:
            # Handle both string and NodeType values
            if isinstance(next_node, NodeType):
                return next_node.value
            return str(next_node)
        return "__end__"

    # ==================== LIFECYCLE ====================

    def initialize(self) -> None:
        """Compile the graph."""
        self.app = self.graph.compile()

    async def invoke(
        self,
        input_data: str | dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke the graph with input.

        Args:
            input_data: User message or state dictionary.
            config: Optional LangGraph config.

        Returns:
            Updated state dictionary.
        """
        from langchain_core.messages import HumanMessage

        if self.app is None:
            self.initialize()

        # Prepare initial state
        if isinstance(input_data, str):
            state = get_initial_state(institution=self.institution or "")
            state["messages"] = [HumanMessage(content=input_data)]
        else:
            state = input_data
            if "messages" not in state:
                state["messages"] = []

        # App should be initialized after initialize() call
        if self.app is None:
            raise RuntimeError("Graph not initialized")

        return await self.app.ainvoke(state, config=config)  # type: ignore[arg-type]

    async def close(self) -> None:
        """Cleanup resources."""
        if self._soap_client_owned and self._soap_client:
            await self._soap_client.close()
            self._soap_client = None

        if self._notification_service_owned and self._notification_service:
            await self._notification_service.close()
            self._notification_service = None

        # Clear node instances
        self._nodes.clear()

    # ==================== FACTORY METHODS ====================

    @classmethod
    async def from_config(
        cls,
        institution_config_id: UUID,
        config: dict[str, Any],
        db_session: "AsyncSession",
        soap_client: HCWebSOAPClient | None = None,
        notification_service: AppointmentNotificationService | None = None,
    ) -> "MedicalAppointmentsGraph":
        """Create graph from database workflow configuration.

        Loads workflow configuration from database and builds graph accordingly.
        Falls back to default workflow if no custom workflow is configured.

        Args:
            institution_config_id: Institution configuration UUID.
            config: Base configuration dictionary.
            db_session: Database session.
            soap_client: Optional pre-configured SOAP client.
            notification_service: Optional pre-configured notification service.

        Returns:
            MedicalAppointmentsGraph instance.
        """
        from ..application.services import WorkflowService

        # Create instance with default workflow first
        instance = cls(
            config=config,
            soap_client=soap_client,
            notification_service=notification_service,
            db_session=db_session,
        )

        # Try to load custom workflow from database
        service = WorkflowService(db_session)
        workflow_config = await service.get_workflow_config(institution_config_id)

        if workflow_config:
            logger.info(
                f"Loading custom workflow: {workflow_config.workflow.workflow_key} "
                f"for institution {institution_config_id}"
            )

            # Get dependencies
            soap = await instance._get_soap_client()
            notification = await instance._get_notification_service()

            # Build configurable workflow engine
            engine = ConfigurableWorkflowEngine(
                workflow_def=workflow_config.workflow,
                node_instances=workflow_config.node_instances,
                transitions=workflow_config.transitions,
                routing_rules=workflow_config.routing_rules,
                medical_client=soap,
                notification_service=notification,
                base_config=config,
            )

            # Build and compile
            engine.build()
            instance.graph = engine._graph  # type: ignore[assignment]
            instance.app = engine.compile()

            # Store engine reference for cleanup
            instance._workflow_engine = engine  # type: ignore[attr-defined]
        else:
            logger.info(
                f"No custom workflow found for institution {institution_config_id}, "
                "using default workflow"
            )
            # Check if routing rules exist to apply to default workflow
            routing_rules = await service.get_routing_rules(institution_config_id)
            if routing_rules:
                instance._routing_rules = routing_rules  # type: ignore[attr-defined]
                # Rebuild with routing rules
                instance.graph = instance._build_graph_with_routing_rules(routing_rules)

        return instance

    def _build_graph_with_routing_rules(
        self,
        routing_rules: list["RoutingRule"],
    ) -> StateGraph:
        """Build default graph with routing rules applied.

        Args:
            routing_rules: List of routing rules to apply.

        Returns:
            StateGraph with routing rules integrated.
        """
        # Use DefaultWorkflowEngine which handles routing rules
        # This will be compiled later by initialize()
        return DefaultWorkflowEngine.create(
            medical_client=self._soap_client,  # type: ignore[arg-type]
            notification_service=self._notification_service,
            config=self.config,
            routing_rules=routing_rules,
        )


class ConfigurableMedicalAppointmentsGraph:
    """Wrapper for ConfigurableWorkflowEngine with graph-like interface.

    Provides the same interface as MedicalAppointmentsGraph but uses
    a fully configurable workflow engine underneath.

    Usage:
        config = await workflow_service.get_workflow_config(institution_config_id)
        graph = ConfigurableMedicalAppointmentsGraph(
            workflow_config=config,
            base_config=base_config,
            db_session=session,
        )
        graph.initialize()
        result = await graph.invoke(state)
    """

    def __init__(
        self,
        workflow_config: Any,  # WorkflowConfig
        base_config: dict[str, Any],
        db_session: "AsyncSession",
        soap_client: HCWebSOAPClient | None = None,
        notification_service: AppointmentNotificationService | None = None,
    ) -> None:
        """Initialize configurable graph.

        Args:
            workflow_config: WorkflowConfig from WorkflowService.
            base_config: Base configuration dictionary.
            db_session: Database session.
            soap_client: Optional pre-configured SOAP client.
            notification_service: Optional pre-configured notification service.
        """
        self.workflow_config = workflow_config
        self.base_config = base_config
        self._db_session = db_session

        self.institution = base_config.get("institution")
        self.institution_name = base_config.get("institution_name", "la institución")
        self.institution_id = base_config.get("institution_id", self.institution or "")
        self.did = base_config.get("did", "")

        # External clients
        self._soap_client = soap_client
        self._soap_client_owned = soap_client is None
        self._notification_service = notification_service
        self._notification_service_owned = notification_service is None

        # Engine and compiled graph
        self._engine: ConfigurableWorkflowEngine | None = None
        self.app: CompiledStateGraph | None = None

    async def _get_soap_client(self) -> HCWebSOAPClient:
        """Get or create SOAP client."""
        if self._soap_client is None:
            soap_url = self.base_config.get("soap_url", "")
            self._soap_client = HCWebSOAPClient(
                base_url=soap_url,
                institution_id=self.institution_id,
            )
        return self._soap_client

    async def _get_notification_service(self) -> AppointmentNotificationService | None:
        """Get or create notification service."""
        if self._notification_service is None:
            if not self.did or not self._db_session:
                return None
            self._notification_service = AppointmentNotificationService(
                db=self._db_session,
                did=self.did,
            )
        return self._notification_service

    async def initialize(self) -> None:
        """Build and compile the workflow engine."""
        soap = await self._get_soap_client()
        notification = await self._get_notification_service()

        self._engine = ConfigurableWorkflowEngine(
            workflow_def=self.workflow_config.workflow,
            node_instances=self.workflow_config.node_instances,
            transitions=self.workflow_config.transitions,
            routing_rules=self.workflow_config.routing_rules,
            medical_client=soap,
            notification_service=notification,
            base_config=self.base_config,
        )

        self._engine.build()
        self.app = self._engine.compile()

    async def invoke(
        self,
        input_data: str | dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke the workflow with input.

        Args:
            input_data: User message or state dictionary.
            config: Optional LangGraph config.

        Returns:
            Updated state dictionary.
        """
        from langchain_core.messages import HumanMessage

        if self.app is None:
            await self.initialize()

        # Prepare initial state
        if isinstance(input_data, str):
            state = get_initial_state(institution=self.institution or "")
            state["messages"] = [HumanMessage(content=input_data)]
        else:
            state = input_data
            if "messages" not in state:
                state["messages"] = []

        if self.app is None:
            raise RuntimeError("Workflow not initialized")

        return await self.app.ainvoke(state, config=config)  # type: ignore[arg-type]

    async def close(self) -> None:
        """Cleanup resources."""
        if self._soap_client_owned and self._soap_client:
            await self._soap_client.close()
            self._soap_client = None

        if self._notification_service_owned and self._notification_service:
            await self._notification_service.close()
            self._notification_service = None
