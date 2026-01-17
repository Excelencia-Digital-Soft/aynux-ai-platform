"""
Admin API for awaiting type configuration management.

Provides CRUD endpoints for database-driven awaiting type configurations.
Supports multi-tenant (organization_id) and multi-domain (domain_key) filtering.

Endpoints:
    GET  /                          - List all configs
    POST /                          - Create config
    GET  /{config_id}               - Get by ID
    PUT  /{config_id}               - Update config
    DELETE /{config_id}             - Delete config
    GET  /by-type/{awaiting_type}   - Get by awaiting type
    POST /bulk                      - Bulk create
    POST /cache/invalidate          - Invalidate cache
    GET  /cache/stats               - Cache statistics
    POST /cache/warm                - Warm cache
    GET  /types                     - List all awaiting types
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_async_db
from app.core.cache.awaiting_type_cache import awaiting_type_cache
from app.models.db.awaiting_type_config import AwaitingTypeConfig, AwaitingTypes
from app.repositories.awaiting_type_repository import AwaitingTypeRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/awaiting-type-configs",
    tags=["Awaiting Type Configuration"],
)


# =============================================================================
# Pydantic Schemas
# =============================================================================


class AwaitingTypeConfigBase(BaseModel):
    """Base schema for awaiting type configuration."""

    domain_key: str = Field(default="pharmacy", description="Domain scope")
    awaiting_type: str = Field(description="Awaiting input type (dni, amount, payment_confirmation, etc.)")
    target_node: str = Field(description="Node to route to when awaiting this type")
    valid_response_intents: list[str] = Field(
        default_factory=list,
        description="Intent keys for validating responses (bypasses global keywords)",
    )
    validation_pattern: str | None = Field(
        default=None,
        description="Optional regex pattern for validating responses",
    )
    priority: int = Field(default=0, description="Processing priority (higher=first)")
    is_enabled: bool = Field(default=True, description="Whether config is active")
    display_name: str | None = Field(default=None, description="Human-readable name")
    description: str | None = Field(default=None, description="Usage notes")


class AwaitingTypeConfigCreate(AwaitingTypeConfigBase):
    """Schema for creating awaiting type configuration."""

    organization_id: UUID | None = Field(default=None, description="Organization (NULL for system defaults)")


class AwaitingTypeConfigUpdate(BaseModel):
    """Schema for updating awaiting type configuration (partial update)."""

    target_node: str | None = None
    valid_response_intents: list[str] | None = None
    validation_pattern: str | None = None
    priority: int | None = None
    is_enabled: bool | None = None
    display_name: str | None = None
    description: str | None = None


class AwaitingTypeConfigResponse(BaseModel):
    """Response schema for awaiting type configuration."""

    id: str
    organization_id: str | None
    domain_key: str
    awaiting_type: str
    target_node: str
    valid_response_intents: list[str]
    validation_pattern: str | None
    priority: int
    is_enabled: bool
    display_name: str | None
    description: str | None
    created_at: str | None
    updated_at: str | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class BulkCreateRequest(BaseModel):
    """Request schema for bulk creation."""

    configs: list[AwaitingTypeConfigCreate] = Field(description="List of configs to create")


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


def _model_to_response(config: AwaitingTypeConfig) -> AwaitingTypeConfigResponse:
    """Convert SQLAlchemy model to response schema."""
    return AwaitingTypeConfigResponse(**config.to_dict())


# =============================================================================
# CRUD Endpoints
# =============================================================================


@router.get("/", response_model=list[AwaitingTypeConfigResponse])
async def list_configs(
    domain_key: str = Query(default="pharmacy", description="Domain to filter by"),
    organization_id: UUID | None = Query(default=None, description="Organization to filter by"),
    enabled_only: bool = Query(default=True, description="Only return enabled"),
    db: AsyncSession = Depends(get_async_db),
) -> list[AwaitingTypeConfigResponse]:
    """
    List awaiting type configurations.

    Filters by domain_key, optionally by organization_id.
    """
    repo = AwaitingTypeRepository(db)
    configs = await repo.get_all(organization_id, domain_key, enabled_only)

    return [_model_to_response(c) for c in configs]


@router.post("/", response_model=AwaitingTypeConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    config_data: AwaitingTypeConfigCreate,
    db: AsyncSession = Depends(get_async_db),
) -> AwaitingTypeConfigResponse:
    """
    Create a new awaiting type configuration.
    """
    repo = AwaitingTypeRepository(db)

    # Check for duplicate
    existing = await repo.get_by_awaiting_type(
        config_data.organization_id,
        config_data.domain_key,
        config_data.awaiting_type,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Config with awaiting_type '{config_data.awaiting_type}' already exists",
        )

    # Create model
    config = AwaitingTypeConfig.create(
        organization_id=config_data.organization_id,
        domain_key=config_data.domain_key,
        awaiting_type=config_data.awaiting_type,
        target_node=config_data.target_node,
        valid_response_intents=config_data.valid_response_intents,
        validation_pattern=config_data.validation_pattern,
        priority=config_data.priority,
        is_enabled=config_data.is_enabled,
        display_name=config_data.display_name,
        description=config_data.description,
    )

    created = await repo.create(config)
    await db.commit()

    # Invalidate cache for this org/domain
    await awaiting_type_cache.invalidate(config_data.organization_id, config_data.domain_key)

    return _model_to_response(created)


@router.get("/{config_id}", response_model=AwaitingTypeConfigResponse)
async def get_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> AwaitingTypeConfigResponse:
    """Get an awaiting type configuration by ID."""
    repo = AwaitingTypeRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    return _model_to_response(config)


@router.put("/{config_id}", response_model=AwaitingTypeConfigResponse)
async def update_config(
    config_id: UUID,
    config_data: AwaitingTypeConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
) -> AwaitingTypeConfigResponse:
    """Update an awaiting type configuration."""
    repo = AwaitingTypeRepository(db)
    config = await repo.get_by_id(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    # Update fields
    update_data = config_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    updated = await repo.update(config)
    await db.commit()

    # Invalidate cache
    org_id = config.organization_id
    domain = config.domain_key
    await awaiting_type_cache.invalidate(org_id, domain)

    return _model_to_response(updated)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """Delete an awaiting type configuration."""
    repo = AwaitingTypeRepository(db)

    # Get config first to know org/domain for cache invalidation
    config = await repo.get_by_id(config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    org_id = config.organization_id
    domain = config.domain_key

    deleted = await repo.delete(config_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config {config_id} not found",
        )

    await db.commit()

    # Invalidate cache
    await awaiting_type_cache.invalidate(org_id, domain)


@router.get("/by-type/{awaiting_type}", response_model=AwaitingTypeConfigResponse | None)
async def get_by_awaiting_type(
    awaiting_type: str,
    domain_key: str = Query(default="pharmacy"),
    organization_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
) -> AwaitingTypeConfigResponse | None:
    """Get an awaiting type configuration by awaiting type."""
    repo = AwaitingTypeRepository(db)
    config = await repo.get_by_awaiting_type(organization_id, domain_key, awaiting_type)

    if not config:
        return None

    return _model_to_response(config)


@router.post("/bulk", response_model=list[AwaitingTypeConfigResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_configs(
    request: BulkCreateRequest,
    db: AsyncSession = Depends(get_async_db),
) -> list[AwaitingTypeConfigResponse]:
    """Bulk create awaiting type configurations."""
    repo = AwaitingTypeRepository(db)

    models = []
    for config_data in request.configs:
        model = AwaitingTypeConfig.create(
            organization_id=config_data.organization_id,
            domain_key=config_data.domain_key,
            awaiting_type=config_data.awaiting_type,
            target_node=config_data.target_node,
            valid_response_intents=config_data.valid_response_intents,
            validation_pattern=config_data.validation_pattern,
            priority=config_data.priority,
            is_enabled=config_data.is_enabled,
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
        await awaiting_type_cache.invalidate(org_id, domain)

    return [_model_to_response(c) for c in created]


# =============================================================================
# Cache Management Endpoints
# =============================================================================


@router.post("/cache/invalidate", response_model=dict[str, Any])
async def invalidate_cache(
    request: CacheInvalidateRequest,
) -> dict[str, Any]:
    """
    Invalidate awaiting type config cache.

    Clears both memory (L1) and Redis (L2) caches.
    """
    count = await awaiting_type_cache.invalidate(request.organization_id, request.domain_key)
    return {
        "status": "cache invalidated",
        "entries_cleared": count,
        "organization_id": str(request.organization_id) if request.organization_id else None,
        "domain_key": request.domain_key,
    }


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """Get awaiting type config cache statistics."""
    stats = awaiting_type_cache.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/warm", response_model=dict[str, Any])
async def warm_cache(
    organization_id: UUID | None = Query(default=None),
    domain_key: str = Query(default="pharmacy"),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Warm awaiting type config cache.

    Force-loads from database and populates both caches.
    """
    configs = await awaiting_type_cache.warm(db, organization_id, domain_key)

    return {
        "status": "cache warmed",
        "organization_id": str(organization_id) if organization_id else None,
        "domain_key": domain_key,
        "awaiting_types": list(configs.keys()),
        "total_configs": len(configs),
    }


# =============================================================================
# Utility Endpoints
# =============================================================================


@router.get("/types", response_model=list[str])
async def get_awaiting_types() -> list[str]:
    """Get all known awaiting types."""
    return list(AwaitingTypes.ALL_TYPES)


@router.get("/domains")
async def list_domains(
    db: AsyncSession = Depends(get_async_db),
) -> list[dict[str, Any]]:
    """
    List all domains that have awaiting type configurations.
    """
    from sqlalchemy import distinct, func, select

    stmt = (
        select(
            AwaitingTypeConfig.domain_key,
            func.count(distinct(AwaitingTypeConfig.id)).label("config_count"),
        )
        .group_by(AwaitingTypeConfig.domain_key)
        .order_by(AwaitingTypeConfig.domain_key)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [{"domain_key": row.domain_key, "config_count": row.config_count} for row in rows]
