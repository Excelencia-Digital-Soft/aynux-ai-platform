"""
Tenant Agents Admin API - Manage agents per organization.

Provides endpoints for configuring which agents are enabled and their settings.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_organization_by_id, require_admin
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization, OrganizationUser, TenantAgent

router = APIRouter(tags=["Tenant Agents"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class TenantAgentCreate(BaseModel):
    """Schema for creating a tenant agent configuration."""

    agent_key: str = Field(..., min_length=1, max_length=100)
    agent_type: Literal["domain", "specialized", "custom"] = "specialized"
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    agent_class: str | None = Field(None, max_length=255)
    enabled: bool = True
    priority: int = Field(default=0, ge=-100, le=100)
    domain_key: str | None = None
    keywords: list[str] = []
    intent_patterns: list[dict] = []
    config: dict = {}


class TenantAgentUpdate(BaseModel):
    """Schema for updating a tenant agent configuration."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(None, ge=-100, le=100)
    keywords: list[str] | None = None
    intent_patterns: list[dict] | None = None
    config: dict | None = None


class TenantAgentResponse(BaseModel):
    """Schema for tenant agent response."""

    id: str
    organization_id: str
    agent_key: str
    agent_type: str
    display_name: str
    description: str | None
    agent_class: str | None
    enabled: bool
    priority: int
    domain_key: str | None
    keywords: list[str]
    intent_patterns: list[dict]
    config: dict
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class TenantAgentListResponse(BaseModel):
    """Schema for tenant agent list response."""

    agents: list[TenantAgentResponse]
    total: int
    enabled_count: int
    disabled_count: int


# ============================================================
# BUILTIN AGENTS DEFINITION
# ============================================================

