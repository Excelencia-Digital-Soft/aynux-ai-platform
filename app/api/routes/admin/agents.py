# ============================================================================
# SCOPE: GLOBAL
# Description: Admin API para gestionar agentes disponibles. Permite
#              crear, actualizar, habilitar/deshabilitar agentes,
#              y configurar qué agentes están disponibles en el sistema.
# Tenant-Aware: No - agentes son globales, habilitación controlada por enabled.
# ============================================================================
"""
Agents Admin API - Manage available agents.

Provides endpoints for:
- Listing all agents with filtering
- Creating and updating agents
- Toggling agent enabled status
- Seeding builtin agents
- Bulk operations

Replaces ENABLED_AGENTS environment variable with database-driven configuration.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.services.agent_service import (
    AgentAlreadyExistsError,
    AgentService,
)

router = APIRouter(tags=["Agents"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class AgentCreate(BaseModel):
    """Schema for creating an agent."""

    agent_key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    agent_type: Literal["builtin", "specialized", "supervisor", "orchestrator", "custom"] = "specialized"
    domain_key: str | None = None
    enabled: bool = True
    priority: int = Field(default=50, ge=0, le=100)
    keywords: list[str] = []
    intent_patterns: list[dict] = []
    config: dict = {}


class AgentUpdate(BaseModel):
    """Schema for updating an agent."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(None, ge=0, le=100)
    keywords: list[str] | None = None
    intent_patterns: list[dict] | None = None
    config: dict | None = None


class AgentResponse(BaseModel):
    """Schema for agent response."""

    id: str
    agent_key: str
    name: str
    description: str | None
    agent_type: str
    domain_key: str | None
    enabled: bool
    priority: int
    keywords: list[str]
    intent_patterns: list[dict]
    config: dict
    sync_source: str
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """Schema for agent list response."""

    agents: list[AgentResponse]
    total: int
    enabled_count: int
    disabled_count: int


class SeedResult(BaseModel):
    """Schema for seed operation result."""

    added: int
    skipped: int


class BulkAgentRequest(BaseModel):
    """Schema for bulk enable/disable request."""

    agent_ids: list[str]


class PriorityUpdate(BaseModel):
    """Schema for updating priority."""

    id: str
    priority: int = Field(..., ge=0, le=100)


class BulkPriorityRequest(BaseModel):
    """Schema for bulk priority update."""

    priorities: list[PriorityUpdate]


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("", response_model=AgentListResponse)
async def list_agents(
    agent_type: str | None = Query(None, description="Filter by type (builtin/specialized/custom)"),
    domain_key: str | None = Query(None, description="Filter by domain (excelencia/ecommerce/etc)"),
    enabled_only: bool = Query(False, description="Only return enabled agents"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all agents with optional filtering.

    Admin endpoint - shows all agents including disabled ones.
    """
    service = AgentService.with_session(db)

    agents = await service.list_agents(
        agent_type=agent_type,
        domain_key=domain_key,
        enabled_only=enabled_only,
    )

    enabled = sum(1 for a in agents if a.enabled)

    return AgentListResponse(
        agents=[AgentResponse(**a.to_dict()) for a in agents],
        total=len(agents),
        enabled_count=enabled,
        disabled_count=len(agents) - enabled,
    )


@router.get("/enabled-keys", response_model=list[str])
async def get_enabled_keys(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get list of enabled agent keys.

    Returns agent_key strings for all enabled agents.
    Used by graph and routing system.
    """
    service = AgentService.with_session(db)
    return await service.get_enabled_keys()


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific agent by ID."""
    service = AgentService.with_session(db)
    agent = await service.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )

    return AgentResponse(**agent.to_dict())


@router.get("/key/{agent_key}", response_model=AgentResponse)
async def get_agent_by_key(
    agent_key: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific agent by key."""
    service = AgentService.with_session(db)
    agent = await service.get_by_key(agent_key)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with key '{agent_key}' not found",
        )

    return AgentResponse(**agent.to_dict())


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new agent entry."""
    service = AgentService.with_session(db)

    try:
        agent_data = data.model_dump()
        agent_data["sync_source"] = "manual"
        agent = await service.create(agent_data)
        return AgentResponse(**agent.to_dict())

    except AgentAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update an existing agent."""
    service = AgentService.with_session(db)

    update_data = data.model_dump(exclude_none=True)
    agent = await service.update(agent_id, update_data)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )

    return AgentResponse(**agent.to_dict())


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an agent."""
    service = AgentService.with_session(db)
    deleted = await service.delete(agent_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )


@router.post("/{agent_id}/toggle", response_model=AgentResponse)
async def toggle_agent_enabled(
    agent_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle agent enabled status."""
    service = AgentService.with_session(db)
    agent = await service.toggle_enabled(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )

    return AgentResponse(**agent.to_dict())


@router.post("/seed/builtin", response_model=SeedResult)
async def seed_builtin_agents(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Seed database with builtin agents from BUILTIN_AGENT_DEFAULTS.

    Only adds agents that don't already exist.
    Does NOT modify existing agents.
    """
    service = AgentService.with_session(db)
    result = await service.seed_builtin_agents()
    return SeedResult(**result)


@router.post("/{agent_key}/reset", response_model=AgentResponse)
async def reset_agent_to_defaults(
    agent_key: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Reset an agent to its builtin defaults.

    Only works for builtin agents.
    """
    service = AgentService.with_session(db)
    agent = await service.reset_to_builtin_defaults(agent_key)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_key}' not found or is not a builtin agent",
        )

    return AgentResponse(**agent.to_dict())


@router.post("/bulk/enable")
async def bulk_enable_agents(
    data: BulkAgentRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Enable multiple agents at once."""
    service = AgentService.with_session(db)
    agent_uuids = [UUID(id_str) for id_str in data.agent_ids]
    count = await service.enable_agents(agent_uuids)
    return {"updated": count}


@router.post("/bulk/disable")
async def bulk_disable_agents(
    data: BulkAgentRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Disable multiple agents at once."""
    service = AgentService.with_session(db)
    agent_uuids = [UUID(id_str) for id_str in data.agent_ids]
    count = await service.disable_agents(agent_uuids)
    return {"updated": count}


@router.post("/bulk/priority")
async def bulk_update_priority(
    data: BulkPriorityRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Update priority for multiple agents."""
    service = AgentService.with_session(db)
    priorities = [{"id": UUID(p.id), "priority": p.priority} for p in data.priorities]
    count = await service.update_priorities(priorities)
    return {"updated": count}
