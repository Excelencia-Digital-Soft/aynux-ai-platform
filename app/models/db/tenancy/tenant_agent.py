# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Configuración de agentes por tenant. Habilitar/deshabilitar,
#              prioridad, keywords, intent_patterns, config personalizado.
# Tenant-Aware: Yes - organization_id FK, sobrescribe BUILTIN_AGENT_DEFAULTS.
# ============================================================================
"""
TenantAgent model - Per-tenant agent configuration.

Allows tenants to configure which agents are enabled, their settings,
and even register custom agents.
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class TenantAgent(Base, TimestampMixin):
    """
    Agent configuration for a tenant.

    Each tenant can:
    - Enable/disable built-in agents
    - Configure agent-specific settings
    - Register custom agents (via agent_class)

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations
        agent_key: Unique key for this agent within the tenant (e.g., "product_agent")
        agent_type: Type classification ("domain", "specialized", "custom")
        display_name: Human-readable name
        description: Description of what this agent does
        agent_class: Full Python class path for custom agents
        enabled: Whether this agent is active
        priority: Priority for routing (higher = preferred)
        domain_key: Associated domain (if domain agent)
        keywords: Keywords that trigger this agent
        intent_patterns: Patterns for intent matching
        config: Agent-specific configuration
    """

    __tablename__ = "tenant_agents"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique agent configuration identifier",
    )

    # Foreign key
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this agent belongs to",
    )

    # Agent identification
    agent_key = Column(
        String(100),
        nullable=False,
        comment="Unique key for this agent (e.g., 'product_agent')",
    )

    agent_type = Column(
        String(50),
        nullable=False,
        default="specialized",
        comment="Agent type: 'domain', 'specialized', 'custom'",
    )

    display_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable agent name",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Description of what this agent does",
    )

    # Custom agent class (for dynamic loading)
    agent_class = Column(
        String(255),
        nullable=True,
        comment="Full Python class path for custom agents (e.g., 'app.custom.MyAgent')",
    )

    # Status and routing
    enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this agent is active",
    )

    priority = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Priority for routing (higher = preferred)",
    )

    domain_key = Column(
        String(50),
        nullable=True,
        index=True,
        comment="Associated domain key (for domain agents)",
    )

    # Intent matching
    keywords = Column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="Keywords that trigger this agent",
    )

    intent_patterns = Column(
        JSONB,
        default=list,
        nullable=False,
        comment="Patterns for intent matching (e.g., [{pattern: '...', weight: 1.0}])",
    )

    # Agent-specific configuration
    config = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Agent-specific configuration (model, temperature, tools, etc.)",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="agents",
    )

    # Table configuration
    __table_args__ = (
        UniqueConstraint("organization_id", "agent_key", name="uq_org_agent_key"),
        Index("idx_tenant_agents_org_id", organization_id),
        Index("idx_tenant_agents_enabled", enabled),
        Index("idx_tenant_agents_domain_key", domain_key),
        Index("idx_tenant_agents_agent_type", agent_type),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<TenantAgent(org_id='{self.organization_id}', key='{self.agent_key}', enabled={self.enabled})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "agent_key": self.agent_key,
            "agent_type": self.agent_type,
            "display_name": self.display_name,
            "description": self.description,
            "agent_class": self.agent_class,
            "enabled": self.enabled,
            "priority": self.priority,
            "domain_key": self.domain_key,
            "keywords": self.keywords or [],
            "intent_patterns": self.intent_patterns or [],
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def is_builtin(self) -> bool:
        """Check if this is a built-in agent (no custom class)."""
        return self.agent_class is None

    @property
    def is_custom(self) -> bool:
        """Check if this is a custom agent."""
        return self.agent_class is not None

    @property
    def is_domain_agent(self) -> bool:
        """Check if this is a domain agent."""
        return bool(self.agent_type == "domain")

    @classmethod
    def create_builtin(
        cls,
        organization_id: uuid.UUID,
        agent_key: str,
        display_name: str,
        description: str | None = None,
        agent_type: str = "specialized",
        domain_key: str | None = None,
        keywords: list[str] | None = None,
        config: dict | None = None,
    ) -> "TenantAgent":
        """Factory method to create a built-in agent configuration."""
        return cls(
            organization_id=organization_id,
            agent_key=agent_key,
            display_name=display_name,
            description=description,
            agent_type=agent_type,
            domain_key=domain_key,
            keywords=keywords or [],
            config=config or {},
            enabled=True,
        )
