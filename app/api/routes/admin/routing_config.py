"""
Admin API for routing configuration management.

Provides CRUD endpoints for database-driven routing configurations.
Supports multi-tenant (organization_id) and multi-domain (domain_key) filtering.

Endpoints:
    GET  /                          - List all configs
    POST /                          - Create config
    GET  /{config_id}               - Get by ID
    PUT  /{config_id}               - Update config
    DELETE /{config_id}             - Delete config
    GET  /by-trigger/{trigger}      - Get by trigger value
    POST /bulk                      - Bulk create
    POST /cache/invalidate          - Invalidate cache
    GET  /cache/stats               - Cache statistics
    POST /cache/warm                - Warm cache
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_async_db
from app.core.cache.routing_config_cache import routing_config_cache
from app.models.db.routing_config import RoutingConfig, RoutingConfigType
from app.repositories.routing_config_repository import RoutingConfigRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/routing-configs",
    tags=["Routing Configuration"],
)


# =============================================================================
# Pydantic Schemas
# =============================================================================


class RoutingConfigBase(BaseModel):
    """Base schema for routing configuration."""

    domain_key: str = Field(default="pharmacy", description="Domain scope")
    config_type: str = Field(description="Type: global_keyword, button_mapping, menu_option, list_selection")
    trigger_value: str = Field(description="Value that triggers routing")
    target_intent: str = Field(description="Intent to set when triggered")
    target_node: str | None = Field(default=None, description="Node to route to")
    priority: int = Field(default=0, description="Processing priority (higher=first)")
    is_enabled: bool = Field(default=True, description="Whether config is active")
    requires_auth: bool = Field(default=False, description="Whether auth required")
    clears_context: bool = Field(default=False, description="Whether to clear context")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional config (aliases, conditions)")
    display_name: str | None = Field(default=None, description="Human-readable name")
    description: str | None = Field(default=None, description="Usage notes")


class RoutingConfigCreate(RoutingConfigBase):
    """Schema for creating routing configuration."""

    organization_id: UUID | None = Field(default=None, description="Organization (NULL for system defaults)")


class RoutingConfigUpdate(BaseModel):
    """Schema for updating routing configuration (partial update)."""

    target_intent: str | None = None
    target_node: str | None = None
    priority: int | None = None
    is_enabled: bool | None = None
    requires_auth: bool | None = None
    clears_context: bool | None = None
    metadata: dict[str, Any] | None = None
    display_name: str | None = None
    description: str | None = None


class RoutingConfigResponse(BaseModel):
    """Response schema for routing configuration."""

    id: str
    organization_id: str | None
    domain_key: str
    config_type: str
    trigger_value: str
    target_intent: str
    target_node: str | None
    priority: int
    is_enabled: bool
    requires_auth: bool
    clears_context: bool
    metadata: dict[str, Any] | None
    display_name: str | None
    description: str | None
    created_at: str | None
    updated_at: str | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class BulkCreateRequest(BaseModel):
    """Request schema for bulk creation."""

    configs: list[RoutingConfigCreate] = Field(description="List of configs to create")


class CacheInvalidateRequest(BaseModel):
    """Request schema for cache invalidation."""

    organization_id: UUID | None = Field(default=None, description="Specific org to invalidate (NULL for all)")
    domain_key: str | None = Field(default=None, description="Specific domain to invalidate (NULL for all)")


class CacheStatsResponse(BaseModel):
    """Response schema for cache statistics."""

    memory_hits: int
    memory_misses: int
    memory_hit_rate: float
    redis_hits: int
    redis_misses: int
    redis_hit_rate: float
    db_loads: int
    invalidations: int
    cached_keys: int


# =============================================================================
# Helper Functions
# =============================================================================


def _model_to_response(config: RoutingConfig) -> RoutingConfigResponse:
    """Convert SQLAlchemy model to response schema."""
    return RoutingConfigResponse(**config.to_dict())


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.get("/", response_model=list[RoutingConfigResponse])
async def list_configs(
    domain_key: str = Query(default="pharmacy", description="Domain to filter by"),
    config_type: str | None = Query(default=None, description="Config type to filter"),
    organization_id: UUID | None = Query(default=None, description="Organization to filter by"),
    enabled_only: bool = Query(default=True, description="Only return enabled"),
    db: AsyncSession = Depends(get_async_db),
) -> list[RoutingConfigResponse]:
    """
    List routing configurations.

    Filters by domain_key, optionally by config_type and organization_id.
    """
    repo = RoutingConfigRepository(db)

    if config_type:
        configs = await repo.get_by_type(organization_id, domain_key, config_type, enabled_only)
    else:
        configs = await repo.get_all(organization_id, domain_key, enabled_only)

    return [_model_to_response(c) for c in configs]


@router.post("/", response_model=RoutingConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: RoutingConfigCreate,
    db: AsyncSession = Depends(get_async_db),
) -> RoutingConfigResponse:
    """
    Create a new routing configuration.

    Validates config_type is valid.
    """
    if config_data.config_type not in RoutingConfigType.ALL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid config_type. Must be one of: {list(RoutingConfigType.ALL_TYPES)}",
        )

    repo = RoutingConfigRepository(db)

    # Check for duplicate
    existing = await repo.get_by_trigger(
        config_data.organization_id,
        config_data.domain_key,
        config_data.config_type,
        config_data.trigger_value,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Config with trigger '{config_data.trigger_value}' already exists",
        )

    # Create model
    config = RoutingConfig.create(
        organization_id=config_data.organization_id,
        domain_key=config_data.domain_key,
        config_type=config_data.config_type,
        trigger_value=config_data.trigger_value,
        target_intent=config_data.target_intent,
        target_node=config_data.target_node,
        priority=config_data.priority,
        is_enabled=config_data.is_enabled,
        requires_auth=config_data.requires_auth,
        clears_context=config_data.clears_context,
        metadata=config_data.metadata,
        display_name=config_data.display_name,
        description=config_data.description,
    )

    created = await repo.create(config)
    await db.commit()

    # Invalidate cache for this org/domain
    await routing_config_cache.invalidate(config_data.organization_id, config_data.domain_key)

    return _model_to_response(created)


@router.get("/{config_id}", response_model=RoutingConfigResponse)
async def get_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> RoutingConfigResponse:
    """Get a routing configuration by ID."""
    repo = RoutingConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    return _model_to_response(config)


@router.put("/{config_id}", response_model=RoutingConfigResponse)
async def update_config(
    config_id: UUID,
    config_data: RoutingConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
) -> RoutingConfigResponse:
    """Update a routing configuration."""
    repo = RoutingConfigRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    # Update fields
    update_data = config_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "metadata":
            config.metadata_ = value
        else:
            setattr(config, field, value)

    updated = await repo.update(config)
    await db.commit()

    # Invalidate cache
    org_id = getattr(config, "organization_id", None)
    domain = getattr(config, "domain_key", "pharmacy")
    await routing_config_cache.invalidate(org_id, domain)

    return _model_to_response(updated)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete a routing configuration."""
    repo = RoutingConfigRepository(db)

    # Get config first to know org/domain for cache invalidation
    config = await repo.get_by_id(config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    org_id = getattr(config, "organization_id", None)
    domain = getattr(config, "domain_key", "pharmacy")

    deleted = await repo.delete(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    await db.commit()

    # Invalidate cache
    await routing_config_cache.invalidate(org_id, domain)


@router.get("/by-trigger/{trigger_value}", response_model=RoutingConfigResponse | None)
async def get_by_trigger(
    trigger_value: str,
    domain_key: str = Query(default="pharmacy"),
    config_type: str = Query(description="Config type to search"),
    organization_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
) -> RoutingConfigResponse | None:
    """Get a routing configuration by trigger value."""
    repo = RoutingConfigRepository(db)
    config = await repo.get_by_trigger(organization_id, domain_key, config_type, trigger_value)

    if not config:
        return None

    return _model_to_response(config)


@router.post("/bulk", response_model=list[RoutingConfigResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_configs(
    request: BulkCreateRequest,
    db: AsyncSession = Depends(get_async_db),
) -> list[RoutingConfigResponse]:
    """Bulk create routing configurations."""
    repo = RoutingConfigRepository(db)

    models = []
    for config_data in request.configs:
        if config_data.config_type not in RoutingConfigType.ALL_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid config_type: {config_data.config_type}",
            )

        model = RoutingConfig.create(
            organization_id=config_data.organization_id,
            domain_key=config_data.domain_key,
            config_type=config_data.config_type,
            trigger_value=config_data.trigger_value,
            target_intent=config_data.target_intent,
            target_node=config_data.target_node,
            priority=config_data.priority,
            is_enabled=config_data.is_enabled,
            requires_auth=config_data.requires_auth,
            clears_context=config_data.clears_context,
            metadata=config_data.metadata,
            display_name=config_data.display_name,
            description=config_data.description,
        )
        models.append(model)

    created = await repo.bulk_create(models)
    await db.commit()

    # Invalidate all affected caches
    affected_keys = set()
    for config_data in request.configs:
        affected_keys.add((config_data.organization_id, config_data.domain_key))

    for org_id, domain in affected_keys:
        await routing_config_cache.invalidate(org_id, domain)

    return [_model_to_response(c) for c in created]


# =============================================================================
# Cache Management Endpoints
# =============================================================================


@router.post("/cache/invalidate", response_model=dict[str, Any])
async def invalidate_cache(
    request: CacheInvalidateRequest,
) -> dict[str, Any]:
    """
    Invalidate routing config cache.

    Clears both memory (L1) and Redis (L2) caches.
    """
    count = await routing_config_cache.invalidate(request.organization_id, request.domain_key)
    return {
        "status": "cache invalidated",
        "entries_cleared": count,
        "organization_id": str(request.organization_id) if request.organization_id else None,
        "domain_key": request.domain_key,
    }


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """Get routing config cache statistics."""
    stats = routing_config_cache.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/warm", response_model=dict[str, Any])
async def warm_cache(
    organization_id: UUID | None = Query(default=None),
    domain_key: str = Query(default="pharmacy"),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Warm routing config cache.

    Force-loads from database and populates both caches.
    """
    configs = await routing_config_cache.warm(db, organization_id, domain_key)
    total_configs = sum(len(v) for v in configs.values())

    return {
        "status": "cache warmed",
        "organization_id": str(organization_id) if organization_id else None,
        "domain_key": domain_key,
        "config_types": list(configs.keys()),
        "total_configs": total_configs,
    }


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get("/types", response_model=list[str])
async def get_config_types() -> list[str]:
    """Get all valid configuration types."""
    return list(RoutingConfigType.ALL_TYPES)


@router.get("/domains")
async def list_domains(
    db: AsyncSession = Depends(get_async_db),
) -> list[dict[str, Any]]:
    """
    List all domains that have routing configurations.
    """
    from sqlalchemy import distinct, func, select

    stmt = (
        select(
            RoutingConfig.domain_key,
            func.count(distinct(RoutingConfig.id)).label("config_count"),
        )
        .group_by(RoutingConfig.domain_key)
        .order_by(RoutingConfig.domain_key)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [{"domain_key": row.domain_key, "config_count": row.config_count} for row in rows]
