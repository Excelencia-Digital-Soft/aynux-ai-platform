# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Transitions between workflow nodes.
#              Defines the edges/connections in the workflow graph.
# Tenant-Aware: Yes - via workflow_id → institution_config_id.
# ============================================================================
"""
WorkflowTransition model - Transitions between nodes.

Defines the connections/edges between nodes in a workflow,
including optional conditions for conditional branching.

Usage:
    # Get all transitions for a workflow
    transitions = await session.execute(
        select(WorkflowTransition).where(
            WorkflowTransition.workflow_id == workflow_id
        ).order_by(WorkflowTransition.priority)
    )
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import WORKFLOW_SCHEMA

if TYPE_CHECKING:
    from .definitions import WorkflowDefinition
    from .node_instances import NodeInstance


class WorkflowTransition(Base, TimestampMixin):
    """
    Transition between workflow nodes.

    Represents an edge in the workflow graph with optional
    conditions for conditional branching.

    Attributes:
        id: Unique identifier.
        workflow_id: FK to workflow_definitions.
        source_node_id: FK to source node_instances.
        target_node_id: FK to target node_instances.
        transition_key: Optional key for identification.
        label: Display label for the transition.
        condition: JSON condition for conditional transitions.
        priority: Order for evaluating multiple transitions.
        is_default: Whether this is the default transition.
        style: Visual style for Vue Flow edge.
    """

    __tablename__ = "workflow_transitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique transition identifier",
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
        comment="Workflow this transition belongs to",
    )

    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{WORKFLOW_SCHEMA}.node_instances.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
        comment="Source node for this transition",
    )

    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{WORKFLOW_SCHEMA}.node_instances.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
        comment="Target node for this transition",
    )

    # Transition identification
    transition_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional key for identification",
    )

    label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Display label for the transition",
    )

    # Conditional logic
    condition: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="JSON condition for conditional transitions",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Order for evaluating multiple transitions (lower = first)",
    )

    is_default: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Whether this is the default transition if no conditions match",
    )

    # Visual styling
    style: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Visual style for Vue Flow edge (animated, color, etc.)",
    )

    # Relationships
    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition",
        back_populates="transitions",
    )

    source_node: Mapped["NodeInstance"] = relationship(
        "NodeInstance",
        foreign_keys=[source_node_id],
    )

    target_node: Mapped["NodeInstance"] = relationship(
        "NodeInstance",
        foreign_keys=[target_node_id],
    )

    __table_args__ = (
        Index("idx_workflow_transitions_workflow", "workflow_id"),
        Index("idx_workflow_transitions_source", "source_node_id"),
        Index("idx_workflow_transitions_target", "target_node_id"),
        Index(
            "idx_workflow_transitions_workflow_priority",
            "workflow_id",
            "source_node_id",
            "priority",
        ),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<WorkflowTransition(source='{self.source_node_id}', target='{self.target_node_id}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "workflow_id": str(self.workflow_id),
            "source_node_id": str(self.source_node_id),
            "target_node_id": str(self.target_node_id),
            "transition_key": self.transition_key,
            "label": self.label,
            "condition": self.condition,
            "priority": self.priority,
            "is_default": self.is_default,
            "style": self.style,
        }

    def to_vue_flow_edge(self) -> dict[str, Any]:
        """Convert to Vue Flow edge format."""
        edge: dict[str, Any] = {
            "id": str(self.id),
            "source": str(self.source_node_id),
            "target": str(self.target_node_id),
            "type": "smoothstep",
        }

        if self.label:
            edge["label"] = self.label

        if self.style:
            edge["style"] = self.style
            if self.style.get("animated"):
                edge["animated"] = True

        return edge

    def evaluate_condition(self, state: dict[str, Any]) -> bool:
        """Evaluate the transition condition against state.

        Args:
            state: Current workflow state.

        Returns:
            True if condition is met or no condition exists.
        """
        if not self.condition:
            return True

        condition_type = self.condition.get("type")

        if condition_type == "equals":
            field = self.condition.get("field", "")
            value = self.condition.get("value")
            return state.get(field) == value

        elif condition_type == "not_equals":
            field = self.condition.get("field", "")
            value = self.condition.get("value")
            return state.get(field) != value

        elif condition_type == "in":
            field = self.condition.get("field", "")
            values = self.condition.get("values", [])
            return state.get(field) in values

        elif condition_type == "not_in":
            field = self.condition.get("field", "")
            values = self.condition.get("values", [])
            return state.get(field) not in values

        elif condition_type == "exists":
            field = self.condition.get("field", "")
            return field in state and state[field] is not None

        elif condition_type == "not_exists":
            field = self.condition.get("field", "")
            return field not in state or state[field] is None

        elif condition_type == "and":
            conditions = self.condition.get("conditions", [])
            for cond in conditions:
                temp_transition = WorkflowTransition(condition=cond)
                if not temp_transition.evaluate_condition(state):
                    return False
            return True

        elif condition_type == "or":
            conditions = self.condition.get("conditions", [])
            for cond in conditions:
                temp_transition = WorkflowTransition(condition=cond)
                if temp_transition.evaluate_condition(state):
                    return True
            return False

        # Default: no condition or unknown type = allow
        return True
