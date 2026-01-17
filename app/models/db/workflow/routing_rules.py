# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Routing rules for workflow decisions.
#              Configurable rules for human handoff, escalation, etc.
# Tenant-Aware: Yes - via institution_config_id FK.
# ============================================================================
"""
RoutingRule model - Configurable routing rules per institution.

Defines rules for routing decisions like human handoff, escalation,
or special handling based on conditions.

Usage:
    # Get routing rules for institution
    rules = await session.execute(
        select(RoutingRule).where(
            RoutingRule.institution_config_id == config_id,
            RoutingRule.is_active == True,
        ).order_by(RoutingRule.priority)
    )
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA, WORKFLOW_SCHEMA

if TYPE_CHECKING:
    from ..tenancy import TenantInstitutionConfig


class RoutingRule(Base, TimestampMixin):
    """
    Routing rule for workflow decisions.

    Defines conditions and actions for routing decisions
    such as human handoff for specific specialties.

    Attributes:
        id: Unique identifier.
        institution_config_id: FK to tenant_institution_configs.
        rule_key: Unique key within institution.
        rule_type: Type of rule (human_handoff, escalation, redirect, etc.).
        display_name: Human-readable name.
        description: Description of the rule.
        condition: JSON condition to evaluate.
        action: JSON action to take when condition is met.
        priority: Order for rule evaluation.
        is_active: Whether the rule is active.
    """

    __tablename__ = "routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique routing rule identifier",
    )

    # Foreign key to institution
    institution_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{CORE_SCHEMA}.tenant_institution_configs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
        comment="Institution this rule belongs to",
    )

    # Rule identification
    rule_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique key within institution",
    )

    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="human_handoff",
        index=True,
        comment="Type: human_handoff, escalation, redirect, skip_node, etc.",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable rule name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of what this rule does",
    )

    # Condition and Action
    condition: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON condition to evaluate (e.g., specialty == 'FONOAUDIOLOGIA')",
    )

    action: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="JSON action to take (e.g., {type: 'human_handoff', message: '...'})",
    )

    # Priority for ordering
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        comment="Order for rule evaluation (lower = first)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this rule is active",
    )

    # Relationships
    institution_config: Mapped["TenantInstitutionConfig"] = relationship(
        "TenantInstitutionConfig",
        foreign_keys=[institution_config_id],
    )

    __table_args__ = (
        Index("idx_routing_rules_institution", "institution_config_id"),
        Index("idx_routing_rules_type_active", "rule_type", "is_active"),
        Index(
            "idx_routing_rules_institution_priority",
            "institution_config_id",
            "priority",
        ),
        # GIN index for JSONB queries
        Index(
            "idx_routing_rules_condition_gin",
            "condition",
            postgresql_using="gin",
        ),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<RoutingRule(key='{self.rule_key}', type='{self.rule_type}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "institution_config_id": str(self.institution_config_id),
            "rule_key": self.rule_key,
            "rule_type": self.rule_type,
            "display_name": self.display_name,
            "description": self.description,
            "condition": self.condition,
            "action": self.action,
            "priority": self.priority,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def evaluate_condition(self, state: dict[str, Any]) -> bool:
        """Evaluate the rule condition against state.

        Args:
            state: Current workflow state.

        Returns:
            True if condition is met.
        """
        if not self.condition:
            return False

        condition_type = self.condition.get("type")

        if condition_type == "specialty_equals":
            # Check if selected specialty matches
            specialty = state.get("selected_specialty") or state.get("specialty_name")
            target = self.condition.get("value", "")
            if not specialty or not target:
                return False
            return str(specialty).upper() == str(target).upper()

        elif condition_type == "specialty_in":
            # Check if selected specialty is in list
            specialty = state.get("selected_specialty") or state.get("specialty_name")
            targets = self.condition.get("values", [])
            if not specialty:
                return False
            return str(specialty).upper() in [str(t).upper() for t in targets]

        elif condition_type == "error_count_exceeds":
            # Check if error count exceeds threshold
            error_count = state.get("error_count", 0)
            threshold = self.condition.get("threshold", 3)
            return bool(error_count > threshold)

        elif condition_type == "intent_equals":
            # Check detected intent
            intent = state.get("detected_intent")
            target = self.condition.get("value")
            return intent == target

        elif condition_type == "field_equals":
            # Generic field equality check
            field = self.condition.get("field", "")
            value = self.condition.get("value")
            return state.get(field) == value

        elif condition_type == "field_in":
            # Generic field in list check
            field = self.condition.get("field", "")
            values = self.condition.get("values", [])
            return state.get(field) in values

        elif condition_type == "always":
            # Always match (catch-all)
            return True

        # Unknown condition type
        return False

    def get_action(self) -> dict[str, Any]:
        """Get the action to execute.

        Returns:
            Action configuration dict.
        """
        return self.action or {}
