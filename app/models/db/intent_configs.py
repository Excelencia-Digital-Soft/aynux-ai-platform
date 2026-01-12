# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Intent configuration models for managing intent-to-agent mappings,
#              flow agents, and keyword-based routing.
# Tenant-Aware: Yes - each organization has isolated configurations.
# ============================================================================
"""
Intent Configuration Models - Database-driven intent routing configuration.

This module replaces the hardcoded values in intent_validator.py:
- IntentAgentMapping: Replaces AGENT_TO_INTENT_MAPPING dict
- FlowAgentConfig: Replaces FLOW_AGENTS set
- KeywordAgentMapping: Replaces KEYWORD_TO_AGENT dict

All configurations are multi-tenant, allowing each organization to customize
their intent routing behavior via the admin UI.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA

if TYPE_CHECKING:
    from .tenancy.organization import Organization


class IntentAgentMapping(Base, TimestampMixin):
    """
    Maps intents to target agents with configuration.

    Replaces the hardcoded AGENT_TO_INTENT_MAPPING in intent_validator.py.
    Each organization can define their own intent-to-agent mappings.

    Attributes:
        id: Unique identifier
        organization_id: Tenant that owns this mapping
        domain_key: Domain scope (NULL for global, 'pharmacy', 'excelencia', etc.)
        intent_key: Intent identifier (e.g., 'saludo', 'soporte')
        intent_name: Human-readable name
        intent_description: Description for documentation
        agent_key: Target agent key (e.g., 'greeting_agent')
        confidence_threshold: Minimum confidence to route (0.00-1.00)
        requires_handoff: Whether intent requires human handoff
        priority: Evaluation order (100 = first, 0 = last)
        is_enabled: Whether mapping is active
        examples: Example phrases for this intent (JSONB array)
        config: Additional configuration (JSONB)
    """

    __tablename__ = "intent_agent_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique mapping identifier",
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this mapping",
    )

    domain_key: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Domain scope: NULL (global), excelencia, pharmacy, etc.",
    )

    intent_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Intent identifier (e.g., 'saludo', 'soporte', 'excelencia')",
    )

    intent_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable intent name",
    )

    intent_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Intent description for documentation",
    )

    agent_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Target agent key (e.g., 'greeting_agent', 'support_agent')",
    )

    confidence_threshold: Mapped[float] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        default=0.75,
        comment="Minimum confidence to route (0.00-1.00)",
    )

    requires_handoff: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether intent requires human handoff",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="Evaluation priority (100 = highest, 0 = lowest)",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether mapping is active",
    )

    examples: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Example phrases for this intent",
    )

    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional configuration",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="intent_agent_mappings",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "domain_key",
            "intent_key",
            name="uq_intent_agent_mappings_org_domain_intent",
        ),
        CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="ck_intent_agent_mappings_priority_range",
        ),
        CheckConstraint(
            "confidence_threshold >= 0 AND confidence_threshold <= 1",
            name="ck_intent_agent_mappings_confidence_range",
        ),
        Index("idx_intent_agent_mappings_org", "organization_id"),
        Index("idx_intent_agent_mappings_org_domain", "organization_id", "domain_key"),
        Index("idx_intent_agent_mappings_enabled", "organization_id", "is_enabled"),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<IntentAgentMapping(intent='{self.intent_key}', agent='{self.agent_key}', org={self.organization_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "domain_key": self.domain_key,
            "intent_key": self.intent_key,
            "intent_name": self.intent_name,
            "intent_description": self.intent_description,
            "agent_key": self.agent_key,
            "confidence_threshold": float(self.confidence_threshold) if self.confidence_threshold else 0.75,
            "requires_handoff": self.requires_handoff,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "examples": self.examples or [],
            "config": self.config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FlowAgentConfig(Base, TimestampMixin):
    """
    Configures agents with multi-turn conversational flows.

    Replaces the hardcoded FLOW_AGENTS set in intent_validator.py.
    Flow agents continue handling a conversation until the flow completes,
    preventing routing away during multi-step workflows.

    Attributes:
        id: Unique identifier
        organization_id: Tenant that owns this config
        agent_key: Agent key (e.g., 'pharmacy_operations_agent')
        is_flow_agent: Whether agent has multi-turn flow
        flow_description: Description of the flow behavior
        max_turns: Maximum conversation turns in flow
        timeout_seconds: Flow timeout in seconds
        is_enabled: Whether config is active
        config: Additional flow configuration (JSONB)
    """

    __tablename__ = "flow_agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique flow config identifier",
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this config",
    )

    agent_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Agent key (e.g., 'pharmacy_operations_agent')",
    )

    is_flow_agent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether agent has multi-turn conversational flow",
    )

    flow_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Description of the flow behavior",
    )

    max_turns: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="Maximum conversation turns in flow",
    )

    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300,
        comment="Flow timeout in seconds",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether flow config is active",
    )

    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
        comment="Additional flow configuration",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="flow_agent_configs",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "agent_key",
            name="uq_flow_agent_configs_org_agent",
        ),
        CheckConstraint(
            "max_turns > 0 AND max_turns <= 100",
            name="ck_flow_agent_configs_max_turns_range",
        ),
        CheckConstraint(
            "timeout_seconds > 0 AND timeout_seconds <= 3600",
            name="ck_flow_agent_configs_timeout_range",
        ),
        Index("idx_flow_agent_configs_org", "organization_id"),
        Index("idx_flow_agent_configs_org_enabled", "organization_id", "is_enabled"),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<FlowAgentConfig(agent='{self.agent_key}', is_flow={self.is_flow_agent}, org={self.organization_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "agent_key": self.agent_key,
            "is_flow_agent": self.is_flow_agent,
            "flow_description": self.flow_description,
            "max_turns": self.max_turns,
            "timeout_seconds": self.timeout_seconds,
            "is_enabled": self.is_enabled,
            "config": self.config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class KeywordAgentMapping(Base):
    """
    Keyword-based fallback routing to agents.

    Replaces the hardcoded KEYWORD_TO_AGENT dict in intent_validator.py.
    Used when follow_up is detected but no previous agent exists,
    allowing keyword-based routing as a fallback.

    Attributes:
        id: Unique identifier
        organization_id: Tenant that owns this mapping
        agent_key: Target agent key
        keyword: Keyword or phrase to match
        match_type: How to match: exact, contains, prefix, regex
        case_sensitive: Whether match is case-sensitive
        priority: Evaluation priority (100 = highest)
        is_enabled: Whether keyword is active
    """

    __tablename__ = "keyword_agent_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique keyword mapping identifier",
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization that owns this mapping",
    )

    agent_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Target agent key",
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Keyword or phrase to match",
    )

    match_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="contains",
        comment="Match type: exact, contains, prefix, regex",
    )

    case_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether match is case-sensitive",
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="Evaluation priority (100 = highest)",
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether keyword is active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="keyword_agent_mappings",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "agent_key",
            "keyword",
            name="uq_keyword_agent_mappings_org_agent_keyword",
        ),
        CheckConstraint(
            "match_type IN ('exact', 'contains', 'prefix', 'regex')",
            name="ck_keyword_agent_mappings_match_type",
        ),
        CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="ck_keyword_agent_mappings_priority_range",
        ),
        Index("idx_keyword_agent_mappings_org", "organization_id"),
        Index("idx_keyword_agent_mappings_org_agent", "organization_id", "agent_key"),
        Index("idx_keyword_agent_mappings_keyword", "organization_id", "keyword"),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<KeywordAgentMapping(keyword='{self.keyword}', agent='{self.agent_key}', org={self.organization_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "agent_key": self.agent_key,
            "keyword": self.keyword,
            "match_type": self.match_type,
            "case_sensitive": self.case_sensitive,
            "priority": self.priority,
            "is_enabled": self.is_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
