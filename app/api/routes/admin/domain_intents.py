# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Admin API for managing unified domain intent patterns. Supports
#              multiple domains (pharmacy, excelencia, ecommerce, healthcare, etc.)
# Tenant-Aware: Yes - each organization has isolated patterns per domain.
# ============================================================================
"""
Domain Intents Admin API - Manage intent patterns for any domain.

Provides endpoints for:
- CRUD operations on intents per domain
- Managing lemmas, phrases, confirmation patterns, keywords
- Seeding patterns from hardcoded defaults
- Cache invalidation and statistics

Multi-tenant: Each organization can customize patterns per domain.
Multi-domain: Supports pharmacy, excelencia, ecommerce, healthcare, etc.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.domain_intents import (
    CacheInvalidateRequest,
    CacheInvalidateResponse,
    CacheStatsResponse,
    ConfirmationPatternsRemoveRequest,
    ConfirmationPatternsRequest,
    DomainListResponse,
    IntentCreate,
    IntentListResponse,
    IntentResponse,
    IntentUpdate,
    KeywordsRequest,
    LemmasRequest,
    PatternOperationResponse,
    PhrasesRemoveRequest,
    PhrasesRequest,
    SeedRequest,
    SeedResponse,
)
from app.core.cache.domain_intent_cache import domain_intent_cache
from app.database.async_db import get_async_db
from app.repositories.domain_intent_repository import DomainIntentRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Domain Intents"])


# ============================================================
# HELPERS
# ============================================================


def _intent_to_response(intent) -> IntentResponse:
    """Convert DomainIntent to response schema."""
    return IntentResponse(
        id=str(intent.id),
        organization_id=str(intent.organization_id),
        domain_key=intent.domain_key,
        intent_key=intent.intent_key,
        name=intent.name,
        description=intent.description,
        weight=float(intent.weight) if intent.weight else 1.0,
        exact_match=intent.exact_match,
        is_enabled=intent.is_enabled,
        priority=intent.priority,
        lemmas=intent.lemmas,
        phrases=[
            {"phrase": p["phrase"], "match_type": p.get("match_type", "contains")}
            for p in intent.phrases
        ],
        confirmation_patterns=[
            {"pattern": c["pattern"], "pattern_type": c.get("pattern_type", "exact")}
            for c in intent.confirmation_patterns
        ],
        keywords=intent.keywords,
        created_at=intent.created_at.isoformat() if intent.created_at else None,
        updated_at=intent.updated_at.isoformat() if intent.updated_at else None,
    )


def _parse_org_id(organization_id: str) -> UUID:
    """Parse and validate organization_id string to UUID."""
    try:
        return UUID(organization_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid organization_id format: {e}",
        ) from e


def _parse_uuid(value: str, name: str = "id") -> UUID:
    """Parse and validate UUID string."""
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {name} format: {e}",
        ) from e


# ============================================================
# DOMAIN DISCOVERY ENDPOINTS
# ============================================================


@router.get("/domains", response_model=DomainListResponse)
async def list_domains(
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all domains with configured intents for an organization.

    Returns list of domain keys that have at least one intent configured.
    """
    org_uuid = _parse_org_id(organization_id)

    repo = DomainIntentRepository(db)
    domains = await repo.get_available_domains(org_uuid)

    return DomainListResponse(
        domains=domains,
        organization_id=organization_id,
    )


# ============================================================
# INTENT CRUD ENDPOINTS
# ============================================================


