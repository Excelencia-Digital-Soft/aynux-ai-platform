# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Admin API para configurar bypass routing rules por organización.
#              Todas las rutas requieren org_id en path + require_admin().
# Tenant-Aware: Yes - todas las operaciones filtran por organization_id.
# ============================================================================
"""
Bypass Rules Admin API - Manage bypass routing rules per organization.

Provides CRUD endpoints for configuring bypass routing rules that allow
direct routing to agents based on phone number patterns or WhatsApp IDs.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_organization_by_id, require_admin
from app.core.schemas.bypass_rule import (
    BypassRuleCreate,
    BypassRuleListResponse,
    BypassRuleResponse,
    BypassRuleTestRequest,
    BypassRuleTestResponse,
    BypassRuleUpdate,
)
from app.database.async_db import get_async_db
from app.models.db.tenancy import BypassRule, Organization, OrganizationUser, TenantConfig

router = APIRouter(tags=["Bypass Rules"])

# Type aliases for common dependencies
OrgIdPath = Annotated[uuid.UUID, Path(description="Organization ID")]
RuleIdPath = Annotated[uuid.UUID, Path(description="Rule ID")]
AdminMembership = Annotated[OrganizationUser, Depends(require_admin)]
OrgDep = Annotated[Organization, Depends(get_organization_by_id)]
DbSession = Annotated[AsyncSession, Depends(get_async_db)]


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/bypass-rules", response_model=BypassRuleListResponse)
async def list_bypass_rules(
    org_id: OrgIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    List all bypass routing rules for the organization.

    Rules are returned ordered by priority (highest first).
    Requires admin or owner role.
    """
    stmt = (
        select(BypassRule)
        .where(BypassRule.organization_id == org_id)
        .order_by(desc(BypassRule.priority), BypassRule.rule_name)
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    rules_list = [BypassRuleResponse(**r.to_dict()) for r in rules]
    enabled_count = sum(1 for r in rules if bool(r.enabled))

    return BypassRuleListResponse(
        rules=rules_list,
        total=len(rules_list),
        enabled_count=enabled_count,
        disabled_count=len(rules_list) - enabled_count,
    )


@router.post("/{org_id}/bypass-rules", response_model=BypassRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_bypass_rule(
    data: BypassRuleCreate,
    org_id: OrgIdPath,
    membership: AdminMembership,
    org: OrgDep,
    db: DbSession,
):
    """
    Create a new bypass routing rule.

    Rule types:
    - phone_number: Pattern matching with wildcard support (e.g., "549264*")
    - phone_number_list: Exact match against a list of numbers
    - whatsapp_phone_number_id: Match WhatsApp Business phone number ID

    Requires admin or owner role.
    """
    # Check if rule_name already exists for this org
    stmt = select(BypassRule).where(
        BypassRule.organization_id == org_id,
        BypassRule.rule_name == data.rule_name,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule name '{data.rule_name}' already exists",
        )

    # Create the rule
    rule = BypassRule(
        id=uuid.uuid4(),
        organization_id=org_id,
        rule_name=data.rule_name,
        description=data.description,
        rule_type=data.rule_type,
        pattern=data.pattern,
        phone_numbers=data.phone_numbers,
        phone_number_id=data.phone_number_id,
        target_agent=data.target_agent,
        target_domain=data.target_domain,
        priority=data.priority,
        enabled=data.enabled,
        isolated_history=data.isolated_history if data.isolated_history else None,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return BypassRuleResponse(**rule.to_dict())


@router.get("/{org_id}/bypass-rules/{rule_id}", response_model=BypassRuleResponse)
async def get_bypass_rule(
    org_id: OrgIdPath,
    rule_id: RuleIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    Get a specific bypass routing rule.

    Requires admin or owner role.
    """
    stmt = select(BypassRule).where(
        BypassRule.organization_id == org_id,
        BypassRule.id == rule_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bypass rule not found",
        )

    return BypassRuleResponse(**rule.to_dict())


@router.put("/{org_id}/bypass-rules/{rule_id}", response_model=BypassRuleResponse)
async def update_bypass_rule(
    data: BypassRuleUpdate,
    org_id: OrgIdPath,
    rule_id: RuleIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    Update a bypass routing rule.

    Requires admin or owner role.
    """
    stmt = select(BypassRule).where(
        BypassRule.organization_id == org_id,
        BypassRule.id == rule_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bypass rule not found",
        )

    # Check for duplicate rule_name if changing it
    if data.rule_name is not None and data.rule_name != rule.rule_name:
        stmt = select(BypassRule).where(
            BypassRule.organization_id == org_id,
            BypassRule.rule_name == data.rule_name,
            BypassRule.id != rule_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rule name '{data.rule_name}' already exists",
            )
        rule.rule_name = data.rule_name

    # Update other fields if provided
    if data.description is not None:
        rule.description = data.description
    if data.pattern is not None:
        rule.pattern = data.pattern
    if data.phone_numbers is not None:
        rule.phone_numbers = data.phone_numbers
    if data.phone_number_id is not None:
        rule.phone_number_id = data.phone_number_id
    if data.target_agent is not None:
        rule.target_agent = data.target_agent
    if data.target_domain is not None:
        rule.target_domain = data.target_domain
    if data.priority is not None:
        rule.priority = data.priority
    if data.enabled is not None:
        rule.enabled = data.enabled
    if data.isolated_history is not None:
        rule.isolated_history = data.isolated_history

    rule.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(rule)

    return BypassRuleResponse(**rule.to_dict())


@router.post("/{org_id}/bypass-rules/{rule_id}/toggle", response_model=BypassRuleResponse)
async def toggle_bypass_rule(
    org_id: OrgIdPath,
    rule_id: RuleIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    Toggle a bypass rule's enabled status.

    Requires admin or owner role.
    """
    stmt = select(BypassRule).where(
        BypassRule.organization_id == org_id,
        BypassRule.id == rule_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bypass rule not found",
        )

    rule.enabled = not bool(rule.enabled)
    rule.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(rule)

    return BypassRuleResponse(**rule.to_dict())


@router.delete("/{org_id}/bypass-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bypass_rule(
    org_id: OrgIdPath,
    rule_id: RuleIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    Delete a bypass routing rule.

    Requires admin or owner role.
    """
    stmt = select(BypassRule).where(
        BypassRule.organization_id == org_id,
        BypassRule.id == rule_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bypass rule not found",
        )

    await db.delete(rule)
    await db.commit()


@router.post("/{org_id}/bypass-rules/test", response_model=BypassRuleTestResponse)
async def test_bypass_routing(
    data: BypassRuleTestRequest,
    org_id: OrgIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    Test bypass routing for a given phone number.

    Simulates the bypass routing evaluation and returns which rule
    (if any) would match and what agent/domain would be used.

    Requires admin or owner role.
    """
    # Get all enabled rules for this org, ordered by priority
    stmt = (
        select(BypassRule)
        .where(BypassRule.organization_id == org_id)
        .order_by(desc(BypassRule.priority), BypassRule.rule_name)
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    evaluation_order: list[str] = [str(r.rule_name) for r in rules]

    # Get tenant config for default domain
    config_stmt = select(TenantConfig).where(TenantConfig.organization_id == org_id)
    config_result = await db.execute(config_stmt)
    tenant_config = config_result.scalar_one_or_none()
    default_domain = tenant_config.default_domain if tenant_config else "excelencia"

    # Evaluate rules
    for rule in rules:
        if rule.matches(data.wa_id, data.whatsapp_phone_number_id):
            target_domain = str(rule.target_domain) if rule.target_domain else default_domain
            return BypassRuleTestResponse(
                matched=True,
                matched_rule=BypassRuleResponse(**rule.to_dict()),
                target_agent=str(rule.target_agent),
                target_domain=target_domain,
                evaluation_order=evaluation_order,
            )

    # No match
    return BypassRuleTestResponse(
        matched=False,
        matched_rule=None,
        target_agent=None,
        target_domain=None,
        evaluation_order=evaluation_order,
    )


@router.post("/{org_id}/bypass-rules/reorder", response_model=BypassRuleListResponse)
async def reorder_bypass_rules(
    rule_priorities: dict[str, int],
    org_id: OrgIdPath,
    membership: AdminMembership,
    db: DbSession,
):
    """
    Reorder bypass rules by updating their priorities.

    Accepts a dictionary mapping rule IDs to new priority values.

    Example:
    ```json
    {
        "rule-id-1": 100,
        "rule-id-2": 50,
        "rule-id-3": 0
    }
    ```

    Requires admin or owner role.
    """
    # Get all rules for this org
    stmt = select(BypassRule).where(BypassRule.organization_id == org_id)
    result = await db.execute(stmt)
    rules = {str(r.id): r for r in result.scalars().all()}

    # Update priorities
    for rule_id, priority in rule_priorities.items():
        if rule_id in rules:
            rules[rule_id].priority = priority
            rules[rule_id].updated_at = datetime.now(UTC)

    await db.commit()

    # Return updated list
    stmt = (
        select(BypassRule)
        .where(BypassRule.organization_id == org_id)
        .order_by(desc(BypassRule.priority), BypassRule.rule_name)
    )
    result = await db.execute(stmt)
    updated_rules = result.scalars().all()

    rules_list = [BypassRuleResponse(**r.to_dict()) for r in updated_rules]
    enabled_count = sum(1 for r in updated_rules if bool(r.enabled))

    return BypassRuleListResponse(
        rules=rules_list,
        total=len(rules_list),
        enabled_count=enabled_count,
        disabled_count=len(rules_list) - enabled_count,
    )
