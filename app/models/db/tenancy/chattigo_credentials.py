# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Credenciales Chattigo ISV por DID (numero WhatsApp Business).
#              Permite multiples numeros con sus propias credenciales y tokens.
# Tenant-Aware: Yes - organization_id FK para aislamiento por tenant.
# ============================================================================
"""
Chattigo Credentials model - Per-DID credential storage for Chattigo ISV.

Each DID (WhatsApp Business number) has its own:
- Username/password for Chattigo ISV authentication
- Login and message URLs (configurable)
- Token refresh configuration
- Optional link to BypassRule for routing

Tokens are managed at runtime by ChattigoTokenCache, not stored in DB.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA

if TYPE_CHECKING:
    from .bypass_rule import BypassRule
    from .organization import Organization


class ChattigoCredentials(Base, TimestampMixin):
    """
    Chattigo ISV credentials per DID (WhatsApp Business number).

    Each row represents one WhatsApp number with its own Chattigo ISV credentials.
    Tokens are obtained at runtime via the ChattigoTokenCache, not stored in DB.

    Attributes:
        id: Unique identifier
        did: WhatsApp Business phone number (e.g., "5492644710400")
        name: Human-readable name (e.g., "Turmedica", "Cuyo")
        username_encrypted: Encrypted Chattigo ISV username
        password_encrypted: Encrypted Chattigo ISV password
        login_url: Chattigo login endpoint
        message_url: Chattigo message/webhook endpoint
        bot_name: Bot display name for outbound messages
        token_refresh_hours: Hours between token refresh (default 7, expires at 8)
        enabled: Whether this DID is active
        organization_id: FK to organization
        bypass_rule_id: Optional FK to bypass_rules for routing association
    """

    __tablename__ = "chattigo_credentials"

    # Primary identification
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique credential identifier",
    )

    # DID identification
    did: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        comment="WhatsApp Business phone number (DID), e.g., '5492644710400'",
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Human-readable name for this DID (e.g., 'Turmedica')",
    )

    # Credentials (encrypted with pgcrypto)
    username_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted Chattigo ISV username (pgcrypto)",
    )

    password_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Encrypted Chattigo ISV password (pgcrypto)",
    )

    # URLs (configurable, have sensible defaults)
    login_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://channels.chattigo.com/bsp-cloud-chattigo-isv/login",
        comment="Chattigo ISV login endpoint",
    )

    base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://channels.chattigo.com/bsp-cloud-chattigo-isv",
        comment="Chattigo API base URL (DID added as /v15.0/{did}/messages)",
    )

    # Configuration
    bot_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Aynux",
        comment="Bot display name for outbound messages",
    )

    token_refresh_hours: Mapped[int] = mapped_column(
        nullable=False,
        default=7,
        comment="Hours between token refresh (tokens expire at 8h)",
    )

    # Status
    enabled: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
        comment="Whether this DID credential is active",
    )

    # Foreign key to organization
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this credential belongs to",
    )

    # Optional link to bypass rule (for routing association)
    bypass_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.bypass_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional bypass rule linked to this DID",
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="chattigo_credentials",
    )

    bypass_rule: Mapped["BypassRule | None"] = relationship(
        "BypassRule",
        foreign_keys=[bypass_rule_id],
    )

    # Table configuration
    __table_args__ = (
        UniqueConstraint("did", name="uq_chattigo_credentials_did"),
        Index("idx_chattigo_credentials_did", "did"),
        Index("idx_chattigo_credentials_org_id", "organization_id"),
        Index("idx_chattigo_credentials_enabled", "enabled"),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return (
            f"<ChattigoCredentials(did='{self.did}', name='{self.name}', "
            f"org_id='{self.organization_id}', enabled={self.enabled})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses (masks credentials)."""
        return {
            "id": str(self.id),
            "did": self.did,
            "name": self.name,
            "username_encrypted": "***",  # Never expose
            "password_encrypted": "***",  # Never expose
            "login_url": self.login_url,
            "base_url": self.base_url,
            "bot_name": self.bot_name,
            "token_refresh_hours": self.token_refresh_hours,
            "enabled": self.enabled,
            "organization_id": str(self.organization_id),
            "bypass_rule_id": str(self.bypass_rule_id) if self.bypass_rule_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
