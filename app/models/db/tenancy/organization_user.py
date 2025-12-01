"""
OrganizationUser model - User membership in organizations.

Links users to organizations with roles and personal settings.
Supports the hybrid isolation model: org defines base, users personalize.
"""

import uuid

from sqlalchemy import Column, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class OrganizationUser(Base, TimestampMixin):
    """
    User membership in an organization.

    Implements the hybrid isolation model where:
    - Organization defines base configuration
    - Users can personalize within organization limits

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations
        user_id: FK to users
        role: User role in organization ("owner", "admin", "member")
        personal_settings: User-specific settings (JSONB)
    """

    __tablename__ = "organization_users"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique membership identifier",
    )

    # Foreign keys
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this membership belongs to",
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who is a member of the organization",
    )

    # Role in organization
    role = Column(
        String(50),
        default="member",
        nullable=False,
        comment="User role: 'owner', 'admin', 'member'",
    )

    # Personal settings (user-level customizations within org)
    personal_settings = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="User-specific settings overrides (e.g., default_domain, ui_preferences)",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="users",
    )

    user = relationship(
        "UserDB",
        backref="organization_memberships",
    )

    # Table configuration
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user"),
        Index("idx_org_users_org_id", organization_id),
        Index("idx_org_users_user_id", user_id),
        Index("idx_org_users_role", role),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<OrganizationUser(org_id='{self.organization_id}', user_id='{self.user_id}', role='{self.role}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "user_id": str(self.user_id),
            "role": self.role,
            "personal_settings": self.personal_settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def is_owner(self) -> bool:
        """Check if user is organization owner."""
        return bool(self.role == "owner")

    @property
    def is_admin(self) -> bool:
        """Check if user is admin or owner."""
        return self.role in ("owner", "admin")

    @property
    def can_manage_agents(self) -> bool:
        """Check if user can manage agents."""
        return self.is_admin

    @property
    def can_manage_prompts(self) -> bool:
        """Check if user can manage prompts."""
        return self.is_admin

    @property
    def can_upload_documents(self) -> bool:
        """Check if user can upload documents."""
        return self.is_admin

    @property
    def can_manage_users(self) -> bool:
        """Check if user can manage other users."""
        return self.is_owner
