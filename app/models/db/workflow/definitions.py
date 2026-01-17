# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Workflow definitions per institution.
#              Each institution can have custom workflows.
# Tenant-Aware: Yes - via institution_config_id FK.
# ============================================================================
"""
WorkflowDefinition model - Configurable workflows per institution.

Stores the workflow structure including nodes, transitions, and settings.
Each institution can have one or more workflows for different purposes.

Usage:
    # Get workflow for institution
    workflow = await session.execute(
        select(WorkflowDefinition).where(
            WorkflowDefinition.institution_config_id == config_id,
            WorkflowDefinition.workflow_type == "medical_appointments",
            WorkflowDefinition.is_active == True,
        )
    )
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA, WORKFLOW_SCHEMA

if TYPE_CHECKING:
    from ..tenancy import TenantInstitutionConfig

    from .node_instances import NodeInstance
    from .transitions import WorkflowTransition


class WorkflowDefinition(Base, TimestampMixin):
    """
    Workflow definition for an institution.

    Stores the complete workflow configuration including nodes,
    transitions, and visual editor state.

    Attributes:
        id: Unique identifier.
        institution_config_id: FK to tenant_institution_configs.
        workflow_key: Unique key within institution (e.g., "default", "vip_flow").
        workflow_type: Type of workflow (e.g., "medical_appointments", "reminders").
        display_name: Human-readable name.
        description: Description of the workflow.
        version: Workflow version for versioning.
        entry_node_id: Starting node for the workflow.
        settings: Workflow-level settings (JSONB).
        canvas_state: Vue Flow canvas state for editor.
        is_active: Whether this workflow is active.
        is_draft: Whether this is a draft version.
        published_at: When the workflow was last published.
    """

    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique workflow identifier",
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
        comment="Institution this workflow belongs to",
    )

    # Workflow identification
    workflow_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Unique key within institution (e.g., 'default', 'vip_flow')",
    )

    workflow_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medical_appointments",
        index=True,
        comment="Type: medical_appointments, reminders, custom",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable workflow name",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the workflow",
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Workflow version number",
    )

    # Entry point
    entry_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{WORKFLOW_SCHEMA}.node_instances.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_workflow_entry_node",
        ),
        nullable=True,
        comment="Starting node for the workflow",
    )

    # Configuration
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Workflow-level settings (interaction mode, NLU config, etc.)",
    )

    # Vue Flow canvas state (positions, zoom, viewport)
    canvas_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Vue Flow canvas state for visual editor",
    )

    # Status flags
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this workflow is active",
    )

    is_draft: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is a draft version",
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the workflow was last published",
    )

    # Relationships
    institution_config: Mapped["TenantInstitutionConfig"] = relationship(
        "TenantInstitutionConfig",
        foreign_keys=[institution_config_id],
    )

    node_instances: Mapped[list["NodeInstance"]] = relationship(
        "NodeInstance",
        back_populates="workflow",
        cascade="all, delete-orphan",
        foreign_keys="NodeInstance.workflow_id",
    )

    transitions: Mapped[list["WorkflowTransition"]] = relationship(
        "WorkflowTransition",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "institution_config_id",
            "workflow_key",
            name="uq_workflow_institution_key",
        ),
        Index("idx_workflow_definitions_institution", "institution_config_id"),
        Index("idx_workflow_definitions_type_active", "workflow_type", "is_active"),
        {"schema": WORKFLOW_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<WorkflowDefinition(key='{self.workflow_key}', type='{self.workflow_type}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "institution_config_id": str(self.institution_config_id),
            "workflow_key": self.workflow_key,
            "workflow_type": self.workflow_type,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "entry_node_id": str(self.entry_node_id) if self.entry_node_id else None,
            "settings": self.settings,
            "canvas_state": self.canvas_state,
            "is_active": self.is_active,
            "is_draft": self.is_draft,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for list views."""
        return {
            "id": str(self.id),
            "workflow_key": self.workflow_key,
            "workflow_type": self.workflow_type,
            "display_name": self.display_name,
            "version": self.version,
            "is_active": self.is_active,
            "is_draft": self.is_draft,
            "node_count": len(self.node_instances) if self.node_instances else 0,
        }
