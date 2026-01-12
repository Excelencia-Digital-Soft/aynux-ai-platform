# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Pydantic schemas for response configs API endpoints. Generic
#              design supports pharmacy domain now and other domains later.
# Tenant-Aware: Yes - schemas include organization_id for tenant context.
# Domain-Aware: Yes - schemas include domain_key for domain scope.
# ============================================================================
"""
Pydantic schemas for response configs API.

Generic schemas for multi-domain response configuration:
- is_critical: Whether intent uses fixed templates (never LLM)
- task_description: Task description for LLM system prompt
- fallback_template_key: Key in fallback_templates.yaml

Currently used by: pharmacy domain
Future domains: healthcare, ecommerce, credit, etc.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# =============================================================================
# Create/Update Schemas
# =============================================================================


class ResponseConfigCreate(BaseModel):
    """Schema for creating a new response configuration."""

    organization_id: str = Field(..., description="Organization UUID")
    domain_key: str = Field(
        default="pharmacy",
        max_length=50,
        description="Domain scope (pharmacy, healthcare, ecommerce, etc.)",
    )
    intent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique intent key (e.g., 'greeting', 'payment_confirmation')",
    )

    # Core configuration
    is_critical: bool = Field(
        default=False,
        description="If True, always uses fixed template from critical_templates.yaml, never LLM",
    )
    task_description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Task description injected into LLM system prompt",
    )
    fallback_template_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Key in fallback_templates.yaml for when LLM fails",
    )

    # Display metadata
    display_name: str | None = Field(
        None,
        max_length=200,
        description="Human-readable configuration name",
    )
    description: str | None = Field(
        None,
        max_length=1000,
        description="Configuration description and usage notes",
    )

    # Status and ordering
    priority: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Display/processing order (higher = first)",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether configuration is active",
    )


class ResponseConfigUpdate(BaseModel):
    """Schema for updating an existing response configuration (partial update)."""

    # Core configuration (all optional for partial update)
    is_critical: bool | None = Field(
        None,
        description="If True, always uses fixed template, never LLM",
    )
    task_description: str | None = Field(
        None,
        min_length=1,
        max_length=2000,
        description="Task description for LLM system prompt",
    )
    fallback_template_key: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Key in fallback_templates.yaml",
    )

    # Display metadata
    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=1000)

    # Status and ordering
    priority: int | None = Field(None, ge=0, le=1000)
    is_enabled: bool | None = None


# =============================================================================
# Response Schemas
# =============================================================================


class ResponseConfigResponse(BaseModel):
    """Schema for response configuration response."""

    id: str
    organization_id: str
    domain_key: str
    intent_key: str
    is_critical: bool
    task_description: str
    fallback_template_key: str
    display_name: str | None
    description: str | None
    priority: int
    is_enabled: bool
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class ResponseConfigListResponse(BaseModel):
    """Schema for paginated response config list."""

    configs: list[ResponseConfigResponse]
    total: int
    domain_key: str = Field(description="Domain scope for this list")


# =============================================================================
# Bulk Operations Schemas
# =============================================================================


class ResponseConfigBulkCreate(BaseModel):
    """Schema for bulk creating response configurations."""

    organization_id: str = Field(..., description="Organization UUID")
    domain_key: str = Field(
        default="pharmacy",
        max_length=50,
        description="Domain scope",
    )
    configs: list[ResponseConfigCreateItem] = Field(
        ...,
        min_length=1,
        description="List of configurations to create",
    )


class ResponseConfigCreateItem(BaseModel):
    """Single item for bulk creation (without org_id/domain_key)."""

    intent_key: str = Field(..., min_length=1, max_length=100)
    is_critical: bool = Field(default=False)
    task_description: str = Field(..., min_length=1, max_length=2000)
    fallback_template_key: str = Field(..., min_length=1, max_length=100)
    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=1000)
    priority: int = Field(default=0, ge=0, le=1000)
    is_enabled: bool = Field(default=True)


# Fix forward reference
ResponseConfigBulkCreate.model_rebuild()


class BulkOperationResponse(BaseModel):
    """Schema for bulk operation result."""

    success: bool
    created: int = Field(description="Number of configs created")
    skipped: int = Field(description="Number of configs skipped (already exist)")
    errors: list[str] | None = Field(
        None,
        description="List of error messages if any",
    )


# =============================================================================
# Seed Schemas
# =============================================================================


class SeedResponseConfigsRequest(BaseModel):
    """Schema for seeding response configs from default data."""

    organization_id: str = Field(
        ...,
        description="Organization UUID to seed configs for",
    )
    domain_key: str = Field(
        default="pharmacy",
        max_length=50,
        description="Domain to seed configs for",
    )
    overwrite: bool = Field(
        default=False,
        description="If True, delete existing configs before seeding. If False, skip existing.",
    )


class SeedResponseConfigsResponse(BaseModel):
    """Schema for seed operation result."""

    success: bool
    added: int
    skipped: int
    total_available: int = Field(description="Total configs available in seed data")
    errors: list[str] | None = None


# =============================================================================
# Cache Management Schemas
# =============================================================================


class CacheInvalidateRequest(BaseModel):
    """Schema for cache invalidation request."""

    organization_id: str | None = Field(
        default=None,
        description="Organization UUID to invalidate. If None, invalidate all.",
    )
    domain_key: str | None = Field(
        default=None,
        description="Domain to invalidate. If None with org_id, invalidates all domains for that org.",
    )


class CacheInvalidateResponse(BaseModel):
    """Schema for cache invalidation result."""

    success: bool
    organizations_invalidated: int
    message: str | None = None


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


class CacheWarmRequest(BaseModel):
    """Schema for cache warming request."""

    organization_id: str = Field(..., description="Organization UUID to warm cache for")
    domain_key: str = Field(default="pharmacy", description="Domain to warm cache for")


class CacheWarmResponse(BaseModel):
    """Schema for cache warming result."""

    success: bool
    configs_loaded: int
    message: str | None = None


# =============================================================================
# Domain Info Schemas (for multi-domain discovery)
# =============================================================================


class DomainInfo(BaseModel):
    """Information about a domain's response config status."""

    domain_key: str
    total_configs: int
    enabled_configs: int
    critical_configs: int


class DomainListResponse(BaseModel):
    """List of domains with response configs for an organization."""

    organization_id: str
    domains: list[DomainInfo]


__all__ = [
    # Create/Update
    "ResponseConfigCreate",
    "ResponseConfigUpdate",
    # Response
    "ResponseConfigResponse",
    "ResponseConfigListResponse",
    # Bulk
    "ResponseConfigBulkCreate",
    "ResponseConfigCreateItem",
    "BulkOperationResponse",
    # Seed
    "SeedResponseConfigsRequest",
    "SeedResponseConfigsResponse",
    # Cache
    "CacheInvalidateRequest",
    "CacheInvalidateResponse",
    "CacheStatsResponse",
    "CacheWarmRequest",
    "CacheWarmResponse",
    # Domain
    "DomainInfo",
    "DomainListResponse",
]