BUILTIN_AGENTS = {
    "greeting_agent": {
        "display_name": "Greeting Agent",
        "description": "Handles greetings and initial interactions",
        "agent_type": "specialized",
        "keywords": ["hola", "hello", "hi", "buenos días", "buenas tardes"],
    },
    "product_agent": {
        "display_name": "Product Agent",
        "description": "Handles product queries, search, and catalog information",
        "agent_type": "domain",
        "domain_key": "ecommerce",
        "keywords": ["producto", "product", "buscar", "precio", "disponible"],
    },
    "support_agent": {
        "display_name": "Support Agent",
        "description": "Handles customer support and troubleshooting",
        "agent_type": "specialized",
        "keywords": ["ayuda", "problema", "soporte", "support", "help"],
    },
    "excelencia_agent": {
        "display_name": "Excelencia Agent",
        "description": "Handles Excelencia ERP system information",
        "agent_type": "domain",
        "domain_key": "excelencia",
        "keywords": ["excelencia", "erp", "módulo", "sistema"],
    },
    "fallback_agent": {
        "display_name": "Fallback Agent",
        "description": "Handles unrecognized intents and provides general assistance",
        "agent_type": "specialized",
        "keywords": [],
    },
    "farewell_agent": {
        "display_name": "Farewell Agent",
        "description": "Handles goodbyes and conversation endings",
        "agent_type": "specialized",
        "keywords": ["adiós", "bye", "chao", "gracias", "hasta luego"],
    },
    "promotions_agent": {
        "display_name": "Promotions Agent",
        "description": "Handles promotions, discounts, and special offers",
        "agent_type": "domain",
        "domain_key": "ecommerce",
        "keywords": ["promoción", "descuento", "oferta", "sale"],
    },
    "tracking_agent": {
        "display_name": "Tracking Agent",
        "description": "Handles order tracking and shipping information",
        "agent_type": "domain",
        "domain_key": "ecommerce",
        "keywords": ["pedido", "envío", "tracking", "seguimiento"],
    },
    "invoice_agent": {
        "display_name": "Invoice Agent",
        "description": "Handles billing, invoices, and payment queries",
        "agent_type": "specialized",
        "keywords": ["factura", "pago", "cobro", "invoice"],
    },
}


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/agents", response_model=TenantAgentListResponse)
async def list_tenant_agents(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all agents configured for the organization.

    Requires admin or owner role.
    """
    stmt = (
        select(TenantAgent)
        .where(TenantAgent.organization_id == org_id)
        .order_by(TenantAgent.priority.desc(), TenantAgent.agent_key)
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()

    agents_list = [TenantAgentResponse(**a.to_dict()) for a in agents]
    enabled_count = sum(1 for a in agents if a.enabled)

    return TenantAgentListResponse(
        agents=agents_list,
        total=len(agents_list),
        enabled_count=enabled_count,
        disabled_count=len(agents_list) - enabled_count,
    )


@router.post("/{org_id}/agents", response_model=TenantAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_agent(
    data: TenantAgentCreate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    org: Organization = Depends(get_organization_by_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new agent configuration.

    Requires admin or owner role.
    """
    # Check quota
    stmt = select(TenantAgent).where(TenantAgent.organization_id == org_id)
    result = await db.execute(stmt)
    current_count = len(result.scalars().all())

    if current_count >= org.max_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Límite de agentes alcanzado ({org.max_agents})",
        )

    # Check if agent_key already exists
    stmt = select(TenantAgent).where(
        TenantAgent.organization_id == org_id,
        TenantAgent.agent_key == data.agent_key,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent key '{data.agent_key}' ya existe",
        )

    agent = TenantAgent(
        id=uuid.uuid4(),
        organization_id=org_id,
        agent_key=data.agent_key,
        agent_type=data.agent_type,
        display_name=data.display_name,
        description=data.description,
        agent_class=data.agent_class,
        enabled=data.enabled,
        priority=data.priority,
        domain_key=data.domain_key,
        keywords=data.keywords,
        intent_patterns=data.intent_patterns,
        config=data.config,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return TenantAgentResponse(**agent.to_dict())


@router.get("/{org_id}/agents/{agent_id}", response_model=TenantAgentResponse)
async def get_tenant_agent(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    agent_id: uuid.UUID = Path(..., description="Agent ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific agent configuration.

    Requires admin or owner role.
    """
    stmt = select(TenantAgent).where(
        TenantAgent.organization_id == org_id,
        TenantAgent.id == agent_id,
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )

    return TenantAgentResponse(**agent.to_dict())


@router.put("/{org_id}/agents/{agent_id}", response_model=TenantAgentResponse)
async def update_tenant_agent(
    data: TenantAgentUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    agent_id: uuid.UUID = Path(..., description="Agent ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update an agent configuration.

    Requires admin or owner role.
    """
    stmt = select(TenantAgent).where(
        TenantAgent.organization_id == org_id,
        TenantAgent.id == agent_id,
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )

    if data.display_name is not None:
        agent.display_name = data.display_name
    if data.description is not None:
        agent.description = data.description
    if data.enabled is not None:
        agent.enabled = data.enabled
    if data.priority is not None:
        agent.priority = data.priority
    if data.keywords is not None:
        agent.keywords = data.keywords
    if data.intent_patterns is not None:
        agent.intent_patterns = data.intent_patterns
    if data.config is not None:
        agent.config = data.config

    agent.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(agent)

    return TenantAgentResponse(**agent.to_dict())


@router.post("/{org_id}/agents/{agent_id}/toggle", response_model=TenantAgentResponse)
async def toggle_tenant_agent(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    agent_id: uuid.UUID = Path(..., description="Agent ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Toggle an agent's enabled status.

    Requires admin or owner role.
    """
    stmt = select(TenantAgent).where(
        TenantAgent.organization_id == org_id,
        TenantAgent.id == agent_id,
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )

    agent.enabled = not agent.enabled
    agent.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(agent)

    return TenantAgentResponse(**agent.to_dict())


@router.delete("/{org_id}/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_agent(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    agent_id: uuid.UUID = Path(..., description="Agent ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete an agent configuration.

    Requires admin or owner role.
    """
    stmt = select(TenantAgent).where(
        TenantAgent.organization_id == org_id,
        TenantAgent.id == agent_id,
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente no encontrado",
        )

    await db.delete(agent)
    await db.commit()


@router.post("/{org_id}/agents/init-builtin", response_model=TenantAgentListResponse)
async def initialize_builtin_agents(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initialize builtin agents for the organization.

    Creates default agent configurations based on BUILTIN_AGENTS.
    Skips agents that already exist.
    Requires admin or owner role.
    """
    created = []

    for agent_key, agent_info in BUILTIN_AGENTS.items():
        # Check if exists
        stmt = select(TenantAgent).where(
            TenantAgent.organization_id == org_id,
            TenantAgent.agent_key == agent_key,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            created.append(existing)
            continue

        agent = TenantAgent(
            id=uuid.uuid4(),
            organization_id=org_id,
            agent_key=agent_key,
            agent_type=agent_info.get("agent_type", "specialized"),
            display_name=agent_info["display_name"],
            description=agent_info.get("description"),
            domain_key=agent_info.get("domain_key"),
            keywords=agent_info.get("keywords", []),
            intent_patterns=[],
            config={},
            enabled=True,
            priority=0,
        )
        db.add(agent)
        created.append(agent)

    await db.commit()

    # Refresh all to get IDs
    agents_list = []
    for agent in created:
        await db.refresh(agent)
        agents_list.append(TenantAgentResponse(**agent.to_dict()))

    enabled_count = sum(1 for a in agents_list if a.enabled)

    return TenantAgentListResponse(
        agents=agents_list,
        total=len(agents_list),
        enabled_count=enabled_count,
        disabled_count=len(agents_list) - enabled_count,
    )
