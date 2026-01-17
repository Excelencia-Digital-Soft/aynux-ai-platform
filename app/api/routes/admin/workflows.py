# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Admin API for workflow management.
#              CRUD operations for workflows, nodes, transitions, and rules.
# Tenant-Aware: Yes - via institution_config_id.
# ============================================================================
"""
Workflow Admin API - Manage configurable workflows.

Provides endpoints for:
- CRUD operations on workflow definitions
- Node instance management
- Transition management
- Routing rules configuration
- Vue Flow import/export

API Prefix: /api/v1/admin/workflows
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas.workflows import (
    NodeDefinitionListResponse,
    NodeDefinitionResponse,
    NodeInstanceCreate,
    NodeInstanceListResponse,
    NodeInstanceResponse,
    NodeInstanceUpdate,
    RoutingRuleCreate,
    RoutingRuleListResponse,
    RoutingRuleResponse,
    RoutingRuleUpdate,
    TransitionCreate,
    TransitionListResponse,
    TransitionResponse,
    TransitionUpdate,
    VueFlowExportResponse,
    VueFlowImportRequest,
    VueFlowImportResponse,
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowPublishResponse,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.database.async_db import get_async_db
from app.models.db.workflow import (
    NodeDefinition,
    NodeInstance,
    RoutingRule,
    WorkflowDefinition,
    WorkflowTransition,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workflows"])


# ============================================================================
# HELPERS
# ============================================================================


def _parse_uuid(value: str, field_name: str = "UUID") -> UUID:
    """Parse string to UUID with proper error handling."""
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: {e}",
        ) from e


def _workflow_to_response(workflow: WorkflowDefinition) -> WorkflowResponse:
    """Convert WorkflowDefinition to response schema."""
    return WorkflowResponse(
        id=str(workflow.id),
        institution_config_id=str(workflow.institution_config_id),
        workflow_key=workflow.workflow_key,
        workflow_type=workflow.workflow_type,
        display_name=workflow.display_name,
        description=workflow.description,
        version=workflow.version,
        entry_node_id=str(workflow.entry_node_id) if workflow.entry_node_id else None,
        settings=workflow.settings,
        canvas_state=workflow.canvas_state,
        is_active=workflow.is_active,
        is_draft=workflow.is_draft,
        published_at=workflow.published_at.isoformat() if workflow.published_at else None,
        created_at=workflow.created_at.isoformat() if workflow.created_at else None,
        updated_at=workflow.updated_at.isoformat() if workflow.updated_at else None,
        node_count=len(workflow.node_instances) if workflow.node_instances else 0,
    )


def _node_instance_to_response(node: NodeInstance) -> NodeInstanceResponse:
    """Convert NodeInstance to response schema."""
    return NodeInstanceResponse(
        id=str(node.id),
        workflow_id=str(node.workflow_id),
        node_definition_id=str(node.node_definition_id),
        instance_key=node.instance_key,
        display_label=node.display_label,
        config=node.config,
        position_x=node.position_x,
        position_y=node.position_y,
        is_entry_point=node.is_entry_point,
        node_key=node.node_definition.node_key if node.node_definition else None,
        node_type=node.node_definition.node_type if node.node_definition else None,
        display_name=node.node_definition.display_name if node.node_definition else None,
        icon=node.node_definition.icon if node.node_definition else None,
        color=node.node_definition.color if node.node_definition else None,
    )


def _transition_to_response(transition: WorkflowTransition) -> TransitionResponse:
    """Convert WorkflowTransition to response schema."""
    return TransitionResponse(
        id=str(transition.id),
        workflow_id=str(transition.workflow_id),
        source_node_id=str(transition.source_node_id),
        target_node_id=str(transition.target_node_id),
        transition_key=transition.transition_key,
        label=transition.label,
        condition=transition.condition,
        priority=transition.priority,
        is_default=transition.is_default,
        style=transition.style,
    )


def _routing_rule_to_response(rule: RoutingRule) -> RoutingRuleResponse:
    """Convert RoutingRule to response schema."""
    return RoutingRuleResponse(
        id=str(rule.id),
        institution_config_id=str(rule.institution_config_id),
        rule_key=rule.rule_key,
        rule_type=rule.rule_type,
        display_name=rule.display_name,
        description=rule.description,
        condition=rule.condition,
        action=rule.action,
        priority=rule.priority,
        is_active=rule.is_active,
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )


# ============================================================================
# NODE DEFINITION ENDPOINTS (Read-only catalog)
# IMPORTANT: These must be defined BEFORE /{workflow_id} routes to avoid
# FastAPI matching "/nodes/catalog" as a workflow_id parameter.
# ============================================================================


@router.get("/nodes/catalog", response_model=NodeDefinitionListResponse)
async def list_node_definitions(
    category: str | None = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only active nodes"),
    db: AsyncSession = Depends(get_async_db),
):
    """List all available node definitions (catalog)."""
    stmt = select(NodeDefinition)

    if category:
        stmt = stmt.where(NodeDefinition.category == category)
    if active_only:
        stmt = stmt.where(NodeDefinition.is_active == True)  # noqa: E712

    stmt = stmt.order_by(NodeDefinition.category, NodeDefinition.node_key)

    result = await db.execute(stmt)
    nodes = result.scalars().all()

    # Get unique categories
    categories = sorted({n.category for n in nodes})

    return NodeDefinitionListResponse(
        nodes=[
            NodeDefinitionResponse(
                id=str(n.id),
                node_key=n.node_key,
                node_type=n.node_type,
                python_class=n.python_class,
                python_module=n.python_module,
                display_name=n.display_name,
                description=n.description,
                icon=n.icon,
                color=n.color,
                category=n.category,
                config_schema=n.config_schema,
                default_config=n.default_config,
                inputs=n.inputs,
                outputs=n.outputs,
                is_builtin=n.is_builtin,
                is_active=n.is_active,
            )
            for n in nodes
        ],
        total=len(nodes),
        categories=categories,
    )


# ============================================================================
# ROUTING RULES ENDPOINTS
# IMPORTANT: These must be defined BEFORE /{workflow_id} routes
# ============================================================================


@router.get("/routing-rules", response_model=RoutingRuleListResponse)
async def list_routing_rules(
    institution_config_id: str = Query(..., description="Institution config UUID"),
    rule_type: str | None = Query(None, description="Filter by type"),
    active_only: bool = Query(False, description="Only active rules"),
    db: AsyncSession = Depends(get_async_db),
):
    """List routing rules for an institution."""
    inst_uuid = _parse_uuid(institution_config_id, "institution_config_id")

    stmt = select(RoutingRule).where(RoutingRule.institution_config_id == inst_uuid)

    if rule_type:
        stmt = stmt.where(RoutingRule.rule_type == rule_type)
    if active_only:
        stmt = stmt.where(RoutingRule.is_active == True)  # noqa: E712

    stmt = stmt.order_by(RoutingRule.priority)

    result = await db.execute(stmt)
    rules = result.scalars().all()

    return RoutingRuleListResponse(
        rules=[_routing_rule_to_response(r) for r in rules],
        total=len(rules),
    )


@router.post("/routing-rules", response_model=RoutingRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_routing_rule(
    data: RoutingRuleCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new routing rule."""
    inst_uuid = _parse_uuid(data.institution_config_id, "institution_config_id")

    rule = RoutingRule(
        institution_config_id=inst_uuid,
        rule_key=data.rule_key,
        rule_type=data.rule_type,
        display_name=data.display_name,
        description=data.description,
        condition=data.condition,
        action=data.action,
        priority=data.priority,
        is_active=data.is_active,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    logger.info(f"Created routing rule '{data.rule_key}' for institution {inst_uuid}")
    return _routing_rule_to_response(rule)


@router.put("/routing-rules/{rule_id}", response_model=RoutingRuleResponse)
async def update_routing_rule(
    rule_id: str,
    data: RoutingRuleUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update a routing rule."""
    rule_uuid = _parse_uuid(rule_id, "rule_id")

    stmt = select(RoutingRule).where(RoutingRule.id == rule_uuid)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routing rule not found: {rule_id}",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)

    logger.info(f"Updated routing rule {rule_id}")
    return _routing_rule_to_response(rule)


@router.delete("/routing-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routing_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a routing rule."""
    rule_uuid = _parse_uuid(rule_id, "rule_id")

    stmt = select(RoutingRule).where(RoutingRule.id == rule_uuid)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Routing rule not found: {rule_id}",
        )

    await db.delete(rule)
    await db.commit()

    logger.info(f"Deleted routing rule {rule_id}")


# ============================================================================
# WORKFLOW DEFINITION ENDPOINTS
# ============================================================================


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    institution_config_id: str = Query(..., description="Institution config UUID"),
    workflow_type: str | None = Query(None, description="Filter by type"),
    active_only: bool = Query(False, description="Only active workflows"),
    db: AsyncSession = Depends(get_async_db),
):
    """List all workflows for an institution."""
    inst_uuid = _parse_uuid(institution_config_id, "institution_config_id")

    stmt = (
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.node_instances))
        .where(WorkflowDefinition.institution_config_id == inst_uuid)
    )

    if workflow_type:
        stmt = stmt.where(WorkflowDefinition.workflow_type == workflow_type)
    if active_only:
        stmt = stmt.where(WorkflowDefinition.is_active == True)  # noqa: E712

    stmt = stmt.order_by(WorkflowDefinition.workflow_key)

    result = await db.execute(stmt)
    workflows = result.scalars().all()

    return WorkflowListResponse(
        workflows=[_workflow_to_response(w) for w in workflows],
        total=len(workflows),
    )


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new workflow definition."""
    inst_uuid = _parse_uuid(data.institution_config_id, "institution_config_id")

    # Check for duplicate workflow_key
    stmt = select(WorkflowDefinition).where(
        WorkflowDefinition.institution_config_id == inst_uuid,
        WorkflowDefinition.workflow_key == data.workflow_key,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow '{data.workflow_key}' already exists for this institution",
        )

    workflow = WorkflowDefinition(
        institution_config_id=inst_uuid,
        workflow_key=data.workflow_key,
        workflow_type=data.workflow_type,
        display_name=data.display_name,
        description=data.description,
        settings=data.settings,
        canvas_state=data.canvas_state,
    )

    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    logger.info(f"Created workflow '{data.workflow_key}' for institution {inst_uuid}")
    return _workflow_to_response(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a workflow by ID."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    stmt = (
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.node_instances))
        .where(WorkflowDefinition.id == wf_uuid)
    )
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    return _workflow_to_response(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update a workflow definition."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == wf_uuid)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    update_data = data.model_dump(exclude_unset=True)
    if "entry_node_id" in update_data and update_data["entry_node_id"]:
        update_data["entry_node_id"] = _parse_uuid(update_data["entry_node_id"], "entry_node_id")

    for key, value in update_data.items():
        setattr(workflow, key, value)

    await db.commit()
    await db.refresh(workflow)

    logger.info(f"Updated workflow {workflow_id}")
    return _workflow_to_response(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a workflow and all its nodes/transitions."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == wf_uuid)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    await db.delete(workflow)
    await db.commit()

    logger.info(f"Deleted workflow {workflow_id}")


@router.post("/{workflow_id}/publish", response_model=WorkflowPublishResponse)
async def publish_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Publish a workflow (mark as non-draft, increment version)."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == wf_uuid)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    workflow.is_draft = False
    workflow.version += 1
    workflow.published_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(workflow)

    logger.info(f"Published workflow {workflow_id} as version {workflow.version}")

    return WorkflowPublishResponse(
        success=True,
        workflow_id=str(workflow.id),
        version=workflow.version,
        published_at=workflow.published_at.isoformat(),
        message=f"Workflow published as version {workflow.version}",
    )


# ============================================================================
# NODE INSTANCE ENDPOINTS
# ============================================================================


@router.get("/{workflow_id}/nodes", response_model=NodeInstanceListResponse)
async def list_node_instances(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """List all node instances in a workflow."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    stmt = (
        select(NodeInstance)
        .options(selectinload(NodeInstance.node_definition))
        .where(NodeInstance.workflow_id == wf_uuid)
        .order_by(NodeInstance.instance_key)
    )

    result = await db.execute(stmt)
    nodes = result.scalars().all()

    return NodeInstanceListResponse(
        nodes=[_node_instance_to_response(n) for n in nodes],
        total=len(nodes),
    )


