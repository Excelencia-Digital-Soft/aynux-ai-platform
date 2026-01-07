"""
Pharmacy Node Factory

Factory for creating pharmacy node instances with dependencies.
Single responsibility: node instantiation with dependency injection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.clients.plex_client import PlexClient

logger = logging.getLogger(__name__)


# Node type constants (same as PharmacyNodeType in graph.py)
class NodeType:
    """Node type constants."""

    CUSTOMER_IDENTIFICATION = "customer_identification_node"
    CUSTOMER_REGISTRATION = "customer_registration_node"
    ROUTER = "pharmacy_router"
    DEBT_CHECK = "debt_check_node"
    CONFIRMATION = "confirmation_node"
    INVOICE = "invoice_generation_node"
    PAYMENT_LINK = "payment_link_node"


class PharmacyNodeFactory:
    """
    Factory for creating pharmacy node instances.

    Responsibility: Create and configure pharmacy domain nodes with dependencies.
    """

    def __init__(
        self,
        plex_client: PlexClient,
        config: dict[str, Any] | None = None,
    ):
        """
        Initialize the factory.

        Args:
            plex_client: The Plex API client
            config: Optional configuration dictionary
        """
        self.plex_client = plex_client
        self.config = config or {}
        self._node_config = self.config.get("node_config", {})
        self._registry = self._build_registry()

    def _build_registry(self) -> dict[str, tuple[type, str]]:
        """
        Build the node registry mapping node types to classes and config keys.

        Returns:
            Dictionary mapping node type to (class, config_key) tuples
        """
        from app.domains.pharmacy.agents.nodes import (
            ConfirmationNode,
            CustomerIdentificationNode,
            CustomerRegistrationNode,
            DebtCheckNode,
            InvoiceGenerationNode,
            PaymentLinkNode,
        )

        return {
            NodeType.CUSTOMER_IDENTIFICATION: (CustomerIdentificationNode, "customer_identification"),
            NodeType.CUSTOMER_REGISTRATION: (CustomerRegistrationNode, "customer_registration"),
            NodeType.DEBT_CHECK: (DebtCheckNode, "debt_check"),
            NodeType.CONFIRMATION: (ConfirmationNode, "confirmation"),
            NodeType.INVOICE: (InvoiceGenerationNode, "invoice"),
            NodeType.PAYMENT_LINK: (PaymentLinkNode, "payment_link"),
        }

    def create_nodes(
        self,
        enabled_nodes: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create all pharmacy domain nodes.

        Args:
            enabled_nodes: Optional list of node types to create.
                          If None, creates all nodes.

        Returns:
            Dictionary mapping node type to node instance
        """
        nodes: dict[str, Any] = {}
        types_to_create = enabled_nodes or list(self._registry.keys())

        for node_type in types_to_create:
            if node_type in self._registry:
                nodes[node_type] = self._create_node(node_type)
            else:
                logger.warning(f"Unknown node type: {node_type}")

        logger.info(f"Created {len(nodes)} pharmacy nodes: {list(nodes.keys())}")
        return nodes

    def _create_node(self, node_type: str) -> Any:
        """
        Create a single node instance.

        Args:
            node_type: The type of node to create

        Returns:
            Node instance
        """
        node_class, config_key = self._registry[node_type]
        node_config = self._node_config.get(config_key, {})

        return node_class(
            plex_client=self.plex_client,
            config=node_config,
        )

    def create_single_node(self, node_type: str) -> Any:
        """
        Create a single node by type.

        Args:
            node_type: The type of node to create

        Returns:
            Node instance

        Raises:
            KeyError: If node type is not in registry
        """
        if node_type not in self._registry:
            raise KeyError(f"Unknown node type: {node_type}")
        return self._create_node(node_type)

    def get_available_node_types(self) -> list[str]:
        """
        Get list of available node types.

        Returns:
            List of node type strings
        """
        return list(self._registry.keys())

    def is_node_type_available(self, node_type: str) -> bool:
        """
        Check if a node type is available in the registry.

        Args:
            node_type: The node type to check

        Returns:
            True if available
        """
        return node_type in self._registry
