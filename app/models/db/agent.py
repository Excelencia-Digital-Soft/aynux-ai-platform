# ============================================================================
# SCOPE: GLOBAL
# Description: Registro global de agentes disponibles. Define el catálogo de
#              agentes con sus configuraciones por defecto. Los agentes pueden
#              ser builtin (sistema) o custom (definidos por usuario).
# Tenant-Aware: No - agentes disponibles globalmente, habilitación controlada
#               por is_enabled. Per-tenant overrides via tenant_agents table.
# ============================================================================
"""
Agent model - Global agent registry for dynamic agent management.

Stores metadata about available agents in the system:
- Builtin agents (greeting, support, fallback, etc.)
- Domain-specific agents (excelencia, ecommerce, pharmacy, etc.)
- Custom agents (user-defined)

Agents can be seeded from BUILTIN_AGENT_DEFAULTS or created manually.
Administrators control visibility via enabled flag.
"""

import uuid
from enum import Enum

from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class AgentType(str, Enum):
    """Agent classification type."""

    BUILTIN = "builtin"
    SPECIALIZED = "specialized"
    SUPERVISOR = "supervisor"
    ORCHESTRATOR = "orchestrator"
    CUSTOM = "custom"


class Agent(Base, TimestampMixin):
    """
    Agent registry entry.

    Stores information about available agents in the system.
    Serves as the global catalog that can be overridden per-tenant
    via the tenant_agents table.

    Attributes:
        id: Unique identifier
        agent_key: Unique agent identifier (e.g., "greeting_agent", "support_agent")
        name: Human-readable display name
        description: Agent description and purpose
        agent_type: Classification (builtin, specialized, custom, etc.)
        domain_key: Associated domain (None for global agents)
        enabled: Whether agent is enabled globally
        priority: Routing priority (100 = highest, 0 = lowest)
        keywords: Keywords for intent matching
        intent_patterns: Patterns with weights for routing (JSONB)
        config: Agent-specific configuration (JSONB)
        sync_source: How this agent was added (seed, manual)
    """

    __tablename__ = "agents"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique agent identifier",
    )

    # Agent identification
    agent_key = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="Unique agent key (e.g., 'greeting_agent', 'support_agent')",
    )

    # Display information
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for UI display",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Agent description and purpose",
    )

    # Classification
    agent_type = Column(
        String(50),
        nullable=False,
        default="builtin",
        comment="Agent type: builtin, specialized, supervisor, orchestrator, custom",
    )

    # Domain association
    domain_key = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Associated domain: None (global), excelencia, ecommerce, pharmacy, credit, etc.",
    )

    # Status and ordering
    enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether agent is enabled globally",
    )

    priority = Column(
        Integer,
        default=50,
        nullable=False,
        comment="Routing priority (100 = highest, 0 = lowest)",
    )

    # Intent matching
    keywords = Column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="Keywords for intent matching",
    )

    intent_patterns = Column(
        JSONB,
        default=list,
        nullable=False,
        comment="Intent patterns with weights: [{pattern: str, weight: float}]",
    )

    # Flexible configuration
    config = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Agent-specific configuration",
    )

    # Sync tracking
    sync_source = Column(
        String(50),
        default="seed",
        nullable=False,
        comment="How agent was added: seed, manual",
    )

    # Table configuration
    __table_args__ = (
        Index("idx_agents_agent_type", agent_type),
        Index("idx_agents_domain_key", domain_key),
        Index("idx_agents_enabled", enabled),
        Index("idx_agents_priority", priority),
        Index("idx_agents_enabled_priority", enabled, priority.desc()),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<Agent(agent_key='{self.agent_key}', type='{self.agent_type}', enabled={self.enabled})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "agent_key": self.agent_key,
            "name": self.name,
            "description": self.description,
            "agent_type": self.agent_type,
            "domain_key": self.domain_key,
            "enabled": self.enabled,
            "priority": self.priority,
            "keywords": self.keywords or [],
            "intent_patterns": self.intent_patterns or [],
            "config": self.config or {},
            "sync_source": self.sync_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_config_dict(self) -> dict:
        """Convert to configuration dictionary for agent initialization."""
        return {
            "agent_key": self.agent_key,
            "agent_type": self.agent_type,
            "display_name": self.name,
            "description": self.description,
            "priority": self.priority,
            "domain_key": self.domain_key,
            "keywords": self.keywords or [],
            "intent_patterns": self.intent_patterns or [],
            "config": self.config or {},
            "enabled": self.enabled,
        }

    @classmethod
    def from_builtin_defaults(cls, agent_key: str, defaults: dict) -> "Agent":
        """
        Factory method to create Agent from BUILTIN_AGENT_DEFAULTS entry.

        Args:
            agent_key: The agent key (e.g., "greeting_agent")
            defaults: Configuration dict from BUILTIN_AGENT_DEFAULTS

        Returns:
            New Agent instance (not saved to DB)
        """
        return cls(
            agent_key=agent_key,
            name=defaults.get("display_name", agent_key),
            description=defaults.get("description"),
            agent_type=defaults.get("agent_type", "builtin"),
            domain_key=defaults.get("domain_key"),
            enabled=True,  # Default to enabled when seeding
            priority=defaults.get("priority", 50),
            keywords=defaults.get("keywords", []),
            intent_patterns=defaults.get("intent_patterns", []),
            config=defaults.get("config", {}),
            sync_source="seed",
        )
