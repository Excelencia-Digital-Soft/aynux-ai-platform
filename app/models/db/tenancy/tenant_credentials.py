# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Credenciales encriptadas por tenant usando pgcrypto.
#              Almacena tokens de WhatsApp, DUX, Plex con encriptaci贸n AES-256.
# Tenant-Aware: Yes - cada registro pertenece a una organizaci贸n espec铆fica.
# ============================================================================
"""
TenantCredentials model - Encrypted credentials per tenant.

Stores sensitive API credentials using pgcrypto symmetric encryption:
- WhatsApp Business API tokens
- DUX ERP API credentials
- Plex ERP API credentials

Security:
- All sensitive fields stored as pgp_sym_encrypt() encrypted text
- Decryption requires CREDENTIAL_ENCRYPTION_KEY environment variable
- Credentials masked in to_dict() for API responses
"""

import uuid

from sqlalchemy import Column, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class TenantCredentials(Base, TimestampMixin):
    """
    Encrypted credentials for a tenant.

    One-to-one relationship with Organization.
    All sensitive fields are stored encrypted using pgcrypto.

    Encrypted fields (stored as base64-encoded pgp_sym_encrypt output):
        - whatsapp_access_token_encrypted: WhatsApp Graph API access token
        - whatsapp_verify_token_encrypted: Webhook verification token
        - dux_api_key_encrypted: DUX ERP API key
        - plex_api_pass_encrypted: Plex ERP password

    Non-sensitive fields (stored as plaintext):
        - whatsapp_phone_number_id: WhatsApp Business phone number ID
        - dux_api_base_url: DUX API base URL
        - plex_api_url: Plex ERP API URL
        - plex_api_user: Plex ERP username
    """

    __tablename__ = "tenant_credentials"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique credential record identifier",
    )

    # Foreign key (one-to-one with organization)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        comment="Organization these credentials belong to",
    )

    # =========================================================================
    # WhatsApp Business API Credentials
    # =========================================================================

    whatsapp_access_token_encrypted = Column(
        Text,
        nullable=True,
        comment="Encrypted WhatsApp Graph API access token (pgcrypto)",
    )

    whatsapp_phone_number_id = Column(
        String(50),
        nullable=True,
        comment="WhatsApp Business phone number ID (not sensitive)",
    )

    whatsapp_verify_token_encrypted = Column(
        Text,
        nullable=True,
        comment="Encrypted webhook verification token (pgcrypto)",
    )

    # =========================================================================
    # DUX ERP API Credentials
    # =========================================================================

    dux_api_key_encrypted = Column(
        Text,
        nullable=True,
        comment="Encrypted DUX ERP API key (pgcrypto)",
    )

    dux_api_base_url = Column(
        String(255),
        nullable=True,
        comment="DUX API base URL (not sensitive)",
    )

    # =========================================================================
    # Plex ERP API Credentials
    # =========================================================================

    plex_api_url = Column(
        String(255),
        nullable=True,
        comment="Plex ERP API URL (not sensitive)",
    )

    plex_api_user = Column(
        String(100),
        nullable=True,
        comment="Plex ERP username (not sensitive)",
    )

    plex_api_pass_encrypted = Column(
        Text,
        nullable=True,
        comment="Encrypted Plex ERP password (pgcrypto)",
    )

    # =========================================================================
    # Relationships
    # =========================================================================

    organization = relationship(
        "Organization",
        back_populates="credentials",
    )

    # =========================================================================
    # Table Configuration
    # =========================================================================

    __table_args__ = (
        Index("idx_tenant_credentials_org_id", organization_id),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<TenantCredentials(org_id='{self.organization_id}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses.

        All encrypted fields are masked with '***' for security.
        """
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            # WhatsApp (masked)
            "whatsapp_access_token": "***" if self.whatsapp_access_token_encrypted else None,
            "whatsapp_phone_number_id": self.whatsapp_phone_number_id,
            "whatsapp_verify_token": "***" if self.whatsapp_verify_token_encrypted else None,
            # DUX (masked)
            "dux_api_key": "***" if self.dux_api_key_encrypted else None,
            "dux_api_base_url": self.dux_api_base_url,
            # Plex (masked)
            "plex_api_url": self.plex_api_url,
            "plex_api_user": self.plex_api_user,
            "plex_api_pass": "***" if self.plex_api_pass_encrypted else None,
            # Timestamps
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def has_whatsapp_credentials(self) -> bool:
        """Check if WhatsApp credentials are configured."""
        return bool(
            self.whatsapp_access_token_encrypted
            and self.whatsapp_phone_number_id
            and self.whatsapp_verify_token_encrypted
        )

    def has_dux_credentials(self) -> bool:
        """Check if DUX credentials are configured."""
        return bool(self.dux_api_key_encrypted and self.dux_api_base_url)

    def has_plex_credentials(self) -> bool:
        """Check if Plex credentials are configured."""
        return bool(
            self.plex_api_url
            and self.plex_api_user
            and self.plex_api_pass_encrypted
        )