@router.post("/{workflow_id}/nodes", response_model=NodeInstanceResponse, status_code=status.HTTP_201_CREATED)
async def create_node_instance(
    workflow_id: str,
    data: NodeInstanceCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new node instance in a workflow."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")
    node_def_uuid = _parse_uuid(data.node_definition_id, "node_definition_id")

    # Verify workflow exists
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == wf_uuid)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    # Check for duplicate instance_key
    stmt = select(NodeInstance).where(
        NodeInstance.workflow_id == wf_uuid,
        NodeInstance.instance_key == data.instance_key,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Node '{data.instance_key}' already exists in this workflow",
        )

    node = NodeInstance(
        workflow_id=wf_uuid,
        node_definition_id=node_def_uuid,
        instance_key=data.instance_key,
        display_label=data.display_label,
        config=data.config,
        position_x=data.position_x,
        position_y=data.position_y,
        is_entry_point=data.is_entry_point,
    )

    db.add(node)
    await db.commit()

    # Refresh with relationship
    stmt = (
        select(NodeInstance)
        .options(selectinload(NodeInstance.node_definition))
        .where(NodeInstance.id == node.id)
    )
    result = await db.execute(stmt)
    node = result.scalar_one()

    logger.info(f"Created node instance '{data.instance_key}' in workflow {workflow_id}")
    return _node_instance_to_response(node)


