# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Admin API para gestionar response configs. Diseño genérico que
#              soporta pharmacy ahora y otros dominios en el futuro.
# Tenant-Aware: Yes - cada organización tiene su propia configuración.
# Domain-Aware: Yes - cada dominio dentro de una org tiene sus configs.
# ============================================================================
"""
Response Configs Admin API - Manage response generation configurations.

Provides endpoints for:
- CRUD operations on response configs
- Seeding configs from default data
- Cache invalidation and statistics
- Multi-domain support (pharmacy, healthcare, etc.)

Multi-tenant: Each organization can customize their own response configs.
No fallback: Configs must be in database for response generation to work.

API Prefix: /api/v1/admin/response-configs

IMPORTANT: Route order matters in FastAPI!
Specific routes (/bulk, /seed, /cache/*, /domains, /by-intent/*)
must be defined BEFORE parameterized routes (/{config_id}).
"""

from __future__ import annotations

import logging
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.response_configs import (
    BulkOperationResponse,
    CacheInvalidateRequest,
    CacheInvalidateResponse,
    CacheStatsResponse,
    CacheWarmRequest,
    CacheWarmResponse,
    DomainInfo,
    DomainListResponse,
    ResponseConfigBulkCreate,
    ResponseConfigCreate,
    ResponseConfigListResponse,
    ResponseConfigResponse,
    ResponseConfigUpdate,
    SeedResponseConfigsRequest,
    SeedResponseConfigsResponse,
)
from app.core.cache.response_config_cache import response_config_cache
from app.database.async_db import get_async_db
from app.models.db.response_configs import ResponseConfig
from app.repositories.response_config_repository import ResponseConfigRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Response Configs"])


# ============================================================
# HELPERS
# ============================================================


def _config_to_response(config) -> ResponseConfigResponse:
    """Convert ResponseConfig to response schema."""
    return ResponseConfigResponse(
        id=str(config.id),
        organization_id=str(config.organization_id),
        domain_key=config.domain_key,
        intent_key=config.intent_key,
        is_critical=config.is_critical,
        task_description=config.task_description,
        fallback_template_key=config.fallback_template_key,
        display_name=config.display_name,
        description=config.description,
        priority=config.priority,
        is_enabled=config.is_enabled,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


def _parse_uuid(value: str, field_name: str = "UUID") -> UUID:
    """Parse string to UUID with proper error handling."""
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: {e}",
        ) from e


# ============================================================
# LIST AND CREATE (root path)
# ============================================================


