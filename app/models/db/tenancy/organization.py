# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Entidad principal de tenant. Cada organización es un tenant
#              aislado con su propia configuración, usuarios, documentos, etc.
# Tenant-Aware: Yes - ES la tabla raíz del sistema multi-tenant.
# ============================================================================
"""
Organization model - Core tenant entity for multi-tenant system.

Organizations are the top-level entity for multi-tenancy, containing:
- Configuration for agents, RAG, prompts, and LLM
- User memberships and roles
- Quotas and feature flags
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class Organization(Base, TimestampMixin):
    """
    Organization entity representing a tenant in the multi-tenant system.

    Each organization has its own:
    - Configuration for LLM, RAG, and agents
    - Users with different roles
    - Documents and knowledge base
    - Prompts (with scope hierarchy)

    Attributes:
        id: Unique identifier (UUID)
        slug: URL-friendly unique identifier (e.g., "acme-corp")
        name: Official organization name
        display_name: Display name for UI
        mode: Operating mode ("generic" or "multi_tenant")
        llm_model: Default LLM model for this tenant
        llm_temperature: Default temperature for LLM
        llm_max_tokens: Max tokens for LLM responses
        features: Feature flags (JSONB)
        max_users: Maximum users allowed
        max_documents: Maximum documents in knowledge base
        max_agents: Maximum custom agents
        status: Organization status ("active", "suspended", "trial")
        trial_ends_at: Trial expiration date (if applicable)
    """

    __tablename__ = "organizations"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique organization identifier",
    )

    slug = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-friendly unique identifier (e.g., 'acme-corp')",
    )

    name = Column(
        String(255),
        nullable=False,
        comment="Official organization name",
    )

    display_name = Column(
        String(255),
        nullable=True,
        comment="Display name for UI (falls back to name)",
    )

    # Operating mode
    mode = Column(
        String(20),
        default="multi_tenant",
        nullable=False,
        comment="Operating mode: 'generic' uses static config, 'multi_tenant' uses DB config",
    )

    # LLM Configuration
    llm_model = Column(
        String(100),
        default="llama3.2:1b",
        nullable=False,
        comment="Default LLM model for this tenant",
    )

    llm_temperature = Column(
        Float,
        default=0.7,
        nullable=False,
        comment="Default temperature for LLM (0.0-1.0)",
    )

    llm_max_tokens = Column(
        Integer,
        default=2048,
        nullable=False,
        comment="Max tokens for LLM responses",
    )

    # Feature flags
    features = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Feature flags (e.g., {'rag_enabled': true, 'custom_agents': false})",
    )

    # Quotas
    max_users = Column(
        Integer,
        default=10,
        nullable=False,
        comment="Maximum users allowed in organization",
    )

    max_documents = Column(
        Integer,
        default=1000,
        nullable=False,
        comment="Maximum documents in knowledge base",
    )

    max_agents = Column(
        Integer,
        default=20,
        nullable=False,
        comment="Maximum custom agents",
    )

    # Status
    status = Column(
        String(20),
        default="active",
        nullable=False,
        index=True,
        comment="Organization status: 'active', 'suspended', 'trial'",
    )

    trial_ends_at = Column(
        DateTime,
        nullable=True,
        comment="Trial expiration date (null if not on trial)",
    )

    # Relationships
    users = relationship(
        "OrganizationUser",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    config = relationship(
        "TenantConfig",
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )

    agents = relationship(
        "TenantAgent",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    prompts = relationship(
        "TenantPrompt",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    documents = relationship(
        "TenantDocument",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    pharmacy_configs = relationship(
        "PharmacyMerchantConfig",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    credentials = relationship(
        "TenantCredentials",
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )

    bypass_rules = relationship(
        "BypassRule",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    chattigo_credentials = relationship(
        "ChattigoCredentials",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    tenant_institution_configs = relationship(
        "TenantInstitutionConfig",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    # Domain intents (unified multi-domain structure)
    domain_intents = relationship(
        "DomainIntent",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    response_configs = relationship(
        "ResponseConfig",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    # Table configuration
    __table_args__ = (
        Index("idx_organizations_slug", slug),
        Index("idx_organizations_status", status),
        Index("idx_organizations_mode", mode),
        Index("idx_organizations_created_at", "created_at"),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<Organization(slug='{self.slug}', name='{self.name}', mode='{self.mode}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "slug": self.slug,
            "name": self.name,
            "display_name": self.display_name or self.name,
            "mode": self.mode,
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
            "llm_max_tokens": self.llm_max_tokens,
            "features": self.features,
            "max_users": self.max_users,
            "max_documents": self.max_documents,
            "max_agents": self.max_agents,
            "status": self.status,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def is_active(self) -> bool:
        """Check if organization is active."""
        return bool(self.status == "active")

    @property
    def is_trial(self) -> bool:
        """Check if organization is on trial."""
        return bool(self.status == "trial")

    @property
    def is_trial_expired(self) -> bool:
        """Check if trial has expired."""
        if not self.is_trial or not self.trial_ends_at:
            return False
        return bool(datetime.now() > self.trial_ends_at)

    @property
    def is_multi_tenant(self) -> bool:
        """Check if organization uses multi-tenant mode."""
        return bool(self.mode == "multi_tenant")

    @property
    def is_generic(self) -> bool:
        """Check if organization uses generic mode."""
        return bool(self.mode == "generic")

    @classmethod
    def create_system_org(cls) -> "Organization":
        """Factory method to create the system organization (for generic mode)."""
        return cls(
            id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            slug="system",
            name="System",
            display_name="System (Generic Mode)",
            mode="generic",
            status="active",
            max_users=1000,
            max_documents=10000,
            max_agents=100,
        )
