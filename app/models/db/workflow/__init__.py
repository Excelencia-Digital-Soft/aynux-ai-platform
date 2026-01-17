# ============================================================================
# SCOPE: WORKFLOW
# Description: SQLAlchemy models for configurable workflows.
#              Visual workflow builder with drag-and-drop editor support.
# Tenant-Aware: Yes - workflows are per-institution.
# ============================================================================
"""
Workflow models package - Configurable workflow builder.

This package contains all models for the visual workflow builder:
- NodeDefinition: Registry of available node types
- WorkflowDefinition: Workflow configurations per institution
- NodeInstance: Configured nodes within workflows
- WorkflowTransition: Transitions between nodes
- RoutingRule: Configurable routing rules (human handoff, etc.)
- ReminderSchedule: Reminder timing configuration
- MessageTemplate: Configurable message templates

Schema: workflow
"""

from .definitions import WorkflowDefinition
from .message_templates import MessageTemplate
from .node_definitions import NodeDefinition
from .node_instances import NodeInstance
from .reminder_schedules import ReminderSchedule
from .routing_rules import RoutingRule
from .transitions import WorkflowTransition

__all__ = [
    # Core workflow models
    "NodeDefinition",
    "WorkflowDefinition",
    "NodeInstance",
    "WorkflowTransition",
    # Routing and messaging
    "RoutingRule",
    "ReminderSchedule",
    "MessageTemplate",
]