@router.get("", response_model=ResponseConfigListResponse)
async def list_configs(
    organization_id: str = Query(..., description="Organization UUID"),
    domain_key: str = Query("pharmacy", description="Domain scope"),
    enabled_only: bool = Query(False, description="Only return enabled configs"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all response configs for an organization and domain.

    Returns configs with all fields for response generation.
    """
    org_uuid = _parse_uuid(organization_id, "organization_id")

    repo = ResponseConfigRepository(db)
    configs = await repo.get_all_configs(
        organization_id=org_uuid,
        domain_key=domain_key,
        enabled_only=enabled_only,
    )

    return ResponseConfigListResponse(
        configs=[_config_to_response(c) for c in configs],
        total=len(configs),
        domain_key=domain_key,
    )


@router.post("", response_model=ResponseConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_config(
    data: ResponseConfigCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new response configuration.

    Invalidates cache for the organization after creation.
    """
    org_uuid = _parse_uuid(data.organization_id, "organization_id")

    repo = ResponseConfigRepository(db)

    # Check if config already exists for this intent
    existing = await repo.get_by_intent_key(org_uuid, data.intent_key, data.domain_key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Config for intent '{data.intent_key}' already exists in domain '{data.domain_key}'",
        )

    # Prepare data dict (exclude organization_id as it's passed separately)
    config_data = data.model_dump(exclude_unset=True)
    config_data.pop("organization_id")

    config = await repo.create(org_uuid, config_data)
    await db.commit()

    # Invalidate cache
    await response_config_cache.invalidate(org_uuid)
    logger.info(f"Created response config '{data.intent_key}' for org {org_uuid}")

    return _config_to_response(config)


# ============================================================
# BULK OPERATIONS - Must be before /{config_id}
# ============================================================


@router.post("/bulk", response_model=BulkOperationResponse)
async def bulk_create_configs(
    data: ResponseConfigBulkCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Bulk create response configurations.

    Skips configs that already exist (by intent_key).
    """
    org_uuid = _parse_uuid(data.organization_id, "organization_id")

    repo = ResponseConfigRepository(db)
    created = 0
    skipped = 0
    errors: list[str] = []

    for item in data.configs:
        try:
            # Check if exists
            existing = await repo.get_by_intent_key(
                org_uuid, item.intent_key, data.domain_key
            )
            if existing:
                skipped += 1
                continue

            # Create config
            config_data = item.model_dump()
            config_data["domain_key"] = data.domain_key
            await repo.create(org_uuid, config_data)
            created += 1

        except Exception as e:
            errors.append(f"{item.intent_key}: {e!s}")
            logger.warning(f"Error creating config {item.intent_key}: {e}")

    await db.commit()

    # Invalidate cache
    await response_config_cache.invalidate(org_uuid)

    return BulkOperationResponse(
        success=len(errors) == 0,
        created=created,
        skipped=skipped,
        errors=errors if errors else None,
    )


# ============================================================
# SEED ENDPOINT - Must be before /{config_id}
# ============================================================


@router.post("/seed", response_model=SeedResponseConfigsResponse)
async def seed_configs(
    data: SeedResponseConfigsRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Seed response configs from default data.

    Uses the same seed data from the migration to populate configs
    for a new organization.
    """
    org_uuid = _parse_uuid(data.organization_id, "organization_id")

    # Import seed data
    from app.scripts.seed_response_configs import get_seed_configs

    seed_data = get_seed_configs(data.domain_key)
    if not seed_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No seed data available for domain '{data.domain_key}'",
        )

    repo = ResponseConfigRepository(db)
    added = 0
    skipped = 0
    errors: list[str] = []

    # Optionally delete existing configs
    if data.overwrite:
        await repo.delete_all_for_org(org_uuid, data.domain_key)

    for config_data in seed_data:
        try:
            # Check if exists
            existing = await repo.get_by_intent_key(
                org_uuid, config_data["intent_key"], data.domain_key
            )
            if existing:
                skipped += 1
                continue

            # Create config
            config_data["domain_key"] = data.domain_key
            await repo.create(org_uuid, config_data)
            added += 1

        except Exception as e:
            errors.append(f"{config_data['intent_key']}: {e!s}")
            logger.warning(f"Error seeding config {config_data['intent_key']}: {e}")

    await db.commit()

    # Invalidate cache
    await response_config_cache.invalidate(org_uuid)

    return SeedResponseConfigsResponse(
        success=len(errors) == 0,
        added=added,
        skipped=skipped,
        total_available=len(seed_data),
        errors=errors if errors else None,
    )


# ============================================================
# CACHE MANAGEMENT - Must be before /{config_id}
# ============================================================


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    data: CacheInvalidateRequest | None = None,
):
    """
    Force cache invalidation.

    If organization_id is provided, invalidates only that org's cache.
    Otherwise, invalidates all caches (admin operation).
    """
    if data and data.organization_id:
        org_uuid = _parse_uuid(data.organization_id, "organization_id")
        await response_config_cache.invalidate(org_uuid)
        return CacheInvalidateResponse(
            success=True,
            organizations_invalidated=1,
            message=f"Cache invalidated for organization {org_uuid}",
        )
    else:
        count = await response_config_cache.invalidate_all()
        return CacheInvalidateResponse(
            success=True,
            organizations_invalidated=count,
            message=f"Cache invalidated for {count} organizations",
        )


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get cache statistics for monitoring."""
    stats = response_config_cache.get_stats()
    return CacheStatsResponse(**stats)


@router.post("/cache/warm", response_model=CacheWarmResponse)
async def warm_cache(
    data: CacheWarmRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Warm cache for a specific organization.

    Force-loads configs from database and populates both caches.
    """
    org_uuid = _parse_uuid(data.organization_id, "organization_id")

    configs = await response_config_cache.warm(db, org_uuid, data.domain_key)

    return CacheWarmResponse(
        success=True,
        configs_loaded=len(configs),
        message=f"Loaded {len(configs)} configs for org {org_uuid}",
    )


# ============================================================
# DOMAIN DISCOVERY - Must be before /{config_id}
# ============================================================


@router.get("/domains", response_model=DomainListResponse)
async def list_domains(
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all domains with response configs for an organization.

    Useful for discovering which domains have been configured.
    """
    org_uuid = _parse_uuid(organization_id, "organization_id")

    stmt = (
        select(
            ResponseConfig.domain_key,
            func.count(ResponseConfig.id).label("total"),
            func.sum(
                func.cast(ResponseConfig.is_enabled, sa.Integer)
            ).label("enabled"),
            func.sum(
                func.cast(ResponseConfig.is_critical, sa.Integer)
            ).label("critical"),
        )
        .where(ResponseConfig.organization_id == org_uuid)
        .group_by(ResponseConfig.domain_key)
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    domains = [
        DomainInfo(
            domain_key=row.domain_key,
            total_configs=row.total,
            enabled_configs=row.enabled or 0,
            critical_configs=row.critical or 0,
        )
        for row in rows
    ]

    return DomainListResponse(
        organization_id=str(org_uuid),
        domains=domains,
    )


# ============================================================
# LOOKUP BY INTENT KEY - Must be before /{config_id}
# ============================================================


@router.get("/by-intent/{intent_key}", response_model=ResponseConfigResponse)
async def get_config_by_intent(
    intent_key: str,
    organization_id: str = Query(..., description="Organization UUID"),
    domain_key: str = Query("pharmacy", description="Domain scope"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get response config by intent key.

    Useful for checking if an intent is configured.
    """
    org_uuid = _parse_uuid(organization_id, "organization_id")

    repo = ResponseConfigRepository(db)
    config = await repo.get_by_intent_key(org_uuid, intent_key, domain_key)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No config for intent '{intent_key}' in domain '{domain_key}'",
        )

    return _config_to_response(config)


# ============================================================
# PARAMETERIZED ROUTES - Must be LAST (catch-all for UUIDs)
# ============================================================


@router.get("/{config_id}", response_model=ResponseConfigResponse)
async def get_config(
    config_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific response config by ID."""
    config_uuid = _parse_uuid(config_id, "config_id")

    repo = ResponseConfigRepository(db)
    config = await repo.get_by_id(config_uuid)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config not found: {config_id}",
        )

    return _config_to_response(config)


@router.put("/{config_id}", response_model=ResponseConfigResponse)
async def update_config(
    config_id: str,
    data: ResponseConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update a response config.

    Only updates provided fields (partial update).
    Invalidates cache after update.
    """
    config_uuid = _parse_uuid(config_id, "config_id")

    repo = ResponseConfigRepository(db)

    # Get current config to get org_id
    current = await repo.get_by_id(config_uuid)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config not found: {config_id}",
        )

    update_data = data.model_dump(exclude_unset=True)
    config = await repo.update(config_uuid, update_data)
    await db.commit()

    # Invalidate cache
    await response_config_cache.invalidate(current.organization_id)
    logger.info(f"Updated response config {config_id}")

    return _config_to_response(config)


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a response config.

    WARNING: This may break response generation for the associated intent.
    Invalidates cache after deletion.
    """
    config_uuid = _parse_uuid(config_id, "config_id")

    repo = ResponseConfigRepository(db)

    # Get current config to get org_id
    current = await repo.get_by_id(config_uuid)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config not found: {config_id}",
        )

    org_id = current.organization_id
    await repo.delete(config_uuid)
    await db.commit()

    # Invalidate cache
    await response_config_cache.invalidate(org_id)
    logger.info(f"Deleted response config {config_id}")
