"""
TenantConfig model - Per-tenant configuration.

Stores detailed configuration for each tenant including:
- Enabled domains and agents
- RAG settings
- Prompt scope
- WhatsApp integration settings
"""

import uuid

from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class TenantConfig(Base, TimestampMixin):
    """
    Detailed configuration for a tenant.

    One-to-one relationship with Organization.
    Contains all configurable settings for the tenant's system behavior.

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations (unique)
        enabled_domains: List of enabled domain keys
        default_domain: Default domain for routing
        enabled_agent_types: List of enabled agent keys
        agent_timeout_seconds: Timeout for agent operations
        rag_enabled: Whether RAG is enabled
        rag_similarity_threshold: Minimum similarity for RAG results
        rag_max_results: Maximum results from RAG search
        prompt_scope: Prompt resolution scope ("system", "global", "org")
        whatsapp_phone_number_id: WhatsApp Business phone number ID
        whatsapp_verify_token: Webhook verification token
        advanced_config: Additional configuration (JSONB)
    """

    __tablename__ = "tenant_configs"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier",
    )

    # Foreign key (one-to-one with organization)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="Organization this config belongs to",
    )

    # Domain configuration
    enabled_domains = Column(
        ARRAY(String),
        default=["excelencia"],
        nullable=False,
        comment="List of enabled domain keys (e.g., ['ecommerce', 'healthcare'])",
    )

    default_domain = Column(
        String(50),
        default="excelencia",
        nullable=False,
        comment="Default domain for routing when intent is unclear",
    )

    # Agent configuration
    enabled_agent_types = Column(
        ARRAY(String),
        default=list,
        nullable=False,
        comment="List of enabled agent keys (empty = all builtin)",
    )

    agent_timeout_seconds = Column(
        Integer,
        default=30,
        nullable=False,
        comment="Timeout for agent operations in seconds",
    )

    # RAG configuration
    rag_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether RAG is enabled for this tenant",
    )

    rag_similarity_threshold = Column(
        Float,
        default=0.7,
        nullable=False,
        comment="Minimum similarity score for RAG results (0.0-1.0)",
    )

    rag_max_results = Column(
        Integer,
        default=5,
        nullable=False,
        comment="Maximum number of results from RAG search",
    )

    # Prompt configuration
    prompt_scope = Column(
        String(20),
        default="org",
        nullable=False,
        comment="Prompt resolution scope: 'system', 'global', 'org'",
    )

    # WhatsApp integration
    whatsapp_phone_number_id = Column(
        String(50),
        nullable=True,
        comment="WhatsApp Business phone number ID (overrides global)",
    )

    whatsapp_verify_token = Column(
        String(255),
        nullable=True,
        comment="Webhook verification token (overrides global)",
    )

    # Advanced configuration
    advanced_config = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Additional configuration (rate limits, custom settings)",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="config",
    )

    # Table configuration
    __table_args__ = (
        Index("idx_tenant_configs_org_id", organization_id),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<TenantConfig(org_id='{self.organization_id}', domains={self.enabled_domains})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "enabled_domains": self.enabled_domains or [],
            "default_domain": self.default_domain,
            "enabled_agent_types": self.enabled_agent_types or [],
            "agent_timeout_seconds": self.agent_timeout_seconds,
            "rag_enabled": self.rag_enabled,
            "rag_similarity_threshold": self.rag_similarity_threshold,
            "rag_max_results": self.rag_max_results,
            "prompt_scope": self.prompt_scope,
            "whatsapp_phone_number_id": self.whatsapp_phone_number_id,
            "whatsapp_verify_token": "***" if self.whatsapp_verify_token else None,
            "advanced_config": self.advanced_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def create_default(cls, organization_id: uuid.UUID) -> "TenantConfig":
        """Factory method to create default configuration for a new organization."""
        return cls(
            organization_id=organization_id,
            enabled_domains=["excelencia"],
            default_domain="excelencia",
            enabled_agent_types=[],
            rag_enabled=True,
            rag_similarity_threshold=0.7,
            rag_max_results=5,
            prompt_scope="org",
        )
