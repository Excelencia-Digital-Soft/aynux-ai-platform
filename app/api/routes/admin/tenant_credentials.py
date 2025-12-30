# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API para gestionar credenciales encriptadas por tenant.
#              WhatsApp, DUX, Plex. Usa pgcrypto para encriptar.
# Tenant-Aware: Yes - todas las rutas requieren org_id + require_admin().
# ============================================================================
"""
Tenant Credentials Admin API - Manage encrypted credentials per tenant.

Provides endpoints for managing WhatsApp, DUX, and Plex API credentials.
All sensitive fields are encrypted at rest using pgcrypto.

Security:
- All endpoints require admin authentication
- Sensitive fields are masked in GET responses
- Encryption uses pgcrypto with CREDENTIAL_ENCRYPTION_KEY

Endpoints:
- GET /{org_id}/credentials - Get credentials (masked)
- PUT /{org_id}/credentials - Update credentials (encrypts automatically)
- DELETE /{org_id}/credentials - Delete all credentials
- GET /{org_id}/credentials/status - Check which credentials are configured
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_organization_by_id, require_admin
from app.core.tenancy import (
    CredentialEncryptionError,
    CredentialNotFoundError,
    CredentialUpdateRequest,
    get_tenant_credential_service,
)
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization

router = APIRouter(tags=["Tenant Credentials"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class CredentialStatusResponse(BaseModel):
    """Status of configured credentials."""

    organization_id: str
    has_credentials: bool
    whatsapp_configured: bool
    dux_configured: bool
    plex_configured: bool


class CredentialsResponse(BaseModel):
    """Masked credentials response."""

    id: str
    organization_id: str
    # WhatsApp (masked)
    whatsapp_access_token: str | None  # "***" if set
    whatsapp_phone_number_id: str | None
    whatsapp_verify_token: str | None  # "***" if set
    # DUX (masked)
    dux_api_key: str | None  # "***" if set
    dux_api_base_url: str | None
    # Plex (masked)
    plex_api_url: str | None
    plex_api_user: str | None
    plex_api_pass: str | None  # "***" if set
    # Timestamps
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class CredentialsUpdate(BaseModel):
    """Schema for updating credentials.

    All fields are optional. Only provided fields will be updated.
    Sensitive fields will be encrypted before storage.
    """

    # WhatsApp
    whatsapp_access_token: str | None = Field(
        None,
        description="WhatsApp Graph API access token (APP_USR-xxx format)",
    )
    whatsapp_phone_number_id: str | None = Field(
        None,
        description="WhatsApp Business phone number ID",
    )
    whatsapp_verify_token: str | None = Field(
        None,
        description="Webhook verification token",
    )

    # DUX
    dux_api_key: str | None = Field(
        None,
        description="DUX ERP API authentication key",
    )
    dux_api_base_url: str | None = Field(
        None,
        description="DUX API base URL",
    )

    # Plex
    plex_api_url: str | None = Field(
        None,
        description="Plex ERP API URL",
    )
    plex_api_user: str | None = Field(
        None,
        description="Plex ERP username",
    )
    plex_api_pass: str | None = Field(
        None,
        description="Plex ERP password",
    )


class WhatsAppCredentialsUpdate(BaseModel):
    """Schema for updating WhatsApp credentials only."""

    access_token: str = Field(..., description="WhatsApp Graph API access token")
    phone_number_id: str = Field(..., description="WhatsApp Business phone number ID")
    verify_token: str = Field(..., description="Webhook verification token")


class DuxCredentialsUpdate(BaseModel):
    """Schema for updating DUX credentials only."""

    api_key: str = Field(..., description="DUX ERP API authentication key")
    base_url: str = Field(..., description="DUX API base URL")


class PlexCredentialsUpdate(BaseModel):
    """Schema for updating Plex credentials only."""

    api_url: str = Field(..., description="Plex ERP API URL")
    username: str = Field(..., description="Plex ERP username")
    password: str = Field(..., description="Plex ERP password")


# ============================================================
# CREDENTIAL STATUS ENDPOINT
# ============================================================


@router.get(
    "/{org_id}/credentials/status",
    response_model=CredentialStatusResponse,
    summary="Check credential configuration status",
)
async def get_credentials_status(
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> CredentialStatusResponse:
    """
    Check which credentials are configured for an organization.

    Returns boolean status for each credential type without exposing values.
    """
    service = get_tenant_credential_service()

    has_creds = await service.has_credentials(db, org_id)

    return CredentialStatusResponse(
        organization_id=str(org_id),
        has_credentials=has_creds,
        whatsapp_configured=await service.has_whatsapp_credentials(db, org_id),
        dux_configured=await service.has_dux_credentials(db, org_id),
        plex_configured=await service.has_plex_credentials(db, org_id),
    )


# ============================================================
# GET CREDENTIALS (MASKED)
# ============================================================


@router.get(
    "/{org_id}/credentials",
    response_model=CredentialsResponse,
    summary="Get credentials (masked)",
)
async def get_credentials(
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> CredentialsResponse:
    """
    Get credentials for an organization.

    All sensitive fields are masked with "***" in the response.
    """
    service = get_tenant_credential_service()

    try:
        creds = await service._get_tenant_credentials(db, org_id)
        return CredentialsResponse(**creds.to_dict())
    except CredentialNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credentials not found for organization {org_id}",
        ) from e


# ============================================================
# UPDATE CREDENTIALS
# ============================================================


@router.put(
    "/{org_id}/credentials",
    response_model=CredentialsResponse,
    summary="Update credentials",
)
async def update_credentials(
    update_data: CredentialsUpdate,
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> CredentialsResponse:
    """
    Update credentials for an organization.

    Creates credentials if they don't exist.
    Only updates fields that are provided (not None).
    Sensitive fields are automatically encrypted using pgcrypto.
    """
    service = get_tenant_credential_service()

    # Convert Pydantic model to dataclass
    update_request = CredentialUpdateRequest(
        whatsapp_access_token=update_data.whatsapp_access_token,
        whatsapp_phone_number_id=update_data.whatsapp_phone_number_id,
        whatsapp_verify_token=update_data.whatsapp_verify_token,
        dux_api_key=update_data.dux_api_key,
        dux_api_base_url=update_data.dux_api_base_url,
        plex_api_url=update_data.plex_api_url,
        plex_api_user=update_data.plex_api_user,
        plex_api_pass=update_data.plex_api_pass,
    )

    try:
        creds = await service.update_credentials(db, org_id, update_request)
        await db.commit()
        return CredentialsResponse(**creds.to_dict())
    except CredentialEncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e}",
        ) from e


# ============================================================
# UPDATE SPECIFIC CREDENTIALS
# ============================================================


@router.put(
    "/{org_id}/credentials/whatsapp",
    response_model=CredentialsResponse,
    summary="Update WhatsApp credentials",
)
async def update_whatsapp_credentials(
    update_data: WhatsAppCredentialsUpdate,
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> CredentialsResponse:
    """Update only WhatsApp credentials for an organization."""
    service = get_tenant_credential_service()

    update_request = CredentialUpdateRequest(
        whatsapp_access_token=update_data.access_token,
        whatsapp_phone_number_id=update_data.phone_number_id,
        whatsapp_verify_token=update_data.verify_token,
    )

    try:
        creds = await service.update_credentials(db, org_id, update_request)
        await db.commit()
        return CredentialsResponse(**creds.to_dict())
    except CredentialEncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e}",
        ) from e


@router.put(
    "/{org_id}/credentials/dux",
    response_model=CredentialsResponse,
    summary="Update DUX credentials",
)
async def update_dux_credentials(
    update_data: DuxCredentialsUpdate,
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> CredentialsResponse:
    """Update only DUX credentials for an organization."""
    service = get_tenant_credential_service()

    update_request = CredentialUpdateRequest(
        dux_api_key=update_data.api_key,
        dux_api_base_url=update_data.base_url,
    )

    try:
        creds = await service.update_credentials(db, org_id, update_request)
        await db.commit()
        return CredentialsResponse(**creds.to_dict())
    except CredentialEncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e}",
        ) from e


@router.put(
    "/{org_id}/credentials/plex",
    response_model=CredentialsResponse,
    summary="Update Plex credentials",
)
async def update_plex_credentials(
    update_data: PlexCredentialsUpdate,
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> CredentialsResponse:
    """Update only Plex credentials for an organization."""
    service = get_tenant_credential_service()

    update_request = CredentialUpdateRequest(
        plex_api_url=update_data.api_url,
        plex_api_user=update_data.username,
        plex_api_pass=update_data.password,
    )

    try:
        creds = await service.update_credentials(db, org_id, update_request)
        await db.commit()
        return CredentialsResponse(**creds.to_dict())
    except CredentialEncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e}",
        ) from e


# ============================================================
# DELETE CREDENTIALS
# ============================================================


@router.delete(
    "/{org_id}/credentials",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete all credentials",
)
async def delete_credentials(
    org_id: uuid.UUID = Path(..., description="Organization UUID"),
    org: Organization = Depends(get_organization_by_id),
    _admin: None = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """
    Delete all credentials for an organization.

    WARNING: This action is irreversible. All encrypted credentials will be deleted.
    """
    service = get_tenant_credential_service()

    deleted = await service.delete_credentials(db, org_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credentials not found for organization {org_id}",
        )

    await db.commit()
