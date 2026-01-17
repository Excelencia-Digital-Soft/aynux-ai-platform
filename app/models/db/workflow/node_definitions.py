# ============================================================================
# SCOPE: WORKFLOW
# Description: Registry of available node types for workflows.
#              Defines the catalog of reusable node definitions.
# Tenant-Aware: No - global catalog, nodes are instance per-tenant.
# ============================================================================
"""
NodeDefinition model - Registry of available workflow node types.

Stores metadata about each node type that can be used in workflows.
This is a global catalog - the actual node instances are per-workflow.

Usage:
    # Get node definition
    node_def = await session.get(NodeDefinition, node_key)

    # Instantiate node from definition
    node_class = registry.get(node_def.python_class)
    node = node_class(medical_client, notification_service, config)
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, TimestampMixin
from ..schemas import WORKFLOW_SCHEMA


class NodeDefinition(Base, TimestampMixin):
    """
    Registry of available node types.

    Global catalog of node types that can be instantiated in workflows.
    Each definition maps to a Python class that implements the node logic.

    Attributes:
        id: Unique identifier.
        node_key: Unique key for the node type (e.g., "greeting", "specialty_selection").
        node_type: Category of node (e.g., "conversation", "routing", "integration").
        python_class: Python class name (e.g., "GreetingNode").
        python_module: Python module path (e.g., "app.domains.medical_appointments.agents.nodes").
        display_name: Human-readable name for UI.
        description: Description of what the node does.
        icon: Icon identifier for UI (e.g., "pi-user", "pi-calendar").
        color: Color for UI rendering (e.g., "#3B82F6").
        category: UI grouping category (e.g., "conversation", "booking", "management").
        config_schema: JSON Schema for node configuration validation.
        default_config: Default configuration values.
        inputs: Expected input keys from state.
        outputs: Output keys this node produces.
        is_builtin: Whether this is a built-in system node.
        is_active: Whether this node type is available for use.
    """

    __tablename__ = "node_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique node definition identifier",
    )

    node_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique key for the node type (e.g., 'greeting', 'specialty_selection')",
    )

    node_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="conversation",
        index=True,
        comment="Category: conversation, routing, integration, management",
    )

    python_class: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Python class name implementing this node",
    )

    python_module: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Python module path containing the class",
    )

    # UI Metadata
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable name for display",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of what this node does",
    )

    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="pi-circle",
        comment="Icon identifier for UI (PrimeIcons)",
    )

    color: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default="#64748b",
        comment="Color hex code for UI rendering",
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",
        index=True,
        comment="UI grouping category",
    )

    # Configuration Schema
    config_schema: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON Schema for validating node configuration",
    )

    default_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Default configuration values",
    )

    # Input/Output Specification
    inputs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Expected input keys from state",
    )

    outputs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Output keys this node produces",
    )

    # Status Flags
    is_builtin: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="Whether this is a built-in system node",
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Whether this node type is available for use",
    )

    __table_args__ = (
        Index("idx_node_definitions_type_category", "node_type", "category"),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<NodeDefinition(key='{self.node_key}', class='{self.python_class}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "node_key": self.node_key,
            "node_type": self.node_type,
            "python_class": self.python_class,
            "python_module": self.python_module,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "category": self.category,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "is_builtin": self.is_builtin,
            "is_active": self.is_active,
        }
