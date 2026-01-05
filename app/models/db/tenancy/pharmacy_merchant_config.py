# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Configuracion de comercio/farmacia por tenant. Almacena
#              credenciales de Mercado Pago e informacion de farmacia para
#              recibos PDF y notificaciones WhatsApp.
# Tenant-Aware: Yes - cada registro pertenece a una organizacion especifica.
# ============================================================================
"""
PharmacyMerchantConfig model - Per-tenant pharmacy and payment configuration.

Stores configuration for each pharmacy/merchant including:
- Pharmacy branding info for PDF receipts
- Mercado Pago credentials and settings
- Webhook notification URLs
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class PharmacyMerchantConfig(Base, TimestampMixin):
    """
    Per-tenant pharmacy and Mercado Pago configuration.

    Many-to-one relationship with Organization (one org can have multiple pharmacies).
    Stores all payment-related configuration for each pharmacy.

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations (multiple pharmacies allowed per org)
        pharmacy_name: Name displayed on PDF receipts
        pharmacy_address: Address on PDF receipts
        pharmacy_phone: Phone on PDF receipts
        pharmacy_logo_path: Path to logo image
        mp_enabled: Whether Mercado Pago is enabled
        mp_access_token: Bearer token for MP API
        mp_public_key: Public key for MP SDK
        mp_webhook_secret: Secret for validating webhooks
        mp_sandbox: Use sandbox mode for testing
        mp_timeout: Request timeout in seconds
        mp_notification_url: Webhook URL for MP notifications
        receipt_public_url_base: Base URL for public receipt access
        whatsapp_phone_number: Optional WA number for fast webhook lookup
    """

    __tablename__ = "pharmacy_merchant_configs"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique configuration identifier",
    )

    # Foreign key (many-to-one with organization - multiple pharmacies allowed)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Organization this config belongs to (multiple pharmacies per org allowed)",
    )

    # Pharmacy receipt info
    pharmacy_name = Column(
        String(255),
        nullable=False,
        default="Farmacia",
        comment="Pharmacy name displayed on PDF receipts",
    )

    pharmacy_address = Column(
        String(500),
        nullable=True,
        comment="Pharmacy address displayed on PDF receipts",
    )

    pharmacy_phone = Column(
        String(50),
        nullable=True,
        comment="Pharmacy phone displayed on PDF receipts",
    )

    pharmacy_logo_path = Column(
        String(500),
        nullable=True,
        comment="Path to pharmacy logo image for PDF receipts",
    )

    # Pharmacy contact and info fields
    pharmacy_email = Column(
        String(255),
        nullable=True,
        comment="Pharmacy contact email address",
    )

    pharmacy_website = Column(
        String(500),
        nullable=True,
        comment="Pharmacy website URL",
    )

    pharmacy_hours = Column(
        JSONB,
        nullable=True,
        comment="Pharmacy operating hours by day (JSONB format)",
    )

    pharmacy_is_24h = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether pharmacy operates 24 hours",
    )

    # Mercado Pago credentials
    mp_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether Mercado Pago integration is enabled",
    )

    mp_access_token = Column(
        String(500),
        nullable=True,
        comment="Mercado Pago Access Token (APP_USR-xxx)",
    )

    mp_public_key = Column(
        String(255),
        nullable=True,
        comment="Mercado Pago Public Key",
    )

    mp_webhook_secret = Column(
        String(255),
        nullable=True,
        comment="Secret for validating MP webhook signatures",
    )

    mp_sandbox = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Use Mercado Pago sandbox mode for testing",
    )

    mp_timeout = Column(
        Integer,
        nullable=False,
        default=30,
        comment="Timeout for Mercado Pago API requests in seconds",
    )

    # URLs
    mp_notification_url = Column(
        String(500),
        nullable=True,
        comment="Public URL for Mercado Pago webhook notifications",
    )

    receipt_public_url_base = Column(
        String(500),
        nullable=True,
        comment="Base URL for public PDF receipt access",
    )

    # Optional WhatsApp mapping for fast webhook lookup
    whatsapp_phone_number = Column(
        String(20),
        nullable=True,
        index=True,
        comment="WhatsApp phone number for quick webhook org resolution",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="pharmacy_configs",
    )

    bypass_rule = relationship(
        "BypassRule",
        back_populates="pharmacy",
        uselist=False,
        passive_deletes=True,
    )

    # Table configuration
    __table_args__ = (
        Index("idx_pharmacy_merchant_configs_org", organization_id),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<PharmacyMerchantConfig(org_id='{self.organization_id}', pharmacy='{self.pharmacy_name}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses (masks secrets)."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "pharmacy_name": self.pharmacy_name,
            "pharmacy_address": self.pharmacy_address,
            "pharmacy_phone": self.pharmacy_phone,
            "pharmacy_logo_path": self.pharmacy_logo_path,
            "pharmacy_email": self.pharmacy_email,
            "pharmacy_website": self.pharmacy_website,
            "pharmacy_hours": self.pharmacy_hours,
            "pharmacy_is_24h": self.pharmacy_is_24h,
            "mp_enabled": self.mp_enabled,
            "mp_sandbox": self.mp_sandbox,
            "mp_timeout": self.mp_timeout,
            "mp_notification_url": self.mp_notification_url,
            "receipt_public_url_base": self.receipt_public_url_base,
            "whatsapp_phone_number": self.whatsapp_phone_number,
            # Mask secrets for security
            "mp_access_token": "***" if self.mp_access_token else None,
            "mp_public_key": "***" if self.mp_public_key else None,
            "mp_webhook_secret": "***" if self.mp_webhook_secret else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def create_default(cls, organization_id: uuid.UUID) -> PharmacyMerchantConfig:
        """Factory method to create default configuration."""
        return cls(
            organization_id=organization_id,
            pharmacy_name="Farmacia",
            mp_enabled=False,
            mp_sandbox=True,
            mp_timeout=30,
        )
