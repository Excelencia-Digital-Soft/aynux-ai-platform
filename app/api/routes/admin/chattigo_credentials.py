# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API para gestionar credenciales Chattigo ISV por DID.
#              Cada DID (numero WhatsApp Business) tiene sus propias credenciales.
# Tenant-Aware: Yes - credentials linked to organization_id, indexed by DID.
# ============================================================================
"""
Chattigo Credentials Admin API - Manage Chattigo ISV credentials per DID.

Provides endpoints for managing Chattigo ISV credentials for multiple
WhatsApp Business numbers (DIDs). Each DID has its own username/password
and configuration.

Security:
- All endpoints require admin authentication
- Sensitive fields (username, password) are masked in GET responses
- Credentials are encrypted at rest using pgcrypto

Endpoints:
- GET /chattigo-credentials - List all credentials
- GET /chattigo-credentials/{did} - Get credentials by DID (masked)
- POST /chattigo-credentials - Create new credentials
- PUT /chattigo-credentials/{did} - Update credentials
- DELETE /chattigo-credentials/{did} - Delete credentials
- POST /chattigo-credentials/{did}/test - Test authentication
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_scopes
from app.core.tenancy import (
    ChattigoCredentialCreateRequest,
    ChattigoCredentialUpdateRequest,
    ChattigoNotFoundError,
    CredentialEncryptionError,
    get_chattigo_credential_service,
)
from app.database.async_db import get_async_db
from app.integrations.chattigo.adapter_factory import (
    ChattigoTokenError,
    get_chattigo_adapter_factory,
)

router = APIRouter(tags=["Chattigo Credentials"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class ChattigoCredentialResponse(BaseModel):
    """Response schema for Chattigo credentials (masked)."""

    did: str = Field(..., description="WhatsApp Business phone number (DID)")
    name: str = Field(..., description="Human-readable name")
    username: str = Field(..., description="Username (masked)")
    login_url: str = Field(..., description="Chattigo login endpoint")
    base_url: str = Field(..., description="Chattigo API base URL")
    bot_name: str = Field(..., description="Bot display name")
    token_refresh_hours: int = Field(..., description="Hours between token refresh")
    enabled: bool = Field(..., description="Whether this credential is active")
    organization_id: str = Field(..., description="Organization UUID")
    bypass_rule_id: str | None = Field(None, description="Linked bypass rule UUID")

    class Config:
        from_attributes = True


class ChattigoCredentialCreate(BaseModel):
    """Schema for creating new Chattigo credentials."""

    did: str = Field(
        ...,
        description="WhatsApp Business phone number (DID), e.g., '5492644710400'",
        pattern=r"^\d{10,15}$",
    )
    name: str = Field(
        ...,
        description="Human-readable name, e.g., 'Turmedica'",
        min_length=1,
        max_length=100,
    )
    username: str = Field(
        ...,
        description="Chattigo ISV username",
        min_length=1,
    )
    password: str = Field(
        ...,
        description="Chattigo ISV password",
        min_length=1,
    )
    organization_id: str = Field(
        ...,
        description="Organization UUID",
    )
    login_url: str | None = Field(
        None,
        description="Chattigo login endpoint (uses default if not provided)",
    )
    base_url: str | None = Field(
        None,
        description="Chattigo API base URL (uses default if not provided)",
    )
    bot_name: str | None = Field(
        None,
        description="Bot display name (defaults to 'Aynux')",
        max_length=50,
    )
    token_refresh_hours: int | None = Field(
        None,
        description="Hours between token refresh (default: 7, tokens expire at 8)",
        ge=1,
        le=7,
    )
    bypass_rule_id: str | None = Field(
        None,
        description="Optional bypass rule UUID to link",
    )


class ChattigoCredentialUpdate(BaseModel):
    """Schema for updating Chattigo credentials.

    All fields are optional. Only provided fields will be updated.
    """

    name: str | None = Field(
        None,
        description="Human-readable name",
        min_length=1,
        max_length=100,
    )
    username: str | None = Field(
        None,
        description="New Chattigo ISV username",
        min_length=1,
    )
    password: str | None = Field(
        None,
        description="New Chattigo ISV password",
        min_length=1,
    )
    login_url: str | None = Field(
        None,
        description="Chattigo login endpoint",
    )
    base_url: str | None = Field(
        None,
        description="Chattigo API base URL",
    )
    bot_name: str | None = Field(
        None,
        description="Bot display name",
        max_length=50,
    )
    token_refresh_hours: int | None = Field(
        None,
        description="Hours between token refresh",
        ge=1,
        le=7,
    )
    enabled: bool | None = Field(
        None,
        description="Whether this credential is active",
    )
    bypass_rule_id: str | None = Field(
        None,
        description="Bypass rule UUID to link (or empty string to unlink)",
    )


class ChattigoCredentialList(BaseModel):
    """Response schema for listing credentials."""

    credentials: list[ChattigoCredentialResponse]
    total: int


class ChattigoTestResult(BaseModel):
    """Response schema for authentication test."""

    success: bool
    did: str
    name: str
    message: str
    token_preview: str | None = None


class ChattigoCacheStats(BaseModel):
    """Response schema for token cache statistics."""

    total_cached: int
    dids: list[dict]


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _mask_username(username: str) -> str:
    """Mask username for display."""
    if len(username) > 4:
        return f"{username[:4]}***"
    return "***"


def _to_response(creds) -> ChattigoCredentialResponse:
    """Convert credentials DTO to response schema (masked)."""
    return ChattigoCredentialResponse(
        did=creds.did,
        name=creds.name,
        username=_mask_username(creds.username),
        login_url=creds.login_url,
        base_url=creds.base_url,
        bot_name=creds.bot_name,
        token_refresh_hours=creds.token_refresh_hours,
        enabled=creds.enabled,  # Use actual enabled value from DTO
        organization_id=str(creds.organization_id),
        bypass_rule_id=str(creds.bypass_rule_id) if creds.bypass_rule_id else None,
    )


# ============================================================
# LIST CREDENTIALS
# ============================================================


@router.get(
    "/chattigo-credentials",
    response_model=ChattigoCredentialList,
    summary="List all Chattigo credentials",
)
async def list_chattigo_credentials(
    organization_id: str | None = Query(
        None,
        description="Filter by organization UUID",
    ),
    _admin: None = Depends(require_scopes(["admin"])),
    db: AsyncSession = Depends(get_async_db),
) -> ChattigoCredentialList:
    """
    List all Chattigo ISV credentials.

    Optionally filter by organization_id.
    All sensitive fields are masked in the response.
    """
    service = get_chattigo_credential_service()

    org_uuid = uuid.UUID(organization_id) if organization_id else None
    # Admin API shows all credentials including disabled ones
    credentials = await service.get_all_credentials(
        db, org_uuid, include_disabled=True
    )

    return ChattigoCredentialList(
        credentials=[_to_response(c) for c in credentials],
        total=len(credentials),
    )


# ============================================================
# GET CREDENTIALS BY DID
# ============================================================


@router.get(
    "/chattigo-credentials/{did}",
    response_model=ChattigoCredentialResponse,
    summary="Get Chattigo credentials by DID",
)
async def get_chattigo_credentials(
    did: str = Path(..., description="WhatsApp Business phone number (DID)"),
    _admin: None = Depends(require_scopes(["admin"])),
    db: AsyncSession = Depends(get_async_db),
) -> ChattigoCredentialResponse:
    """
    Get Chattigo credentials for a specific DID.

    Sensitive fields are masked in the response.
    """
    service = get_chattigo_credential_service()

    try:
        creds = await service.get_credentials_by_did(db, did)
        return _to_response(creds)
    except ChattigoNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chattigo credentials not found for DID {did}",
        ) from e


# ============================================================
# CREATE CREDENTIALS
# ============================================================


@router.post(
    "/chattigo-credentials",
    response_model=ChattigoCredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new Chattigo credentials",
)
async def create_chattigo_credentials(
    data: ChattigoCredentialCreate,
    _admin: None = Depends(require_scopes(["admin"])),
    db: AsyncSession = Depends(get_async_db),
) -> ChattigoCredentialResponse:
    """
    Create new Chattigo ISV credentials for a DID.

    Credentials are automatically encrypted using pgcrypto.
    """
    service = get_chattigo_credential_service()

    # Parse UUIDs
    try:
        org_uuid = uuid.UUID(data.organization_id)
        bypass_uuid = uuid.UUID(data.bypass_rule_id) if data.bypass_rule_id else None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UUID format: {e}",
        ) from e

    # Create request DTO
    request = ChattigoCredentialCreateRequest(
        did=data.did,
        name=data.name,
        username=data.username,
        password=data.password,
        organization_id=org_uuid,
        login_url=data.login_url,
        base_url=data.base_url,
        bot_name=data.bot_name,
        token_refresh_hours=data.token_refresh_hours,
        bypass_rule_id=bypass_uuid,
    )

    try:
        creds = await service.create_credentials(db, request)
        await db.commit()
        return _to_response(creds)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except CredentialEncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e}",
        ) from e


# ============================================================
# UPDATE CREDENTIALS
# ============================================================


@router.put(
    "/chattigo-credentials/{did}",
    response_model=ChattigoCredentialResponse,
    summary="Update Chattigo credentials",
)
async def update_chattigo_credentials(
    data: ChattigoCredentialUpdate,
    did: str = Path(..., description="WhatsApp Business phone number (DID)"),
    _admin: None = Depends(require_scopes(["admin"])),
    db: AsyncSession = Depends(get_async_db),
) -> ChattigoCredentialResponse:
    """
    Update Chattigo credentials for a DID.

    Only provided fields will be updated.
    Username and password are re-encrypted if provided.
    """
    service = get_chattigo_credential_service()

    # Parse bypass_rule_id (empty string = unlink)
    bypass_uuid: uuid.UUID | None = None
    if data.bypass_rule_id:
        try:
            bypass_uuid = uuid.UUID(data.bypass_rule_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bypass_rule_id UUID: {e}",
            ) from e

    # Create request DTO
    request = ChattigoCredentialUpdateRequest(
        name=data.name,
        username=data.username,
        password=data.password,
        login_url=data.login_url,
        base_url=data.base_url,
        bot_name=data.bot_name,
        token_refresh_hours=data.token_refresh_hours,
        enabled=data.enabled,
        bypass_rule_id=bypass_uuid,
    )

    try:
        creds = await service.update_credentials(db, did, request)
        await db.commit()

        # Invalidate token cache if credentials changed
        if data.username or data.password:
            factory = get_chattigo_adapter_factory()
            await factory.token_cache.invalidate(did)

        return _to_response(creds)
    except ChattigoNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chattigo credentials not found for DID {did}",
        ) from e
    except CredentialEncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Encryption failed: {e}",
        ) from e


# ============================================================
# DELETE CREDENTIALS
# ============================================================


@router.delete(
    "/chattigo-credentials/{did}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Chattigo credentials",
)
async def delete_chattigo_credentials(
    did: str = Path(..., description="WhatsApp Business phone number (DID)"),
    _admin: None = Depends(require_scopes(["admin"])),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """
    Delete Chattigo credentials for a DID.

    WARNING: This action is irreversible.
    """
    service = get_chattigo_credential_service()

    deleted = await service.delete_credentials(db, did)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chattigo credentials not found for DID {did}",
        )

    await db.commit()

    # Invalidate token cache
    factory = get_chattigo_adapter_factory()
    await factory.token_cache.invalidate(did)


# ============================================================
# TEST AUTHENTICATION
# ============================================================


@router.post(
    "/chattigo-credentials/{did}/test",
    response_model=ChattigoTestResult,
    summary="Test Chattigo authentication",
)
async def test_chattigo_credentials(
    did: str = Path(..., description="WhatsApp Business phone number (DID)"),
    _admin: None = Depends(require_scopes(["admin"])),
    db: AsyncSession = Depends(get_async_db),
) -> ChattigoTestResult:
    """
    Test authentication for Chattigo credentials.

    Attempts to obtain a JWT token using the stored credentials.
    Does NOT send any messages.
    """
    factory = get_chattigo_adapter_factory()

    try:
        adapter = await factory.get_adapter(db, did)
        health = await adapter.health_check()

        if health.get("authenticated"):
            return ChattigoTestResult(
                success=True,
                did=did,
                name=health.get("name", "Unknown"),
                message="Authentication successful",
                token_preview=health.get("token_preview"),
            )
        else:
            return ChattigoTestResult(
                success=False,
                did=did,
                name=health.get("name", "Unknown"),
                message=health.get("error", "Authentication failed"),
            )
    except ChattigoNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chattigo credentials not found for DID {did}",
        ) from e
    except ChattigoTokenError as e:
        return ChattigoTestResult(
            success=False,
            did=did,
            name="Unknown",
            message=f"Authentication failed: {e}",
        )


# ============================================================
# TOKEN CACHE STATS
# ============================================================


@router.get(
    "/chattigo-credentials/cache/stats",
    response_model=ChattigoCacheStats,
    summary="Get token cache statistics",
)
async def get_cache_stats(
    _admin: None = Depends(require_scopes(["admin"])),
) -> ChattigoCacheStats:
    """
    Get token cache statistics for monitoring.

    Shows which DIDs have cached tokens and when they expire.
    """
    factory = get_chattigo_adapter_factory()
    stats = factory.token_cache.get_cache_stats()

    return ChattigoCacheStats(
        total_cached=stats["total_cached"],
        dids=stats["dids"],
    )


@router.post(
    "/chattigo-credentials/cache/invalidate/{did}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate cached token",
)
async def invalidate_cache(
    did: str = Path(..., description="WhatsApp Business phone number (DID)"),
    _admin: None = Depends(require_scopes(["admin"])),
) -> None:
    """
    Invalidate cached token for a DID.

    Forces token refresh on next request.
    """
    factory = get_chattigo_adapter_factory()
    await factory.token_cache.invalidate(did)
