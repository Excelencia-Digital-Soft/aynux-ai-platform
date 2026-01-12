# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic schemas for intent configuration API endpoints.
#              Manages intent-agent mappings, flow agents, and keyword routing.
# Tenant-Aware: Yes - schemas include organization_id for tenant context.
# ============================================================================
"""
Pydantic schemas for intent configuration API.

Replaces hardcoded values in intent_validator.py:
- IntentAgentMapping: AGENT_TO_INTENT_MAPPING
- FlowAgentConfig: FLOW_AGENTS
- KeywordAgentMapping: KEYWORD_TO_AGENT
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class MatchTypeEnum(str, Enum):
    """Match strategies for keyword patterns."""

    EXACT = "exact"
    CONTAINS = "contains"
    PREFIX = "prefix"
    REGEX = "regex"


# =============================================================================
# Intent Agent Mapping Schemas
# =============================================================================


class IntentAgentMappingCreate(BaseModel):
    """Schema for creating an intent-to-agent mapping."""

    intent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Intent key (e.g., 'saludo', 'soporte')",
    )
    intent_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable intent name",
    )
    intent_description: str | None = Field(
        None,
        max_length=1000,
        description="Intent description",
    )
    agent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Target agent key (e.g., 'greeting_agent')",
    )
    domain_key: str | None = Field(
        None,
        max_length=50,
        description="Domain scope: null (global), excelencia, pharmacy, etc.",
    )
    confidence_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to route (0.00-1.00)",
    )
    requires_handoff: bool = Field(
        default=False,
        description="Whether intent requires human handoff",
    )
    priority: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Evaluation priority (100 = highest)",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether mapping is active",
    )
    examples: list[str] = Field(
        default_factory=list,
        description="Example phrases for this intent",
    )


class IntentAgentMappingUpdate(BaseModel):
    """Schema for updating an intent-to-agent mapping."""

    intent_name: str | None = Field(None, min_length=1, max_length=255)
    intent_description: str | None = None
    agent_key: str | None = Field(None, min_length=1, max_length=100)
    domain_key: str | None = None
    confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    requires_handoff: bool | None = None
    priority: int | None = Field(None, ge=0, le=100)
    is_enabled: bool | None = None
    examples: list[str] | None = None


class IntentAgentMappingResponse(BaseModel):
    """Response schema for intent-to-agent mapping."""

    id: str
    organization_id: str
    domain_key: str | None
    intent_key: str
    intent_name: str
    intent_description: str | None
    agent_key: str
    confidence_threshold: float
    requires_handoff: bool
    priority: int
    is_enabled: bool
    examples: list[str]
    created_at: str | None
    updated_at: str | None


class IntentAgentMappingListResponse(BaseModel):
    """Response schema for list of mappings."""

    mappings: list[IntentAgentMappingResponse]
    total: int
    organization_id: str


# =============================================================================
# Flow Agent Config Schemas
# =============================================================================


class FlowAgentConfigCreate(BaseModel):
    """Schema for creating a flow agent configuration."""

    agent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Agent key (e.g., 'pharmacy_operations_agent')",
    )
    is_flow_agent: bool = Field(
        default=True,
        description="Whether agent has multi-turn flow",
    )
    flow_description: str | None = Field(
        None,
        max_length=500,
        description="Description of the flow behavior",
    )
    max_turns: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum conversation turns in flow",
    )
    timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Flow timeout in seconds",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether config is active",
    )


class FlowAgentConfigUpdate(BaseModel):
    """Schema for updating a flow agent configuration."""

    is_flow_agent: bool | None = None
    flow_description: str | None = None
    max_turns: int | None = Field(None, ge=1, le=100)
    timeout_seconds: int | None = Field(None, ge=1, le=3600)
    is_enabled: bool | None = None


class FlowAgentConfigResponse(BaseModel):
    """Response schema for flow agent configuration."""

    id: str
    organization_id: str
    agent_key: str
    is_flow_agent: bool
    flow_description: str | None
    max_turns: int
    timeout_seconds: int
    is_enabled: bool
    created_at: str | None
    updated_at: str | None


class FlowAgentConfigListResponse(BaseModel):
    """Response schema for list of flow agent configs."""

    configs: list[FlowAgentConfigResponse]
    total: int
    organization_id: str


# =============================================================================
# Keyword Agent Mapping Schemas
# =============================================================================


class KeywordAgentMappingCreate(BaseModel):
    """Schema for creating a keyword-to-agent mapping."""

    agent_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Target agent key",
    )
    keyword: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Keyword or phrase to match",
    )
    match_type: MatchTypeEnum = Field(
        default=MatchTypeEnum.CONTAINS,
        description="Match type: exact, contains, prefix, regex",
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether match is case-sensitive",
    )
    priority: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Evaluation priority (100 = highest)",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether keyword is active",
    )


class KeywordAgentMappingBulkCreate(BaseModel):
    """Schema for bulk creating keyword mappings."""

    agent_key: str = Field(..., min_length=1, max_length=100)
    keywords: list[str] = Field(..., min_length=1, description="List of keywords to add")
    match_type: MatchTypeEnum = Field(default=MatchTypeEnum.CONTAINS)
    case_sensitive: bool = Field(default=False)
    priority: int = Field(default=50, ge=0, le=100)


class KeywordAgentMappingResponse(BaseModel):
    """Response schema for keyword-to-agent mapping."""

    id: str
    organization_id: str
    agent_key: str
    keyword: str
    match_type: str
    case_sensitive: bool
    priority: int
    is_enabled: bool
    created_at: str | None


class KeywordAgentMappingListResponse(BaseModel):
    """Response schema for list of keyword mappings."""

    mappings: list[KeywordAgentMappingResponse]
    total: int
    organization_id: str


# =============================================================================
# Testing Schemas
# =============================================================================


class IntentTestRequest(BaseModel):
    """Request schema for testing intent detection."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Message to test",
    )
    domain_key: str | None = Field(
        None,
        description="Optional domain filter",
    )


