# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pydantic schemas for pharmacy configuration API endpoints.
# Tenant-Aware: Yes - schemas include organization_id for tenant context.
# ============================================================================
"""Pydantic schemas for pharmacy configuration API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PharmacyConfigCreate(BaseModel):
    """Schema for creating a pharmacy configuration."""

    organization_id: str = Field(..., description="Organization UUID")

    # Basic info
    pharmacy_name: str = Field(
        default="Farmacia", min_length=2, max_length=255, description="Pharmacy name"
    )
    pharmacy_address: str | None = Field(None, max_length=500, description="Pharmacy address")
    pharmacy_phone: str | None = Field(None, max_length=50, description="Pharmacy phone")
    pharmacy_logo_path: str | None = Field(None, max_length=500, description="Logo image path")

    # Mercado Pago config
    mp_enabled: bool = Field(default=False, description="Enable Mercado Pago integration")
    mp_access_token: str | None = Field(None, max_length=500, description="MP Access Token")
    mp_public_key: str | None = Field(None, max_length=255, description="MP Public Key")
    mp_webhook_secret: str | None = Field(None, max_length=255, description="MP Webhook Secret")
    mp_sandbox: bool = Field(default=True, description="Use MP sandbox mode")
    mp_timeout: int = Field(default=30, ge=5, le=120, description="MP request timeout (seconds)")
    mp_notification_url: str | None = Field(None, max_length=500, description="MP webhook URL")
    receipt_public_url_base: str | None = Field(
        None, max_length=500, description="Base URL for public receipts"
    )

    # WhatsApp
    whatsapp_phone_number: str | None = Field(
        None, max_length=20, description="WhatsApp phone number for webhook resolution"
    )


class PharmacyConfigUpdate(BaseModel):
    """Schema for updating a pharmacy configuration (partial update)."""

    # Basic info
    pharmacy_name: str | None = Field(None, min_length=2, max_length=255)
    pharmacy_address: str | None = Field(None, max_length=500)
    pharmacy_phone: str | None = Field(None, max_length=50)
    pharmacy_logo_path: str | None = Field(None, max_length=500)

    # Mercado Pago config
    mp_enabled: bool | None = None
    mp_access_token: str | None = Field(None, max_length=500)
    mp_public_key: str | None = Field(None, max_length=255)
    mp_webhook_secret: str | None = Field(None, max_length=255)
    mp_sandbox: bool | None = None
    mp_timeout: int | None = Field(None, ge=5, le=120)
    mp_notification_url: str | None = Field(None, max_length=500)
    receipt_public_url_base: str | None = Field(None, max_length=500)

    # WhatsApp
    whatsapp_phone_number: str | None = Field(None, max_length=20)


class PharmacyConfigResponse(BaseModel):
    """Schema for pharmacy configuration response with masked secrets."""

    id: str
    organization_id: str
    organization_name: str | None = None

    # Basic info
    pharmacy_name: str
    pharmacy_address: str | None
    pharmacy_phone: str | None
    pharmacy_logo_path: str | None

    # Mercado Pago (secrets masked)
    mp_enabled: bool
    mp_sandbox: bool
    mp_timeout: int
    mp_notification_url: str | None
    receipt_public_url_base: str | None
    has_mp_credentials: bool  # True if access_token is configured

    # Masked credentials (only shown if configured)
    mp_access_token: str | None = None  # Will be "***" if set
    mp_public_key: str | None = None  # Will be "***" if set
    mp_webhook_secret: str | None = None  # Will be "***" if set

    # WhatsApp
    whatsapp_phone_number: str | None

    # Timestamps
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class PharmacyConfigListResponse(BaseModel):
    """Schema for paginated pharmacy configuration list."""

    pharmacies: list[PharmacyConfigResponse]
    total: int
    page: int
    page_size: int
