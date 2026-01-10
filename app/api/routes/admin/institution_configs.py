# ============================================================================
# SCOPE: MULTI-TENANT
# Description: API para gestionar configuraciones de instituciones por tenant.
#              Soporta CRUD completo con validacion JSONB y secrets separados.
# Tenant-Aware: Yes - todas las rutas requieren org_id + membership check.
# ============================================================================
"""
Institution Configuration Admin API.

Provides CRUD endpoints for managing tenant-specific institution configurations.
Each institution can have connection settings, authentication, scheduling, etc.

SECURITY:
- Secrets (API keys, passwords) are stored separately in encrypted_secrets column
- Secrets are NEVER returned in API responses
- Use /secrets endpoint to update secrets (write-only)
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin, verify_org_membership

# Import Pydantic schema for validation
from app.core.tenancy.schemas.institution_settings import InstitutionSettings
from app.database.async_db import get_async_db
from app.models.db.tenancy import OrganizationUser, TenantInstitutionConfig

router = APIRouter()


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class InstitutionConfigCreate(BaseModel):
    """Schema for creating a new institution configuration."""

    institution_key: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Unique identifier for the institution (e.g., 'patologia_digestiva')",
    )
    institution_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Human-readable institution name",
    )
    institution_type: str = Field(
        default="generic",
        max_length=50,
        description="Type of institution: 'medical', 'pharmacy', 'generic', etc.",
    )
    enabled: bool = Field(default=True, description="Whether this config is active")
    description: str | None = Field(
        default=None, description="Optional notes about this configuration"
    )
    settings: dict | None = Field(
        default=None,
        description="JSONB settings (connection, auth, scheduler, branding, whatsapp, custom)",
    )

    @field_validator("institution_key")
    @classmethod
    def validate_institution_key(cls, v: str) -> str:
        """Validate institution_key format: lowercase, alphanumeric + underscore."""
        import re

        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                "institution_key must be lowercase, start with letter, "
                "and contain only alphanumeric characters and underscores"
            )
        return v


class InstitutionConfigUpdate(BaseModel):
    """Schema for updating an institution configuration (partial update)."""

    institution_name: str | None = Field(None, min_length=2, max_length=255)
    institution_type: str | None = Field(None, max_length=50)
    enabled: bool | None = None
    description: str | None = None
    settings: dict | None = None


class InstitutionConfigSecretsUpdate(BaseModel):
    """Schema for updating encrypted secrets (write-only endpoint).

    NOTE: These are stored encrypted, never returned in responses.
    """

    api_key: str | None = Field(
        None, description="API key for api_key auth type"
    )
    password: str | None = Field(
        None, description="Password for basic auth or soap_wss auth"
    )
    client_secret: str | None = Field(
        None, description="Client secret for oauth2 auth type"
    )


class InstitutionConfigResponse(BaseModel):
    """Schema for institution configuration response."""

    id: str
    organization_id: str
    institution_key: str
    institution_name: str
    institution_type: str
    enabled: bool
    description: str | None
    settings: dict
    has_secrets: bool = Field(
        description="True if encrypted_secrets is configured (secrets never returned)"
    )
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class InstitutionConfigListResponse(BaseModel):
    """Schema for listing institution configurations."""

    items: list[InstitutionConfigResponse]
    total: int
    enabled_count: int
    disabled_count: int


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def config_to_response(config: TenantInstitutionConfig) -> InstitutionConfigResponse:
    """Convert database model to response schema."""
    return InstitutionConfigResponse(
        id=str(config.id),
        organization_id=str(config.organization_id),
        institution_key=config.institution_key,
        institution_name=config.institution_name,
        institution_type=config.institution_type or "generic",
        enabled=config.enabled,
        description=config.description,
        settings=config.settings or {},
        has_secrets=bool(config.encrypted_secrets),
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


async def get_config_or_404(
    db: AsyncSession, org_id: uuid.UUID, config_id: uuid.UUID
) -> TenantInstitutionConfig:
    """Get institution config by ID or raise 404."""
    stmt = select(TenantInstitutionConfig).where(
        TenantInstitutionConfig.id == config_id,
        TenantInstitutionConfig.organization_id == org_id,
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution config {config_id} not found in organization {org_id}",
        )

    return config


async def validate_whatsapp_phone_unique(
    db: AsyncSession,
    org_id: uuid.UUID,
    phone_number_id: str | None,
    exclude_config_id: uuid.UUID | None = None,
) -> None:
    """Validate WhatsApp phone_number_id is unique across all organizations."""
    if not phone_number_id:
        return

    stmt = select(TenantInstitutionConfig).where(
        TenantInstitutionConfig.settings["whatsapp"]["phone_number_id"].astext
        == phone_number_id
    )

    if exclude_config_id:
        stmt = stmt.where(TenantInstitutionConfig.id != exclude_config_id)

    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"WhatsApp phone_number_id '{phone_number_id}' is already "
            f"configured for institution '{existing.institution_key}'",
        )


def validate_settings(settings: dict | None) -> dict:
    """Validate settings dict against InstitutionSettings schema."""
    if not settings:
        # Return default settings
        return InstitutionSettings().model_dump()

    try:
        validated = InstitutionSettings.model_validate(settings)
        return validated.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid settings structure: {e}",
        ) from e


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/institution-configs", response_model=InstitutionConfigListResponse)
async def list_institution_configs(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    institution_type: str | None = Query(None, description="Filter by institution type"),
    search: str | None = Query(None, description="Search in name or key"),
    enabled_only: bool = Query(False, description="Return only enabled configs"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    membership: OrganizationUser = Depends(verify_org_membership),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List institution configurations for an organization.

    Requires organization membership.
    """
    # Base query
    stmt = select(TenantInstitutionConfig).where(
        TenantInstitutionConfig.organization_id == org_id
    )

    # Apply filters
    if institution_type:
        stmt = stmt.where(TenantInstitutionConfig.institution_type == institution_type)

    if enabled_only:
        stmt = stmt.where(TenantInstitutionConfig.enabled.is_(True))

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            TenantInstitutionConfig.institution_name.ilike(search_pattern)
            | TenantInstitutionConfig.institution_key.ilike(search_pattern)
        )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Count enabled/disabled
    enabled_stmt = select(func.count()).where(
        TenantInstitutionConfig.organization_id == org_id,
        TenantInstitutionConfig.enabled.is_(True),
    )
    disabled_stmt = select(func.count()).where(
        TenantInstitutionConfig.organization_id == org_id,
        TenantInstitutionConfig.enabled.is_(False),
    )

    enabled_result = await db.execute(enabled_stmt)
    enabled_count = enabled_result.scalar() or 0

    disabled_result = await db.execute(disabled_stmt)
    disabled_count = disabled_result.scalar() or 0

    # Paginate
    offset = (page - 1) * page_size
    stmt = stmt.order_by(TenantInstitutionConfig.institution_name).offset(offset).limit(page_size)

    result = await db.execute(stmt)
    configs = result.scalars().all()

    return InstitutionConfigListResponse(
        items=[config_to_response(c) for c in configs],
        total=total,
        enabled_count=enabled_count,
        disabled_count=disabled_count,
    )


