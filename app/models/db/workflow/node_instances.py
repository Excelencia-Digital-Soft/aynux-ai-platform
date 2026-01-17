# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Node instances within workflows.
#              Each instance is a configured node in a specific workflow.
# Tenant-Aware: Yes - via workflow_id → institution_config_id.
# ============================================================================
"""
NodeInstance model - Configured node instances within workflows.

Each instance represents a node in a specific workflow with its configuration
and visual position in the editor.

Usage:
    # Get all nodes in a workflow
    nodes = await session.execute(
        select(NodeInstance).where(NodeInstance.workflow_id == workflow_id)
    )
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import WORKFLOW_SCHEMA

if TYPE_CHECKING:
    from .definitions import WorkflowDefinition
    from .node_definitions import NodeDefinition


class NodeInstance(Base, TimestampMixin):
    """
    Node instance within a workflow.

    Represents a configured instance of a node definition
    within a specific workflow.

    Attributes:
        id: Unique identifier.
        workflow_id: FK to workflow_definitions.
        node_definition_id: FK to node_definitions.
        instance_key: Unique key within workflow (e.g., "greeting_1").
        display_label: Custom label for this instance.
        config: Instance-specific configuration (JSONB).
        position_x: X position in Vue Flow canvas.
        position_y: Y position in Vue Flow canvas.
        is_entry_point: Whether this is the workflow entry point.
    """

    __tablename__ = "node_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique node instance identifier",
    )

    # Foreign keys
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{WORKFLOW_SCHEMA}.workflow_definitions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
        comment="Workflow this node belongs to",
    )

    node_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{WORKFLOW_SCHEMA}.node_definitions.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
        comment="Node definition this instance is based on",
    )

    # Instance identification
    instance_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique key within workflow (e.g., 'greeting_1')",
    )

    display_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Custom display label for this instance",
    )

    # Configuration
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Instance-specific configuration overrides",
    )

    # Visual Editor Position
    position_x: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="X position in Vue Flow canvas",
    )

    position_y: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Y position in Vue Flow canvas",
    )

    # Status
    is_entry_point: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Whether this is the workflow entry point",
    )

    # Relationships
    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition",
        back_populates="node_instances",
        foreign_keys=[workflow_id],
    )

    node_definition: Mapped["NodeDefinition"] = relationship(
        "NodeDefinition",
        foreign_keys=[node_definition_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "instance_key",
            name="uq_node_instance_workflow_key",
        ),
        Index("idx_node_instances_workflow", "workflow_id"),
        Index("idx_node_instances_definition", "node_definition_id"),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<NodeInstance(key='{self.instance_key}', workflow='{self.workflow_id}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "node_definition_id": str(self.node_definition_id),
            "instance_key": self.instance_key,
            "display_label": self.display_label,
            "config": self.config,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "is_entry_point": self.is_entry_point,
            # Include node definition info
            "node_key": self.node_definition.node_key if self.node_definition else None,
            "node_type": self.node_definition.node_type if self.node_definition else None,
            "display_name": self.node_definition.display_name if self.node_definition else None,
            "icon": self.node_definition.icon if self.node_definition else None,
            "color": self.node_definition.color if self.node_definition else None,
        }

    def to_vue_flow_node(self) -> dict[str, Any]:
        """Convert to Vue Flow node format."""
        return {
            "id": str(self.id),
            "type": self.node_definition.node_type if self.node_definition else "default",
            "position": {
                "x": self.position_x,
                "y": self.position_y,
            },
            "data": {
                "instance_key": self.instance_key,
                "label": self.display_label or (
                    self.node_definition.display_name if self.node_definition else self.instance_key
                ),
                "node_key": self.node_definition.node_key if self.node_definition else None,
                "icon": self.node_definition.icon if self.node_definition else None,
                "color": self.node_definition.color if self.node_definition else None,
                "config": self.config,
                "is_entry_point": self.is_entry_point,
            },
        }