@router.put("/{workflow_id}/nodes/{node_id}", response_model=NodeInstanceResponse)
async def update_node_instance(
    workflow_id: str,
    node_id: str,
    data: NodeInstanceUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update a node instance."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")
    node_uuid = _parse_uuid(node_id, "node_id")

    stmt = (
        select(NodeInstance)
        .options(selectinload(NodeInstance.node_definition))
        .where(NodeInstance.id == node_uuid, NodeInstance.workflow_id == wf_uuid)
    )
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node not found: {node_id} in workflow {workflow_id}",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(node, key, value)

    await db.commit()
    await db.refresh(node)

    logger.info(f"Updated node instance {node_id}")
    return _node_instance_to_response(node)


@router.delete("/{workflow_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node_instance(
    workflow_id: str,
    node_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a node instance."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")
    node_uuid = _parse_uuid(node_id, "node_id")

    stmt = select(NodeInstance).where(
        NodeInstance.id == node_uuid, NodeInstance.workflow_id == wf_uuid
    )
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node not found: {node_id} in workflow {workflow_id}",
        )

    await db.delete(node)
    await db.commit()

    logger.info(f"Deleted node instance {node_id}")


# ============================================================================
# TRANSITION ENDPOINTS
# ============================================================================


@router.get("/{workflow_id}/transitions", response_model=TransitionListResponse)
async def list_transitions(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """List all transitions in a workflow."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    stmt = (
        select(WorkflowTransition)
        .where(WorkflowTransition.workflow_id == wf_uuid)
        .order_by(WorkflowTransition.priority)
    )

    result = await db.execute(stmt)
    transitions = result.scalars().all()

    return TransitionListResponse(
        transitions=[_transition_to_response(t) for t in transitions],
        total=len(transitions),
    )


@router.post(
    "/{workflow_id}/transitions",
    response_model=TransitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transition(
    workflow_id: str,
    data: TransitionCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new transition in a workflow."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")
    source_uuid = _parse_uuid(data.source_node_id, "source_node_id")
    target_uuid = _parse_uuid(data.target_node_id, "target_node_id")

    transition = WorkflowTransition(
        workflow_id=wf_uuid,
        source_node_id=source_uuid,
        target_node_id=target_uuid,
        transition_key=data.transition_key,
        label=data.label,
        condition=data.condition,
        priority=data.priority,
        is_default=data.is_default,
        style=data.style,
    )

    db.add(transition)
    await db.commit()
    await db.refresh(transition)

    logger.info(f"Created transition in workflow {workflow_id}")
    return _transition_to_response(transition)


@router.put("/{workflow_id}/transitions/{transition_id}", response_model=TransitionResponse)
async def update_transition(
    workflow_id: str,
    transition_id: str,
    data: TransitionUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update a transition."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")
    trans_uuid = _parse_uuid(transition_id, "transition_id")

    stmt = select(WorkflowTransition).where(
        WorkflowTransition.id == trans_uuid, WorkflowTransition.workflow_id == wf_uuid
    )
    result = await db.execute(stmt)
    transition = result.scalar_one_or_none()

    if not transition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transition not found: {transition_id} in workflow {workflow_id}",
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(transition, key, value)

    await db.commit()
    await db.refresh(transition)

    logger.info(f"Updated transition {transition_id}")
    return _transition_to_response(transition)


@router.delete("/{workflow_id}/transitions/{transition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transition(
    workflow_id: str,
    transition_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a transition."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")
    trans_uuid = _parse_uuid(transition_id, "transition_id")

    stmt = select(WorkflowTransition).where(
        WorkflowTransition.id == trans_uuid, WorkflowTransition.workflow_id == wf_uuid
    )
    result = await db.execute(stmt)
    transition = result.scalar_one_or_none()

    if not transition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transition not found: {transition_id} in workflow {workflow_id}",
        )

    await db.delete(transition)
    await db.commit()

    logger.info(f"Deleted transition {transition_id}")


# ============================================================================
# VUE FLOW IMPORT/EXPORT
# ============================================================================


@router.get("/{workflow_id}/export", response_model=VueFlowExportResponse)
async def export_to_vue_flow(
    workflow_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Export workflow to Vue Flow format."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    # Get workflow with nodes and transitions
    stmt = (
        select(WorkflowDefinition)
        .options(
            selectinload(WorkflowDefinition.node_instances).selectinload(
                NodeInstance.node_definition
            ),
            selectinload(WorkflowDefinition.transitions),
        )
        .where(WorkflowDefinition.id == wf_uuid)
    )
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    # Convert to Vue Flow format
    nodes = [node.to_vue_flow_node() for node in workflow.node_instances]
    edges = [trans.to_vue_flow_edge() for trans in workflow.transitions]

    return VueFlowExportResponse(
        workflow_id=str(workflow.id),
        workflow_key=workflow.workflow_key,
        nodes=nodes,
        edges=edges,
        viewport=workflow.canvas_state.get("viewport"),
    )


@router.post("/{workflow_id}/import", response_model=VueFlowImportResponse)
async def import_from_vue_flow(
    workflow_id: str,
    data: VueFlowImportRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Import Vue Flow data into workflow."""
    wf_uuid = _parse_uuid(workflow_id, "workflow_id")

    # Verify workflow exists
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.id == wf_uuid)
    result = await db.execute(stmt)
    workflow = result.scalar_one_or_none()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow not found: {workflow_id}",
        )

    nodes_created = 0
    nodes_updated = 0
    transitions_created = 0
    transitions_updated = 0

    # Process nodes - update positions
    for vue_node in data.nodes:
        node_id = vue_node.get("id")
        if not node_id:
            continue

        try:
            node_uuid = UUID(node_id)
            stmt = select(NodeInstance).where(NodeInstance.id == node_uuid)
            result = await db.execute(stmt)
            node = result.scalar_one_or_none()

            if node:
                position = vue_node.get("position", {})
                node.position_x = position.get("x", node.position_x)
                node.position_y = position.get("y", node.position_y)
                nodes_updated += 1
        except ValueError:
            # Invalid UUID, skip
            continue

    # Update viewport in canvas_state
    if data.viewport:
        workflow.canvas_state["viewport"] = data.viewport

    await db.commit()

    return VueFlowImportResponse(
        success=True,
        workflow_id=str(workflow.id),
        nodes_created=nodes_created,
        nodes_updated=nodes_updated,
        transitions_created=transitions_created,
        transitions_updated=transitions_updated,
        message=f"Updated {nodes_updated} nodes",
    )