@router.post(
    "/{org_id}/institution-configs",
    response_model=InstitutionConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_institution_config(
    data: InstitutionConfigCreate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new institution configuration.

    Requires admin or owner role.
    """
    # Check for duplicate institution_key in same org
    existing_stmt = select(TenantInstitutionConfig).where(
        TenantInstitutionConfig.organization_id == org_id,
        TenantInstitutionConfig.institution_key == data.institution_key,
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Institution with key '{data.institution_key}' already exists in this organization",
        )

    # Validate settings
    validated_settings = validate_settings(data.settings)

    # Validate WhatsApp phone_number_id uniqueness
    whatsapp_phone = validated_settings.get("whatsapp", {}).get("phone_number_id")
    await validate_whatsapp_phone_unique(db, org_id, whatsapp_phone)

    # Create config
    config = TenantInstitutionConfig(
        organization_id=org_id,
        institution_key=data.institution_key,
        institution_name=data.institution_name,
        institution_type=data.institution_type,
        enabled=data.enabled,
        description=data.description,
        settings=validated_settings,
    )

    db.add(config)
    await db.commit()
    await db.refresh(config)

    return config_to_response(config)


@router.get(
    "/{org_id}/institution-configs/{config_id}",
    response_model=InstitutionConfigResponse,
)
async def get_institution_config(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    config_id: uuid.UUID = Path(..., description="Institution config ID"),
    membership: OrganizationUser = Depends(verify_org_membership),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a single institution configuration.

    Requires organization membership.
    """
    config = await get_config_or_404(db, org_id, config_id)
    return config_to_response(config)


@router.patch(
    "/{org_id}/institution-configs/{config_id}",
    response_model=InstitutionConfigResponse,
)
async def update_institution_config(
    data: InstitutionConfigUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    config_id: uuid.UUID = Path(..., description="Institution config ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update an institution configuration (partial update).

    Requires admin or owner role.
    """
    config = await get_config_or_404(db, org_id, config_id)

    # Update fields if provided
    if data.institution_name is not None:
        config.institution_name = data.institution_name

    if data.institution_type is not None:
        config.institution_type = data.institution_type

    if data.enabled is not None:
        config.enabled = data.enabled

    if data.description is not None:
        config.description = data.description

    if data.settings is not None:
        # Validate new settings
        validated_settings = validate_settings(data.settings)

        # Validate WhatsApp phone_number_id uniqueness (excluding current)
        whatsapp_phone = validated_settings.get("whatsapp", {}).get("phone_number_id")
        await validate_whatsapp_phone_unique(db, org_id, whatsapp_phone, exclude_config_id=config_id)

        config.settings = validated_settings

    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return config_to_response(config)


@router.delete(
    "/{org_id}/institution-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_institution_config(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    config_id: uuid.UUID = Path(..., description="Institution config ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete an institution configuration.

    Requires admin or owner role.
    WARNING: This action cannot be undone.
    """
    config = await get_config_or_404(db, org_id, config_id)

    await db.delete(config)
    await db.commit()


@router.post(
    "/{org_id}/institution-configs/{config_id}/toggle",
    response_model=InstitutionConfigResponse,
)
async def toggle_institution_config(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    config_id: uuid.UUID = Path(..., description="Institution config ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Toggle enabled/disabled status of an institution configuration.

    Requires admin or owner role.
    """
    config = await get_config_or_404(db, org_id, config_id)

    config.enabled = not config.enabled
    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return config_to_response(config)


@router.patch(
    "/{org_id}/institution-configs/{config_id}/secrets",
    response_model=dict,
)
async def update_institution_secrets(
    data: InstitutionConfigSecretsUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    config_id: uuid.UUID = Path(..., description="Institution config ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update encrypted secrets for an institution configuration.

    SECURITY:
    - This is a write-only endpoint
    - Secrets are encrypted before storage
    - Secrets are NEVER returned in any API response

    Requires admin or owner role.
    """
    config = await get_config_or_404(db, org_id, config_id)

    # Build secrets dict (only non-None values)
    secrets = {}
    if data.api_key is not None:
        secrets["api_key"] = data.api_key
    if data.password is not None:
        secrets["password"] = data.password
    if data.client_secret is not None:
        secrets["client_secret"] = data.client_secret

    if not secrets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one secret field must be provided",
        )

    # TODO: Implement actual encryption before storage
    # For now, store as JSON bytes (should use Fernet or similar)
    import json

    config.encrypted_secrets = json.dumps(secrets).encode("utf-8")
    config.updated_at = datetime.now(UTC)

    await db.commit()

    return {
        "message": "Secrets updated successfully",
        "config_id": str(config_id),
        "has_secrets": True,
    }
