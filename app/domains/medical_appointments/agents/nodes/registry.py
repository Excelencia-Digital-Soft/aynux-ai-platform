# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Registry of available node types for workflow builder.
# ============================================================================
"""Node Registry.

Singleton registry that maps node keys to their Python implementations.
Used by the workflow engine to instantiate nodes from database configuration.

Usage:
    # Get registry instance
    registry = NodeRegistry.get_instance()

    # Get node class
    node_class = registry.get_node_class("greeting")

    # Instantiate node
    node = registry.instantiate(
        node_key="greeting",
        medical_client=soap_client,
        notification_service=notification,
        config=node_config
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .appointment_management import AppointmentManagementNode
from .base import BaseNode
from .booking_confirmation import BookingConfirmationNode
from .date_selection import DateSelectionNode
from .fallback import FallbackNode
from .greeting import GreetingNode
from .human_handoff import HumanHandoffNode
from .patient_identification import PatientIdentificationNode
from .patient_registration import PatientRegistrationNode
from .provider_selection import ProviderSelectionNode
from .reschedule import RescheduleNode
from .router import RouterNode
from .specialty_selection import SpecialtySelectionNode
from .time_selection import TimeSelectionNode

if TYPE_CHECKING:
    from ...application.ports import IMedicalSystemClient, INotificationService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeDefinitionLocal:
    """Local node definition for registry.

    Contains metadata about a node type for local instantiation.
    This is a simplified version of the database NodeDefinition.
    """

    node_key: str
    node_class: type[BaseNode]
    node_type: str
    display_name: str
    description: str
    icon: str = "pi-circle"
    color: str = "#64748b"
    category: str = "general"


# Built-in node definitions
BUILTIN_NODES: list[NodeDefinitionLocal] = [
    NodeDefinitionLocal(
        node_key="router",
        node_class=RouterNode,
        node_type="routing",
        display_name="Router",
        description="Entry point - detects intent and routes to appropriate node",
        icon="pi-directions",
        color="#3B82F6",
        category="routing",
    ),
    NodeDefinitionLocal(
        node_key="greeting",
        node_class=GreetingNode,
        node_type="conversation",
        display_name="Greeting",
        description="Sends welcome message to the user",
        icon="pi-comments",
        color="#10B981",
        category="conversation",
    ),
    NodeDefinitionLocal(
        node_key="patient_identification",
        node_class=PatientIdentificationNode,
        node_type="conversation",
        display_name="Patient Identification",
        description="Requests and validates patient DNI",
        icon="pi-id-card",
        color="#8B5CF6",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="patient_registration",
        node_class=PatientRegistrationNode,
        node_type="conversation",
        display_name="Patient Registration",
        description="Registers a new patient in the system",
        icon="pi-user-plus",
        color="#F59E0B",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="specialty_selection",
        node_class=SpecialtySelectionNode,
        node_type="conversation",
        display_name="Specialty Selection",
        description="Shows available specialties for selection",
        icon="pi-heart",
        color="#EC4899",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="provider_selection",
        node_class=ProviderSelectionNode,
        node_type="conversation",
        display_name="Provider Selection",
        description="Shows available providers/doctors for selection",
        icon="pi-user",
        color="#14B8A6",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="date_selection",
        node_class=DateSelectionNode,
        node_type="conversation",
        display_name="Date Selection",
        description="Shows available dates for selection",
        icon="pi-calendar",
        color="#6366F1",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="time_selection",
        node_class=TimeSelectionNode,
        node_type="conversation",
        display_name="Time Selection",
        description="Shows available time slots for selection",
        icon="pi-clock",
        color="#0EA5E9",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="booking_confirmation",
        node_class=BookingConfirmationNode,
        node_type="conversation",
        display_name="Booking Confirmation",
        description="Shows summary and confirms the booking",
        icon="pi-check-circle",
        color="#22C55E",
        category="booking",
    ),
    NodeDefinitionLocal(
        node_key="appointment_management",
        node_class=AppointmentManagementNode,
        node_type="conversation",
        display_name="Appointment Management",
        description="View and manage existing appointments",
        icon="pi-list",
        color="#64748B",
        category="management",
    ),
    NodeDefinitionLocal(
        node_key="reschedule",
        node_class=RescheduleNode,
        node_type="conversation",
        display_name="Reschedule",
        description="Handles appointment rescheduling",
        icon="pi-calendar-times",
        color="#F97316",
        category="management",
    ),
    NodeDefinitionLocal(
        node_key="fallback",
        node_class=FallbackNode,
        node_type="routing",
        display_name="Fallback",
        description="Handles unrecognized inputs and error recovery",
        icon="pi-exclamation-triangle",
        color="#EF4444",
        category="routing",
    ),
    NodeDefinitionLocal(
        node_key="human_handoff",
        node_class=HumanHandoffNode,
        node_type="routing",
        display_name="Human Handoff",
        description="Transfers conversation to human agent",
        icon="pi-user-cog",
        color="#DC2626",
        category="routing",
    ),
]


class NodeRegistry:
    """Singleton registry of available node types.

    Maps node keys to their Python class implementations and provides
    methods for instantiating nodes with dependencies.
    """

    _instance: NodeRegistry | None = None

    def __init__(self) -> None:
        """Initialize registry with builtin nodes."""
        self._definitions: dict[str, NodeDefinitionLocal] = {}
        self._classes: dict[str, type[BaseNode]] = {}

        # Register builtin nodes
        for node_def in BUILTIN_NODES:
            self.register(node_def)

    @classmethod
    def get_instance(cls) -> NodeRegistry:
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = NodeRegistry()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def register(self, definition: NodeDefinitionLocal) -> None:
        """Register a node definition.

        Args:
            definition: Node definition to register.
        """
        self._definitions[definition.node_key] = definition
        self._classes[definition.node_key] = definition.node_class
        logger.debug(f"Registered node: {definition.node_key}")

    def register_class(
        self,
        node_key: str,
        node_class: type[BaseNode],
        display_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Register a node class directly.

        Args:
            node_key: Unique key for the node.
            node_class: Python class implementing the node.
            display_name: Optional display name.
            **kwargs: Additional definition fields.
        """
        definition = NodeDefinitionLocal(
            node_key=node_key,
            node_class=node_class,
            node_type=kwargs.get("node_type", "conversation"),
            display_name=display_name or node_key.replace("_", " ").title(),
            description=kwargs.get("description", ""),
            icon=kwargs.get("icon", "pi-circle"),
            color=kwargs.get("color", "#64748b"),
            category=kwargs.get("category", "general"),
        )
        self.register(definition)

    def get(self, node_key: str) -> NodeDefinitionLocal | None:
        """Get node definition by key.

        Args:
            node_key: Node key to look up.

        Returns:
            NodeDefinitionLocal or None if not found.
        """
        return self._definitions.get(node_key)

    def get_node_class(self, node_key: str) -> type[BaseNode] | None:
        """Get node class by key.

        Args:
            node_key: Node key to look up.

        Returns:
            Node class or None if not found.
        """
        return self._classes.get(node_key)

    def has(self, node_key: str) -> bool:
        """Check if node key is registered.

        Args:
            node_key: Node key to check.

        Returns:
            True if registered.
        """
        return node_key in self._classes

    def instantiate(
        self,
        node_key: str,
        medical_client: "IMedicalSystemClient",
        notification_service: "INotificationService | None" = None,
        config: dict[str, Any] | None = None,
    ) -> BaseNode:
        """Instantiate a node by key.

        Args:
            node_key: Node key to instantiate.
            medical_client: Medical system client (required).
            notification_service: Optional notification service.
            config: Optional node configuration.

        Returns:
            Instantiated node.

        Raises:
            KeyError: If node_key not found.
        """
        node_class = self._classes.get(node_key)
        if node_class is None:
            raise KeyError(f"Unknown node key: {node_key}")

        return node_class(
            medical_client=medical_client,
            notification_service=notification_service,
            config=config,
        )

    def list_all(self) -> list[NodeDefinitionLocal]:
        """List all registered node definitions.

        Returns:
            List of all definitions.
        """
        return list(self._definitions.values())

    def list_by_category(self, category: str) -> list[NodeDefinitionLocal]:
        """List node definitions by category.

        Args:
            category: Category to filter by.

        Returns:
            List of matching definitions.
        """
        return [d for d in self._definitions.values() if d.category == category]

    def list_by_type(self, node_type: str) -> list[NodeDefinitionLocal]:
        """List node definitions by type.

        Args:
            node_type: Type to filter by.

        Returns:
            List of matching definitions.
        """
        return [d for d in self._definitions.values() if d.node_type == node_type]

    @property
    def keys(self) -> list[str]:
        """Get all registered node keys."""
        return list(self._classes.keys())


def get_node_registry() -> NodeRegistry:
    """Get the global node registry instance.

    Convenience function for accessing the singleton.

    Returns:
        NodeRegistry instance.
    """
    return NodeRegistry.get_instance()