@router.get("/domains/{domain_key}/intents", response_model=IntentListResponse)
async def list_intents(
    domain_key: str = Path(..., description="Domain scope (e.g., pharmacy, excelencia)"),
    organization_id: str = Query(..., description="Organization UUID"),
    enabled_only: bool = Query(False, description="Only return enabled intents"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all intents for an organization and domain.

    Returns intents with all associated patterns (lemmas, phrases, etc.).
    """
    org_uuid = _parse_org_id(organization_id)

    repo = DomainIntentRepository(db)
    intents = await repo.find_all_intents(
        organization_id=org_uuid,
        domain_key=domain_key,
        enabled_only=enabled_only,
    )

    return IntentListResponse(
        intents=[_intent_to_response(i) for i in intents],
        total=len(intents),
        domain_key=domain_key,
    )


@router.post(
    "/domains/{domain_key}/intents",
    response_model=IntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_intent(
    data: IntentCreate,
    domain_key: str = Path(..., description="Domain scope"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new intent with optional patterns.

    Invalidates cache for the organization/domain after creation.
    """
    org_uuid = _parse_org_id(organization_id)

    repo = DomainIntentRepository(db)

    # Check if intent already exists
    existing = await repo.get_intent_by_key(org_uuid, domain_key, data.intent_key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intent '{data.intent_key}' already exists for domain '{domain_key}'",
        )

    # Prepare data dict
    intent_data = data.model_dump(exclude_unset=True)

    # Convert phrase models to dicts
    if intent_data.get("phrases"):
        intent_data["phrases"] = [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in intent_data["phrases"]
        ]
    if intent_data.get("confirmation_patterns"):
        intent_data["confirmation_patterns"] = [
            p.model_dump() if hasattr(p, "model_dump") else p
            for p in intent_data["confirmation_patterns"]
        ]

    intent = await repo.create_intent(org_uuid, domain_key, intent_data)

    # Invalidate cache
    await domain_intent_cache.invalidate(org_uuid, domain_key)
    logger.info(f"Created intent '{data.intent_key}' for org {org_uuid}, domain {domain_key}")

    return _intent_to_response(intent)


@router.get("/domains/{domain_key}/intents/{intent_id}", response_model=IntentResponse)
async def get_intent(
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific intent by ID."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)
    intent = await repo.get_intent_by_id(intent_uuid)

    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    # Verify domain matches
    if intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found in domain '{domain_key}'",
        )

    return _intent_to_response(intent)


@router.put("/domains/{domain_key}/intents/{intent_id}", response_model=IntentResponse)
async def update_intent(
    data: IntentUpdate,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update an intent's base fields.

    Use dedicated endpoints for managing patterns (lemmas, phrases, etc.).
    Invalidates cache after update.
    """
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    # Get current intent
    current = await repo.get_intent_by_id(intent_uuid)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    # Verify domain matches
    if current.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found in domain '{domain_key}'",
        )

    update_data = data.model_dump(exclude_unset=True)
    intent = await repo.update_intent(intent_uuid, update_data)

    # Invalidate cache
    await domain_intent_cache.invalidate(current.organization_id, domain_key)
    logger.info(f"Updated intent {intent_id}")

    return _intent_to_response(intent)


@router.delete(
    "/domains/{domain_key}/intents/{intent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_intent(
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete an intent and all its patterns.

    Cascades to delete all patterns.
    Invalidates cache after deletion.
    """
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    # Get current intent
    current = await repo.get_intent_by_id(intent_uuid)
    if not current:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    # Verify domain matches
    if current.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found in domain '{domain_key}'",
        )

    org_id = current.organization_id
    await repo.delete_intent(intent_uuid)

    # Invalidate cache
    await domain_intent_cache.invalidate(org_id, domain_key)
    logger.info(f"Deleted intent {intent_id}")


# ============================================================
# PATTERN MANAGEMENT ENDPOINTS
# ============================================================


@router.post(
    "/domains/{domain_key}/intents/{intent_id}/lemmas",
    response_model=PatternOperationResponse,
)
async def add_lemmas(
    data: LemmasRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Add lemmas to an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    count = await repo.add_lemmas(intent_uuid, data.lemmas)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Added {count} lemmas"
    )


@router.delete(
    "/domains/{domain_key}/intents/{intent_id}/lemmas",
    response_model=PatternOperationResponse,
)
async def remove_lemmas(
    data: LemmasRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove lemmas from an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    count = await repo.remove_lemmas(intent_uuid, data.lemmas)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Removed {count} lemmas"
    )


@router.post(
    "/domains/{domain_key}/intents/{intent_id}/phrases",
    response_model=PatternOperationResponse,
)
async def add_phrases(
    data: PhrasesRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Add phrases to an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    phrases_data = [p.model_dump() for p in data.phrases]
    count = await repo.add_phrases(intent_uuid, phrases_data)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Added {count} phrases"
    )


@router.delete(
    "/domains/{domain_key}/intents/{intent_id}/phrases",
    response_model=PatternOperationResponse,
)
async def remove_phrases(
    data: PhrasesRemoveRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove phrases from an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    count = await repo.remove_phrases(intent_uuid, data.phrases)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Removed {count} phrases"
    )


@router.post(
    "/domains/{domain_key}/intents/{intent_id}/confirmation",
    response_model=PatternOperationResponse,
)
async def add_confirmation_patterns(
    data: ConfirmationPatternsRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Add confirmation patterns to an intent (for confirm/reject)."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    patterns_data = [p.model_dump() for p in data.patterns]
    count = await repo.add_confirmation_patterns(intent_uuid, patterns_data)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Added {count} confirmation patterns"
    )


@router.delete(
    "/domains/{domain_key}/intents/{intent_id}/confirmation",
    response_model=PatternOperationResponse,
)
async def remove_confirmation_patterns(
    data: ConfirmationPatternsRemoveRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove confirmation patterns from an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    count = await repo.remove_confirmation_patterns(intent_uuid, data.patterns)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Removed {count} confirmation patterns"
    )


@router.post(
    "/domains/{domain_key}/intents/{intent_id}/keywords",
    response_model=PatternOperationResponse,
)
async def add_keywords(
    data: KeywordsRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Add keywords to an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    count = await repo.add_keywords(intent_uuid, data.keywords)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Added {count} keywords"
    )


@router.delete(
    "/domains/{domain_key}/intents/{intent_id}/keywords",
    response_model=PatternOperationResponse,
)
async def remove_keywords(
    data: KeywordsRequest,
    domain_key: str = Path(..., description="Domain scope"),
    intent_id: str = Path(..., description="Intent UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove keywords from an intent."""
    intent_uuid = _parse_uuid(intent_id, "intent_id")

    repo = DomainIntentRepository(db)

    intent = await repo.get_intent_by_id(intent_uuid)
    if not intent or intent.domain_key != domain_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intent not found: {intent_id}",
        )

    count = await repo.remove_keywords(intent_uuid, data.keywords)
    await domain_intent_cache.invalidate(intent.organization_id, domain_key)

    return PatternOperationResponse(
        success=True, count=count, message=f"Removed {count} keywords"
    )


# ============================================================
# UTILITY ENDPOINTS
# ============================================================


@router.post("/domains/{domain_key}/intents/seed", response_model=SeedResponse)
async def seed_intents(
    data: SeedRequest,
    domain_key: str = Path(..., description="Domain scope"),
    organization_id: str = Query(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Seed intents from hardcoded patterns for a specific domain.

    Migrates patterns from seed data to database for an organization.
    """
    org_uuid = _parse_org_id(organization_id)

    # Import seed data based on domain
    from app.scripts.seed_domain_intents import get_seed_data_for_domain

    seed_data = get_seed_data_for_domain(domain_key)
    if not seed_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No seed data available for domain '{domain_key}'",
        )

    repo = DomainIntentRepository(db)
    added = 0
    skipped = 0
    errors: list[str] = []

    for intent_key, pattern_data in seed_data.items():
        try:
            # Check if exists
            existing = await repo.get_intent_by_key(org_uuid, domain_key, intent_key)
            if existing:
                if data.overwrite:
                    await repo.delete_intent(existing.id)
                else:
                    skipped += 1
                    continue

            # Create intent
            intent_data = {
                "intent_key": intent_key,
                "name": pattern_data.get("name", intent_key.replace("_", " ").title()),
                "description": pattern_data.get("description", f"Auto-seeded intent: {intent_key}"),
                "weight": pattern_data.get("weight", 1.0),
                "exact_match": pattern_data.get("exact_match", False),
                "priority": pattern_data.get("priority", 50),
                "lemmas": pattern_data.get("lemmas", []),
                "phrases": pattern_data.get("phrases", []),
                "confirmation_patterns": pattern_data.get("confirmation_patterns", []),
                "keywords": pattern_data.get("keywords", []),
            }

            await repo.create_intent(org_uuid, domain_key, intent_data)
            added += 1

        except Exception as e:
            errors.append(f"{intent_key}: {e!s}")
            logger.warning(f"Error seeding intent {intent_key}: {e}")

    # Invalidate cache
    await domain_intent_cache.invalidate(org_uuid, domain_key)

    return SeedResponse(
        success=len(errors) == 0,
        domain_key=domain_key,
        added=added,
        skipped=skipped,
        errors=errors if errors else None,
    )


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def invalidate_cache(
    organization_id: str = Query(..., description="Organization UUID"),
    data: CacheInvalidateRequest | None = None,
):
    """
    Force cache invalidation.

    If domain_key is provided in body, invalidates only that domain's cache.
    Otherwise, invalidates all domains for the organization.
    """
    org_uuid = _parse_org_id(organization_id)

    if data and data.domain_key:
        await domain_intent_cache.invalidate(org_uuid, data.domain_key)
        return CacheInvalidateResponse(success=True, domains_invalidated=1)
    else:
        count = await domain_intent_cache.invalidate_all_domains(org_uuid)
        return CacheInvalidateResponse(success=True, domains_invalidated=count)


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """Get cache statistics for monitoring."""
    stats = domain_intent_cache.get_stats()
    return CacheStatsResponse(**stats)