class IntentTestResult(BaseModel):
    """Result of intent detection test."""

    detected_intent: str
    confidence: float
    target_agent: str
    method: str  # 'mapping', 'keyword', 'flow_continuation'
    reasoning: str
    matched_keywords: list[str]
    is_flow_agent: bool


class IntentTestResponse(BaseModel):
    """Response schema for intent test."""

    result: IntentTestResult
    organization_id: str


# =============================================================================
# Visualization Schemas
# =============================================================================


class FlowNode(BaseModel):
    """Node for flow visualization."""

    id: str
    type: str  # 'intent', 'agent', 'keyword'
    label: str
    data: dict


class FlowEdge(BaseModel):
    """Edge for flow visualization."""

    id: str
    source: str
    target: str
    label: str | None = None


class FlowVisualizationResponse(BaseModel):
    """Response schema for flow visualization data."""

    nodes: list[FlowNode]
    edges: list[FlowEdge]
    organization_id: str


# =============================================================================
# Seed and Cache Schemas
# =============================================================================


class SeedRequest(BaseModel):
    """Request schema for seeding default configurations."""

    overwrite: bool = Field(
        default=False,
        description="Overwrite existing configurations",
    )


class SeedResponse(BaseModel):
    """Response schema for seed operation."""

    mappings_created: int
    flow_agents_created: int
    keywords_created: int
    organization_id: str


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
    cached_organizations: int


class CacheInvalidateResponse(BaseModel):
    """Response schema for cache invalidation."""

    success: bool
    organization_id: str
    message: str


# =============================================================================
# Combined Config Schemas
# =============================================================================


class AllConfigsResponse(BaseModel):
    """Response schema for all configurations."""

    intent_mappings: list[IntentAgentMappingResponse]
    flow_agents: list[FlowAgentConfigResponse]
    keyword_mappings: list[KeywordAgentMappingResponse]
    organization_id: str
