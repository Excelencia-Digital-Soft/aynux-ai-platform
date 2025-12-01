"""
TenantPrompt model - Per-tenant prompt overrides.

Implements the scope hierarchy:
1. USER: User-level overrides within organization
2. ORG: Organization-level customizations
3. GLOBAL: System-wide defaults (in prompts table)
4. SYSTEM: Code-level YAML files
"""

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class TenantPrompt(Base, TimestampMixin):
    """
    Prompt override for a tenant.

    Allows organizations and users to customize prompts while maintaining
    a fallback hierarchy to system defaults.

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations
        prompt_key: Key matching PromptRegistry (e.g., "product.search.intent")
        scope: Override scope ("org" or "user")
        user_id: FK to users (only for scope="user")
        template: The prompt template text
        description: Description of this prompt
        version: Version string
        metadata: Additional metadata (variables, temperature, etc.)
        is_active: Whether this override is active
    """

    __tablename__ = "tenant_prompts"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique prompt identifier",
    )

    # Foreign keys
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this prompt belongs to",
    )

    # Prompt identification
    prompt_key = Column(
        String(255),
        nullable=False,
        comment="Key matching PromptRegistry (e.g., 'product.search.intent')",
    )

    # Scope hierarchy
    scope = Column(
        String(20),
        default="org",
        nullable=False,
        comment="Override scope: 'org' (organization) or 'user' (user-specific)",
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="User ID for user-scope prompts (null for org-scope)",
    )

    # Prompt content
    template = Column(
        Text,
        nullable=False,
        comment="The prompt template text with {variable} placeholders",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Description of this prompt's purpose",
    )

    version = Column(
        String(50),
        default="1.0.0",
        nullable=False,
        comment="Semantic version of this prompt",
    )

    # Metadata (renamed to meta_data to avoid SQLAlchemy reserved word)
    meta_data = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Additional metadata (required_variables, temperature, max_tokens, model)",
    )

    # Status
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this override is active",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="prompts",
    )

    user = relationship(
        "UserDB",
        backref="tenant_prompts",
    )

    # Table configuration
    __table_args__ = (
        # Unique constraint ensures only one active override per key/scope/user
        UniqueConstraint(
            "organization_id",
            "prompt_key",
            "scope",
            "user_id",
            name="uq_org_prompt_key_scope_user",
        ),
        Index("idx_tenant_prompts_org_id", organization_id),
        Index("idx_tenant_prompts_key", prompt_key),
        Index("idx_tenant_prompts_scope", scope),
        Index("idx_tenant_prompts_user_id", user_id),
        Index("idx_tenant_prompts_active", is_active),
        # Composite index for common lookup pattern
        Index("idx_tenant_prompts_org_key_scope", organization_id, prompt_key, scope),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        scope_info = f"user={self.user_id}" if self.scope == "user" else "org"
        return f"<TenantPrompt(org_id='{self.organization_id}', key='{self.prompt_key}', scope='{scope_info}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "prompt_key": self.prompt_key,
            "scope": self.scope,
            "user_id": str(self.user_id) if self.user_id else None,
            "template": self.template,
            "description": self.description,
            "version": self.version,
            "meta_data": self.meta_data,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def is_org_scope(self) -> bool:
        """Check if this is an organization-level override."""
        return bool(self.scope == "org")

    @property
    def is_user_scope(self) -> bool:
        """Check if this is a user-level override."""
        return bool(self.scope == "user")

    @property
    def required_variables(self) -> list[str]:
        """Get list of required variables from meta_data."""
        return self.meta_data.get("required_variables", [])

    @classmethod
    def create_org_override(
        cls,
        organization_id: uuid.UUID,
        prompt_key: str,
        template: str,
        description: str | None = None,
        meta_data: dict | None = None,
    ) -> "TenantPrompt":
        """Factory method to create an organization-level prompt override."""
        return cls(
            organization_id=organization_id,
            prompt_key=prompt_key,
            scope="org",
            template=template,
            description=description,
            meta_data=meta_data or {},
            is_active=True,
        )

    @classmethod
    def create_user_override(
        cls,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        prompt_key: str,
        template: str,
        description: str | None = None,
        meta_data: dict | None = None,
    ) -> "TenantPrompt":
        """Factory method to create a user-level prompt override."""
        return cls(
            organization_id=organization_id,
            user_id=user_id,
            prompt_key=prompt_key,
            scope="user",
            template=template,
            description=description,
            meta_data=meta_data or {},
            is_active=True,
        )
