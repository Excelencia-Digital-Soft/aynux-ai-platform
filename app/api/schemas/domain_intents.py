# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Pydantic schemas for unified domain intent patterns API endpoints.
# Tenant-Aware: Yes - schemas include organization_id for tenant context.
# Domain-Aware: Yes - schemas include domain_key for domain isolation.
# ============================================================================
"""
Pydantic schemas for domain intent patterns API.

Supports multiple domains: pharmacy, excelencia, ecommerce, healthcare, etc.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class PatternTypeEnum(str, Enum):
    """Types of patterns that can be associated with an intent."""

    LEMMA = "lemma"
    PHRASE = "phrase"
    CONFIRMATION = "confirmation"
    KEYWORD = "keyword"


class MatchTypeEnum(str, Enum):
    """Match strategies for phrase and confirmation patterns."""

    EXACT = "exact"
    CONTAINS = "contains"
    PREFIX = "prefix"


# =============================================================================
# Nested Pattern Schemas
# =============================================================================


class PhraseCreate(BaseModel):
    """Schema for creating a phrase pattern."""

    phrase: str = Field(..., min_length=1, max_length=500, description="Phrase to match")
    match_type: MatchTypeEnum = Field(
        default=MatchTypeEnum.CONTAINS,
        description="Match type: exact, contains, prefix",
    )


class ConfirmationPatternCreate(BaseModel):
    """Schema for creating a confirmation pattern."""

    pattern: str = Field(..., min_length=1, max_length=100, description="Pattern string")
    pattern_type: MatchTypeEnum = Field(
        ...,
        description="Pattern type: exact or contains",
    )


class PatternCreate(BaseModel):
    """Generic schema for creating any type of pattern."""

    pattern_type: PatternTypeEnum = Field(..., description="Type of pattern")
    pattern_value: str = Field(..., min_length=1, max_length=500, description="Pattern string")
    match_type: MatchTypeEnum | None = Field(
        None, description="Match type (required for phrase/confirmation)"
    )
    priority: int = Field(default=0, ge=0, le=100, description="Pattern priority")


# =============================================================================
# Intent CRUD Schemas
# =============================================================================


class IntentCreate(BaseModel):
    """Schema for creating a new domain intent."""

    intent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique intent key (e.g., 'debt_query', 'confirm')",
    )
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable name")
    description: str | None = Field(None, max_length=1000, description="Intent description")
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


# =============================================================================
# Response Schemas
# =============================================================================


class PhraseResponse(BaseModel):
    """Schema for phrase pattern response."""

    phrase: str
    match_type: str

    model_config = {"from_attributes": True}


class ConfirmationPatternResponse(BaseModel):
    """Schema for confirmation pattern response."""

    pattern: str
    pattern_type: str

    model_config = {"from_attributes": True}


class PatternResponse(BaseModel):
    """Schema for generic pattern response."""

    id: str
    intent_id: str
    pattern_type: str
    pattern_value: str
    match_type: str | None
    priority: int

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


class IntentListResponse(BaseModel):
    """Schema for paginated intent list."""

    intents: list[IntentResponse]
    total: int
    domain_key: str


class DomainListResponse(BaseModel):
    """Schema for list of available domains."""

    domains: list[str]
    organization_id: str


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


class PatternsRequest(BaseModel):
    """Generic schema for adding patterns of any type."""

    patterns: list[PatternCreate] = Field(
        ..., min_length=1, description="List of patterns to add"
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

    overwrite: bool = Field(
        default=False,
        description="If True, overwrite existing intents. If False, skip existing.",
    )


class SeedResponse(BaseModel):
    """Schema for seed operation result."""

    success: bool
    domain_key: str
    added: int
    skipped: int
    errors: list[str] | None = None


class CacheInvalidateRequest(BaseModel):
    """Schema for cache invalidation request."""

    domain_key: str | None = Field(
        default=None,
        description="Domain to invalidate. If None, invalidate all domains for org.",
    )


class CacheInvalidateResponse(BaseModel):
    """Schema for cache invalidation result."""

    success: bool
    domains_invalidated: int


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
    cached_entries: int
