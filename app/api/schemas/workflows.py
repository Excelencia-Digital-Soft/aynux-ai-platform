# ============================================================================
# SCOPE: ADMIN API
# Description: Pydantic schemas for workflow management API.
# ============================================================================
"""
Workflow API Schemas.

Pydantic models for workflow management endpoints including:
- Workflow definitions
- Node instances
- Transitions
- Routing rules
- Reminder schedules
- Message templates
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Workflow Definition Schemas
# ============================================================================


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow definition."""

    institution_config_id: str = Field(..., description="Institution config UUID")
    workflow_key: str = Field(..., description="Unique key within institution")
    workflow_type: str = Field(default="medical_appointments", description="Workflow type")
    display_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(default=None, description="Description")
    settings: dict[str, Any] = Field(default_factory=dict, description="Workflow settings")
    canvas_state: dict[str, Any] = Field(default_factory=dict, description="Vue Flow canvas state")


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow definition."""

    display_name: str | None = None
    description: str | None = None
    settings: dict[str, Any] | None = None
    canvas_state: dict[str, Any] | None = None
    is_active: bool | None = None
    is_draft: bool | None = None
    entry_node_id: str | None = None


class WorkflowResponse(BaseModel):
    """Schema for workflow API response."""

    id: str
    institution_config_id: str
    workflow_key: str
    workflow_type: str
    display_name: str
    description: str | None
    version: int
    entry_node_id: str | None
    settings: dict[str, Any]
    canvas_state: dict[str, Any]
    is_active: bool
    is_draft: bool
    published_at: str | None
    created_at: str | None
    updated_at: str | None
    node_count: int | None = None


class WorkflowListResponse(BaseModel):
    """Schema for listing workflows."""

    workflows: list[WorkflowResponse]
    total: int


class WorkflowPublishResponse(BaseModel):
    """Schema for publish workflow response."""

    success: bool
    workflow_id: str
    version: int
    published_at: str
    message: str


# ============================================================================
# Node Definition Schemas (Read-only catalog)
# ============================================================================


class NodeDefinitionResponse(BaseModel):
    """Schema for node definition API response."""

    id: str
    node_key: str
    node_type: str
    python_class: str
    python_module: str
    display_name: str
    description: str | None
    icon: str | None
    color: str | None
    category: str
    config_schema: dict[str, Any] | None
    default_config: dict[str, Any]
    inputs: list[str]
    outputs: list[str]
    is_builtin: bool
    is_active: bool


class NodeDefinitionListResponse(BaseModel):
    """Schema for listing node definitions."""

    nodes: list[NodeDefinitionResponse]
    total: int
    categories: list[str]


# ============================================================================
# Node Instance Schemas
# ============================================================================


class NodeInstanceCreate(BaseModel):
    """Schema for creating a node instance."""

    workflow_id: str = Field(..., description="Workflow UUID")
    node_definition_id: str = Field(..., description="Node definition UUID")
    instance_key: str = Field(..., description="Unique key within workflow")
    display_label: str | None = Field(default=None, description="Custom label")
    config: dict[str, Any] = Field(default_factory=dict, description="Instance config")
    position_x: float = Field(default=0.0, description="X position")
    position_y: float = Field(default=0.0, description="Y position")
    is_entry_point: bool = Field(default=False, description="Is entry point")


class NodeInstanceUpdate(BaseModel):
    """Schema for updating a node instance."""

    display_label: str | None = None
    config: dict[str, Any] | None = None
    position_x: float | None = None
    position_y: float | None = None
    is_entry_point: bool | None = None


class NodeInstanceResponse(BaseModel):
    """Schema for node instance API response."""

    id: str
    workflow_id: str
    node_definition_id: str
    instance_key: str
    display_label: str | None
    config: dict[str, Any]
    position_x: float
    position_y: float
    is_entry_point: bool
    # From node definition
    node_key: str | None
    node_type: str | None
    display_name: str | None
    icon: str | None
    color: str | None


class NodeInstanceListResponse(BaseModel):
    """Schema for listing node instances."""

    nodes: list[NodeInstanceResponse]
    total: int


# ============================================================================
# Transition Schemas
# ============================================================================


class TransitionCreate(BaseModel):
    """Schema for creating a workflow transition."""

    workflow_id: str = Field(..., description="Workflow UUID")
    source_node_id: str = Field(..., description="Source node instance UUID")
    target_node_id: str = Field(..., description="Target node instance UUID")
    transition_key: str | None = Field(default=None, description="Optional key")
    label: str | None = Field(default=None, description="Display label")
    condition: dict[str, Any] | None = Field(default=None, description="JSON condition")
    priority: int = Field(default=0, description="Evaluation priority")
    is_default: bool = Field(default=False, description="Is default transition")
    style: dict[str, Any] = Field(default_factory=dict, description="Visual style")


class TransitionUpdate(BaseModel):
    """Schema for updating a transition."""

    transition_key: str | None = None
    label: str | None = None
    condition: dict[str, Any] | None = None
    priority: int | None = None
    is_default: bool | None = None
    style: dict[str, Any] | None = None


class TransitionResponse(BaseModel):
    """Schema for transition API response."""

    id: str
    workflow_id: str
    source_node_id: str
    target_node_id: str
    transition_key: str | None
    label: str | None
    condition: dict[str, Any] | None
    priority: int
    is_default: bool
    style: dict[str, Any]


class TransitionListResponse(BaseModel):
    """Schema for listing transitions."""

    transitions: list[TransitionResponse]
    total: int


# ============================================================================
# Routing Rule Schemas
# ============================================================================


class RoutingRuleCreate(BaseModel):
    """Schema for creating a routing rule."""

    institution_config_id: str = Field(..., description="Institution config UUID")
    rule_key: str = Field(..., description="Unique key within institution")
    rule_type: str = Field(default="human_handoff", description="Rule type")
    display_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(default=None, description="Description")
    condition: dict[str, Any] = Field(default_factory=dict, description="JSON condition")
    action: dict[str, Any] = Field(default_factory=dict, description="JSON action")
    priority: int = Field(default=100, description="Evaluation priority")
    is_active: bool = Field(default=True, description="Is active")


class RoutingRuleUpdate(BaseModel):
    """Schema for updating a routing rule."""

    display_name: str | None = None
    description: str | None = None
    condition: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    priority: int | None = None
    is_active: bool | None = None


class RoutingRuleResponse(BaseModel):
    """Schema for routing rule API response."""

    id: str
    institution_config_id: str
    rule_key: str
    rule_type: str
    display_name: str
    description: str | None
    condition: dict[str, Any]
    action: dict[str, Any]
    priority: int
    is_active: bool
    created_at: str | None
    updated_at: str | None


class RoutingRuleListResponse(BaseModel):
    """Schema for listing routing rules."""

    rules: list[RoutingRuleResponse]
    total: int


# ============================================================================
# Reminder Schedule Schemas
# ============================================================================


class ReminderScheduleCreate(BaseModel):
    """Schema for creating a reminder schedule."""

    institution_config_id: str = Field(..., description="Institution config UUID")
    schedule_key: str = Field(..., description="Unique key within institution")
    display_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(default=None, description="Description")
    trigger_type: str = Field(default="days_before", description="Trigger type")
    trigger_value: int = Field(default=1, description="Trigger value")
    execution_hour: int = Field(default=9, ge=0, le=23, description="Hour to send")
    timezone: str = Field(default="America/Argentina/San_Juan", description="Timezone")
    message_template_id: str | None = Field(default=None, description="Template UUID")
    fallback_message: str | None = Field(default=None, description="Fallback message")
    buttons: list[dict[str, str]] = Field(default_factory=list, description="Buttons")
    is_active: bool = Field(default=True, description="Is active")


class ReminderScheduleUpdate(BaseModel):
    """Schema for updating a reminder schedule."""

    display_name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    trigger_value: int | None = None
    execution_hour: int | None = None
    timezone: str | None = None
    message_template_id: str | None = None
    fallback_message: str | None = None
    buttons: list[dict[str, str]] | None = None
    is_active: bool | None = None


class ReminderScheduleResponse(BaseModel):
    """Schema for reminder schedule API response."""

    id: str
    institution_config_id: str
    schedule_key: str
    display_name: str
    description: str | None
    trigger_type: str
    trigger_value: int
    execution_hour: int
    timezone: str
    message_template_id: str | None
    fallback_message: str | None
    buttons: list[dict[str, str]]
    is_active: bool
    created_at: str | None
    updated_at: str | None


class ReminderScheduleListResponse(BaseModel):
    """Schema for listing reminder schedules."""

    schedules: list[ReminderScheduleResponse]
    total: int


# ============================================================================
# Message Template Schemas
# ============================================================================


class MessageTemplateCreate(BaseModel):
    """Schema for creating a message template."""

    institution_config_id: str | None = Field(
        default=None, description="Institution UUID (null for global)"
    )
    template_key: str = Field(..., description="Unique template key")
    template_type: str = Field(default="general", description="Template type")
    display_name: str = Field(..., description="Human-readable name")
    description: str | None = Field(default=None, description="Description")
    content: str = Field(..., description="Message content with {placeholders}")
    content_html: str | None = Field(default=None, description="HTML version")
    buttons: list[dict[str, str]] = Field(default_factory=list, description="Buttons")
    placeholders: list[str] = Field(default_factory=list, description="Placeholders")
    language: str = Field(default="es", description="Language code")
    is_active: bool = Field(default=True, description="Is active")


class MessageTemplateUpdate(BaseModel):
    """Schema for updating a message template."""

    display_name: str | None = None
    description: str | None = None
    content: str | None = None
    content_html: str | None = None
    buttons: list[dict[str, str]] | None = None
    placeholders: list[str] | None = None
    language: str | None = None
    is_active: bool | None = None


class MessageTemplateResponse(BaseModel):
    """Schema for message template API response."""

    id: str
    institution_config_id: str | None
    template_key: str
    template_type: str
    display_name: str
    description: str | None
    content: str
    content_html: str | None
    buttons: list[dict[str, str]]
    placeholders: list[str]
    language: str
    is_active: bool
    is_global: bool
    created_at: str | None
    updated_at: str | None


class MessageTemplateListResponse(BaseModel):
    """Schema for listing message templates."""

    templates: list[MessageTemplateResponse]
    total: int


# ============================================================================
# Vue Flow Export Schemas
# ============================================================================


class VueFlowExportRequest(BaseModel):
    """Schema for exporting workflow to Vue Flow format."""

    workflow_id: str = Field(..., description="Workflow UUID")


class VueFlowNode(BaseModel):
    """Vue Flow node format."""

    id: str
    type: str
    position: dict[str, float]
    data: dict[str, Any]


class VueFlowEdge(BaseModel):
    """Vue Flow edge format."""

    id: str
    source: str
    target: str
    type: str = "smoothstep"
    label: str | None = None
    animated: bool = False
    style: dict[str, Any] | None = None


class VueFlowExportResponse(BaseModel):
    """Schema for Vue Flow export response."""

    workflow_id: str
    workflow_key: str
    nodes: list[VueFlowNode]
    edges: list[VueFlowEdge]
    viewport: dict[str, Any] | None = None


class VueFlowImportRequest(BaseModel):
    """Schema for importing Vue Flow data into workflow."""

    workflow_id: str = Field(..., description="Workflow UUID")
    nodes: list[dict[str, Any]] = Field(..., description="Vue Flow nodes")
    edges: list[dict[str, Any]] = Field(..., description="Vue Flow edges")
    viewport: dict[str, Any] | None = Field(default=None, description="Viewport state")


class VueFlowImportResponse(BaseModel):
    """Schema for Vue Flow import response."""

    success: bool
    workflow_id: str
    nodes_created: int
    nodes_updated: int
    transitions_created: int
    transitions_updated: int
    message: str
