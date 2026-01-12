# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic schemas for pharmacy intent patterns API endpoints.
# Tenant-Aware: Yes - schemas include organization_id for tenant context.
# ============================================================================
"""Pydantic schemas for pharmacy intent patterns API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# =============================================================================
# Nested Pattern Schemas
# =============================================================================


class PhraseCreate(BaseModel):
    """Schema for creating a phrase pattern."""

    phrase: str = Field(..., min_length=1, max_length=500, description="Phrase to match")
    match_type: str = Field(
        default="contains",
        description="Match type: exact, contains, prefix",
        pattern="^(exact|contains|prefix)$",
    )


class ConfirmationPatternCreate(BaseModel):
    """Schema for creating a confirmation pattern."""

    pattern: str = Field(..., min_length=1, max_length=100, description="Pattern string")
    pattern_type: str = Field(
        ...,
        description="Pattern type: exact or contains",
        pattern="^(exact|contains)$",
    )


# =============================================================================
# Intent CRUD Schemas
# =============================================================================


class IntentCreate(BaseModel):
    """Schema for creating a new pharmacy intent."""

    organization_id: str = Field(..., description="Organization UUID")
    intent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique intent key (e.g., 'debt_query', 'confirm')",
    )
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name")
    description: str | None = Field(None, max_length=1000, description="Intent description")
    domain_key: str = Field(default="pharmacy", max_length=50, description="Domain scope")
    weight: float = Field(
        default=1.0, ge=0.0, le=2.0, description="Scoring weight multiplier"
    )
    exact_match: bool = Field(
        default=False, description="Require exact phrase match (for confirm/reject)"
    )
    is_enabled: bool = Field(default=True, description="Whether intent is active")
    priority: int = Field(
        default=50, ge=0, le=100, description="Evaluation order (100 = first)"
    )

    # Optional initial patterns
    lemmas: list[str] | None = Field(
        default=None, description="List of word lemmas for spaCy matching"
    )
    phrases: list[PhraseCreate] | None = Field(
        default=None, description="List of phrase patterns"
    )
    confirmation_patterns: list[ConfirmationPatternCreate] | None = Field(
        default=None, description="List of confirmation patterns (for confirm/reject)"
    )
    keywords: list[str] | None = Field(
        default=None, description="List of fallback keywords"
    )


class IntentUpdate(BaseModel):
    """Schema for updating an existing intent (partial update)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    weight: float | None = Field(None, ge=0.0, le=2.0)
    exact_match: bool | None = None
    is_enabled: bool | None = None
    priority: int | None = Field(None, ge=0, le=100)


class PhraseResponse(BaseModel):
    """Schema for phrase pattern response."""

    phrase: str
    match_type: str

    class Config:
        from_attributes = True


class ConfirmationPatternResponse(BaseModel):
    """Schema for confirmation pattern response."""

    pattern: str
    pattern_type: str

    class Config:
        from_attributes = True


class IntentResponse(BaseModel):
    """Schema for intent response with all patterns."""

    id: str
    organization_id: str
    domain_key: str
    intent_key: str
    name: str
    description: str | None
    weight: float
    exact_match: bool
    is_enabled: bool
    priority: int
    lemmas: list[str]
    phrases: list[PhraseResponse]
    confirmation_patterns: list[ConfirmationPatternResponse]
    keywords: list[str]
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class IntentListResponse(BaseModel):
    """Schema for paginated intent list."""

    intents: list[IntentResponse]
    total: int


# =============================================================================
# Pattern Management Schemas
# =============================================================================


class LemmasRequest(BaseModel):
    """Schema for adding/removing lemmas."""

    lemmas: list[str] = Field(
        ..., min_length=1, description="List of lemma strings"
    )


class PhrasesRequest(BaseModel):
    """Schema for adding phrases."""

    phrases: list[PhraseCreate] = Field(
        ..., min_length=1, description="List of phrase patterns"
    )


class PhrasesRemoveRequest(BaseModel):
    """Schema for removing phrases."""

    phrases: list[str] = Field(
        ..., min_length=1, description="List of phrase strings to remove"
    )


class ConfirmationPatternsRequest(BaseModel):
    """Schema for adding/removing confirmation patterns."""

    patterns: list[ConfirmationPatternCreate] = Field(
        ..., min_length=1, description="List of confirmation patterns"
    )


class KeywordsRequest(BaseModel):
    """Schema for adding/removing keywords."""

    keywords: list[str] = Field(
        ..., min_length=1, description="List of keyword strings"
    )


class PatternOperationResponse(BaseModel):
    """Schema for pattern operation result."""

    success: bool
    count: int = Field(description="Number of patterns affected")
    message: str | None = None


# =============================================================================
# Utility Schemas
# =============================================================================


class SeedRequest(BaseModel):
    """Schema for seeding intents from hardcoded patterns."""

    organization_id: str = Field(..., description="Organization UUID to seed patterns for")
    overwrite: bool = Field(
        default=False,
        description="If True, overwrite existing intents. If False, skip existing.",
    )


class SeedResponse(BaseModel):
    """Schema for seed operation result."""

    success: bool
    added: int
    skipped: int
    errors: list[str] | None = None


class CacheInvalidateRequest(BaseModel):
    """Schema for cache invalidation request."""

    organization_id: str | None = Field(
        default=None,
        description="Organization UUID to invalidate. If None, invalidate all.",
    )


class CacheInvalidateResponse(BaseModel):
    """Schema for cache invalidation result."""

    success: bool
    organizations_invalidated: int


class CacheStatsResponse(BaseModel):
    """Schema for cache statistics."""

    memory_hits: int
    memory_misses: int
    memory_hit_rate: float
    redis_hits: int
    redis_misses: int
    redis_hit_rate: float
    db_loads: int
    invalidations: int
    cached_organizations: int
