"""
Tenant Agent Configuration Schema.

Runtime configuration models for tenant-specific agent configuration.
These models represent the agent configuration loaded from database,
merged with builtin defaults.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class IntentPattern(BaseModel):
    """
    A pattern for intent matching.

    Attributes:
        pattern: The intent pattern string (e.g., "producto", "saludo")
        weight: Weight for scoring when multiple patterns match (0.0-1.0)
        requires_context: Whether this pattern requires conversation context
    """

    pattern: str
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    requires_context: bool = False


class AgentConfig(BaseModel):
    """
    Configuration for a single agent.

    This model represents the runtime configuration for an agent,
    loaded from database and merged with builtin defaults.

    Attributes:
        id: Database ID (if persisted)
        agent_key: Unique key for the agent (e.g., "greeting_agent")
        agent_type: Type of agent ("builtin" or "custom")
        display_name: Human-readable name
        description: Agent description
        agent_class: Python class path for custom agents
        enabled: Whether the agent is enabled
        priority: Routing priority (higher = checked first)
        domain_key: Associated domain (e.g., "ecommerce", "healthcare")
        keywords: Keywords for intent matching
        intent_patterns: Patterns for intent routing
        config: Agent-specific configuration (prompts, model settings, etc.)
    """

    id: UUID | None = None
    agent_key: str
    agent_type: str = Field(default="builtin", pattern="^(builtin|custom|domain|specialized)$")
    display_name: str
    description: str | None = None
    agent_class: str | None = None  # For custom agents: "app.agents.custom.MyAgent"
    enabled: bool = True
    priority: int = Field(default=50, ge=0, le=100)
    domain_key: str | None = None
    keywords: list[str] = Field(default_factory=list)
    intent_patterns: list[IntentPattern] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class TenantAgentRegistry(BaseModel):
    """
    Complete agent registry for a tenant.

    This model holds all agent configurations for a specific tenant,
    along with computed indexes for efficient routing.

    Attributes:
        organization_id: The tenant's organization ID
        agents: Dict of agent_key -> AgentConfig
        intent_to_agent: Computed mapping of intent -> agent_key
        keyword_index: Computed mapping of keyword -> [agent_keys]
    """

    organization_id: UUID
    agents: dict[str, AgentConfig] = Field(default_factory=dict)

    # Computed indexes (populated automatically via model_validator)
    intent_to_agent: dict[str, str] = Field(default_factory=dict)
    keyword_index: dict[str, list[str]] = Field(default_factory=dict)

    # Bypass routing (set when a bypass rule matches before normal routing)
    bypass_target_agent: str | None = Field(
        default=None,
        description="Agent to route to directly when bypass rule matches"
    )

    @model_validator(mode="after")
    def _build_indexes(self) -> "TenantAgentRegistry":
        """Build indexes after model creation."""
        self.rebuild_indexes()
        return self

    def get_enabled_agents(self) -> list[AgentConfig]:
        """Get list of enabled agents sorted by priority (desc)."""
        enabled = [a for a in self.agents.values() if a.enabled]
        return sorted(enabled, key=lambda a: a.priority, reverse=True)

    def get_agent(self, agent_key: str) -> AgentConfig | None:
        """Get agent configuration by key."""
        return self.agents.get(agent_key)

    def is_agent_enabled(self, agent_key: str) -> bool:
        """Check if an agent is enabled."""
        agent = self.agents.get(agent_key)
        return agent.enabled if agent else False

    def get_agents_for_domain(self, domain_key: str) -> list[AgentConfig]:
        """Get all enabled agents for a specific domain."""
        return [
            a
            for a in self.agents.values()
            if a.enabled and a.domain_key == domain_key
        ]

    def get_agent_for_intent(self, intent: str) -> str | None:
        """Get the agent key for a given intent."""
        return self.intent_to_agent.get(intent)

    def get_agents_for_keyword(self, keyword: str) -> list[str]:
        """Get agent keys that match a keyword."""
        keyword_lower = keyword.lower()
        return self.keyword_index.get(keyword_lower, [])

    def rebuild_indexes(self) -> None:
        """Rebuild intent and keyword indexes from agent configurations."""
        self.intent_to_agent.clear()
        self.keyword_index.clear()

        for agent in self.get_enabled_agents():
            # Build intent index
            for pattern in agent.intent_patterns:
                # Higher priority agent takes precedence
                if pattern.pattern not in self.intent_to_agent:
                    self.intent_to_agent[pattern.pattern] = agent.agent_key

            # Build keyword index
            for keyword in agent.keywords:
                keyword_lower = keyword.lower()
                if keyword_lower not in self.keyword_index:
                    self.keyword_index[keyword_lower] = []
                if agent.agent_key not in self.keyword_index[keyword_lower]:
                    self.keyword_index[keyword_lower].append(agent.agent_key)


class AgentConfigUpdate(BaseModel):
    """
    Schema for updating agent configuration.

    All fields are optional - only provided fields will be updated.
    """

    display_name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    keywords: list[str] | None = None
    intent_patterns: list[IntentPattern] | None = None
    config: dict[str, Any] | None = None


class AgentConfigCreate(BaseModel):
    """
    Schema for creating a new custom agent.
    """

    agent_key: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    agent_class: str | None = None  # Required for custom agents
    enabled: bool = True
    priority: int = Field(default=50, ge=0, le=100)
    domain_key: str | None = None
    keywords: list[str] = Field(default_factory=list)
    intent_patterns: list[IntentPattern] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "IntentPattern",
    "AgentConfig",
    "TenantAgentRegistry",
    "AgentConfigUpdate",
    "AgentConfigCreate",
]
