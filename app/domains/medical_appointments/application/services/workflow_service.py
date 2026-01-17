# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Service for loading and managing workflow configuration.
# ============================================================================
"""Workflow Service.

Handles loading workflow configuration from database and provides
data to the ConfigurableWorkflowEngine.

Usage:
    service = WorkflowService(db_session)

    # Get active workflow for institution
    workflow = await service.get_active_workflow(institution_config_id)

    # Get complete workflow configuration
    config = await service.get_workflow_config(institution_config_id)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.db.workflow import (
        MessageTemplate,
        NodeInstance,
        ReminderSchedule,
        RoutingRule,
        WorkflowDefinition,
        WorkflowTransition,
    )

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """Complete workflow configuration for an institution.

    Contains all necessary data to build a ConfigurableWorkflowEngine.
    """

    workflow: "WorkflowDefinition"
    node_instances: list["NodeInstance"]
    transitions: list["WorkflowTransition"]
    routing_rules: list["RoutingRule"]
    reminder_schedules: list["ReminderSchedule"]
    message_templates: dict[str, "MessageTemplate"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow": self.workflow.to_dict(),
            "node_instances": [n.to_dict() for n in self.node_instances],
            "transitions": [t.to_dict() for t in self.transitions],
            "routing_rules": [r.to_dict() for r in self.routing_rules],
            "reminder_schedules": [s.to_dict() for s in self.reminder_schedules],
            "message_templates": {
                k: t.to_dict() for k, t in self.message_templates.items()
            },
        }


class WorkflowService:
    """Service for loading workflow configuration from database.

    Provides methods to retrieve complete workflow configuration
    including nodes, transitions, routing rules, and templates.
    """

    def __init__(self, db_session: "AsyncSession") -> None:
        """Initialize service.

        Args:
            db_session: SQLAlchemy async session.
        """
        self._session = db_session

    async def get_active_workflow(
        self,
        institution_config_id: UUID,
        workflow_type: str = "medical_appointments",
    ) -> "WorkflowDefinition | None":
        """Get active workflow for an institution.

        Args:
            institution_config_id: Institution configuration UUID.
            workflow_type: Type of workflow to retrieve.

        Returns:
            WorkflowDefinition or None if not found.
        """
        from app.models.db.workflow import WorkflowDefinition

        stmt = (
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.institution_config_id == institution_config_id,
                WorkflowDefinition.workflow_type == workflow_type,
                WorkflowDefinition.is_active == True,  # noqa: E712
                WorkflowDefinition.is_draft == False,  # noqa: E712
            )
            .order_by(WorkflowDefinition.version.desc())
            .limit(1)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_workflow_by_key(
        self,
        institution_config_id: UUID,
        workflow_key: str,
    ) -> "WorkflowDefinition | None":
        """Get workflow by key for an institution.

        Args:
            institution_config_id: Institution configuration UUID.
            workflow_key: Workflow key (e.g., 'default', 'vip_flow').

        Returns:
            WorkflowDefinition or None if not found.
        """
        from app.models.db.workflow import WorkflowDefinition

        stmt = select(WorkflowDefinition).where(
            WorkflowDefinition.institution_config_id == institution_config_id,
            WorkflowDefinition.workflow_key == workflow_key,
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_node_instances(
        self,
        workflow_id: UUID,
    ) -> list["NodeInstance"]:
        """Get all node instances for a workflow.

        Args:
            workflow_id: Workflow definition UUID.

        Returns:
            List of NodeInstance objects with node_definition loaded.
        """
        from app.models.db.workflow import NodeInstance

        stmt = (
            select(NodeInstance)
            .where(NodeInstance.workflow_id == workflow_id)
            .options(selectinload(NodeInstance.node_definition))
            .order_by(NodeInstance.created_at)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_transitions(
        self,
        workflow_id: UUID,
    ) -> list["WorkflowTransition"]:
        """Get all transitions for a workflow.

        Args:
            workflow_id: Workflow definition UUID.

        Returns:
            List of WorkflowTransition objects.
        """
        from app.models.db.workflow import WorkflowTransition

        stmt = (
            select(WorkflowTransition)
            .where(WorkflowTransition.workflow_id == workflow_id)
            .order_by(WorkflowTransition.priority)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_routing_rules(
        self,
        institution_config_id: UUID,
        active_only: bool = True,
    ) -> list["RoutingRule"]:
        """Get routing rules for an institution.

        Args:
            institution_config_id: Institution configuration UUID.
            active_only: Only return active rules.

        Returns:
            List of RoutingRule objects.
        """
        from app.models.db.workflow import RoutingRule

        stmt = select(RoutingRule).where(
            RoutingRule.institution_config_id == institution_config_id
        )

        if active_only:
            stmt = stmt.where(RoutingRule.is_active == True)  # noqa: E712

        stmt = stmt.order_by(RoutingRule.priority)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_reminder_schedules(
        self,
        institution_config_id: UUID,
        active_only: bool = True,
    ) -> list["ReminderSchedule"]:
        """Get reminder schedules for an institution.

        Args:
            institution_config_id: Institution configuration UUID.
            active_only: Only return active schedules.

        Returns:
            List of ReminderSchedule objects.
        """
        from app.models.db.workflow import ReminderSchedule

        stmt = select(ReminderSchedule).where(
            ReminderSchedule.institution_config_id == institution_config_id
        )

        if active_only:
            stmt = stmt.where(ReminderSchedule.is_active == True)  # noqa: E712

        stmt = stmt.order_by(ReminderSchedule.priority)

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_message_templates(
        self,
        institution_config_id: UUID | None = None,
        template_type: str | None = None,
    ) -> dict[str, "MessageTemplate"]:
        """Get message templates, including global templates.

        Args:
            institution_config_id: Institution configuration UUID (optional).
            template_type: Filter by template type (optional).

        Returns:
            Dictionary mapping template_key to MessageTemplate.
        """
        from sqlalchemy import or_

        from app.models.db.workflow import MessageTemplate

        # Get global templates + institution-specific templates
        conditions = [MessageTemplate.is_active == True]  # noqa: E712

        if institution_config_id:
            conditions.append(
                or_(
                    MessageTemplate.institution_config_id == institution_config_id,
                    MessageTemplate.institution_config_id.is_(None),  # Global templates
                )
            )
        else:
            conditions.append(MessageTemplate.institution_config_id.is_(None))

        if template_type:
            conditions.append(MessageTemplate.template_type == template_type)

        stmt = select(MessageTemplate).where(*conditions)

        result = await self._session.execute(stmt)
        templates = result.scalars().all()

        # Build dictionary, institution-specific templates override global
        template_dict: dict[str, MessageTemplate] = {}
        for template in templates:
            key = template.template_key
            # Institution-specific takes precedence over global
            if key not in template_dict or template.institution_config_id is not None:
                template_dict[key] = template

        return template_dict

    async def get_workflow_config(
        self,
        institution_config_id: UUID,
        workflow_type: str = "medical_appointments",
    ) -> WorkflowConfig | None:
        """Get complete workflow configuration for an institution.

        Loads all necessary data to build a ConfigurableWorkflowEngine.

        Args:
            institution_config_id: Institution configuration UUID.
            workflow_type: Type of workflow to retrieve.

        Returns:
            WorkflowConfig or None if no workflow found.
        """
        # Get active workflow
        workflow = await self.get_active_workflow(
            institution_config_id, workflow_type
        )

        if not workflow:
            logger.debug(
                f"No active workflow found for institution {institution_config_id}"
            )
            return None

        # Load all related data
        node_instances = await self.get_node_instances(workflow.id)
        transitions = await self.get_transitions(workflow.id)
        routing_rules = await self.get_routing_rules(institution_config_id)
        reminder_schedules = await self.get_reminder_schedules(institution_config_id)
        message_templates = await self.get_message_templates(institution_config_id)

        logger.info(
            f"Loaded workflow config: workflow={workflow.workflow_key}, "
            f"nodes={len(node_instances)}, transitions={len(transitions)}, "
            f"rules={len(routing_rules)}"
        )

        return WorkflowConfig(
            workflow=workflow,
            node_instances=node_instances,
            transitions=transitions,
            routing_rules=routing_rules,
            reminder_schedules=reminder_schedules,
            message_templates=message_templates,
        )

    async def has_custom_workflow(
        self,
        institution_config_id: UUID,
        workflow_type: str = "medical_appointments",
    ) -> bool:
        """Check if institution has a custom workflow configured.

        Args:
            institution_config_id: Institution configuration UUID.
            workflow_type: Type of workflow to check.

        Returns:
            True if custom workflow exists.
        """
        workflow = await self.get_active_workflow(
            institution_config_id, workflow_type
        )
        return workflow is not None

    async def list_workflows(
        self,
        institution_config_id: UUID,
    ) -> list["WorkflowDefinition"]:
        """List all workflows for an institution.

        Args:
            institution_config_id: Institution configuration UUID.

        Returns:
            List of WorkflowDefinition objects.
        """
        from app.models.db.workflow import WorkflowDefinition

        stmt = (
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.institution_config_id == institution_config_id
            )
            .order_by(WorkflowDefinition.workflow_type, WorkflowDefinition.workflow_key)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
