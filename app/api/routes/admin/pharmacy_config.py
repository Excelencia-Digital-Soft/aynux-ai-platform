# ============================================================================
# SCOPE: MULTI-TENANT
# Description: CRUD API for pharmacy configurations (PharmacyMerchantConfig).
#              Thin HTTP handler layer - delegates to services.
# Tenant-Aware: Yes - each pharmacy belongs to a specific organization.
# ============================================================================
"""Pharmacy Config Admin API - CRUD endpoints (thin controller)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_db
from app.api.pharmacy_auth import (
    is_system_admin,
    require_org_admin_for_create,
    require_pharmacy_admin_access,
    require_pharmacy_owner_access,
    require_pharmacy_read_access,
)
from app.api.schemas.pharmacy_config import (
    PharmacyConfigCreate,
    PharmacyConfigListResponse,
    PharmacyConfigResponse,
    PharmacyConfigUpdate,
)
from app.core.tenancy.pharmacy_bypass_service import PharmacyBypassService
from app.core.tenancy.pharmacy_repository import PharmacyRepository
from app.core.tenancy.pharmacy_service import PharmacyService
from app.database.async_db import get_async_db
from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig
from app.models.db.user import UserDB

router = APIRouter(tags=["Pharmacy Config"])


# ============================================================
# RESPONSE MAPPING
# ============================================================


def pharmacy_to_response(
    config: PharmacyMerchantConfig, org_name: str | None = None
) -> PharmacyConfigResponse:
    """Convert PharmacyMerchantConfig model to response with masked secrets."""
    return PharmacyConfigResponse(
        id=str(config.id),
        organization_id=str(config.organization_id),
        organization_name=org_name,
        pharmacy_name=config.pharmacy_name,
        pharmacy_address=config.pharmacy_address,
        pharmacy_phone=config.pharmacy_phone,
        pharmacy_logo_path=config.pharmacy_logo_path,
        # Contact and hours info
        pharmacy_email=config.pharmacy_email,
        pharmacy_website=config.pharmacy_website,
        pharmacy_hours=config.pharmacy_hours,
        pharmacy_is_24h=config.pharmacy_is_24h,
        # Mercado Pago
        mp_enabled=config.mp_enabled,
        mp_sandbox=config.mp_sandbox,
        mp_timeout=config.mp_timeout,
        mp_notification_url=config.mp_notification_url,
        receipt_public_url_base=config.receipt_public_url_base,
        has_mp_credentials=bool(config.mp_access_token),
        mp_access_token="***" if config.mp_access_token else None,
        mp_public_key="***" if config.mp_public_key else None,
        mp_webhook_secret="***" if config.mp_webhook_secret else None,
        whatsapp_phone_number=config.whatsapp_phone_number,
        created_at=config.created_at.isoformat() if config.created_at else None,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


# ============================================================
# SERVICE FACTORY
# ============================================================


def get_service(db: AsyncSession) -> PharmacyService:
    """Factory for PharmacyService with dependencies."""
    return PharmacyService(
        repository=PharmacyRepository(db),
        bypass_service=PharmacyBypassService(db),
    )


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("", response_model=PharmacyConfigListResponse)
async def list_pharmacy_configs(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=25, ge=1, le=100, description="Items per page"),
    search: str | None = Query(default=None, description="Search by name or phone"),
    mp_enabled: bool | None = Query(default=None, description="Filter by MP enabled status"),
    user: Annotated[UserDB, Depends(get_current_user_db)] = None,
    db: Annotated[AsyncSession, Depends(get_async_db)] = None,
):
    """
    List pharmacy configurations accessible by the current user.

    - System admins (scope "admin") can see ALL pharmacies
    - Regular users only see pharmacies for organizations they belong to
    Supports pagination and filtering by name/phone and MP status.
    """
    service = get_service(db)
    result = await service.list_for_user(
        user_id=user.id,
        is_system_admin=is_system_admin(user),
        search=search,
        mp_enabled=mp_enabled,
        page=page,
        page_size=page_size,
    )
    return PharmacyConfigListResponse(
        pharmacies=[
            pharmacy_to_response(p, p.organization.name if p.organization else None)
            for p in result.pharmacies
        ],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


@router.get("/{pharmacy_id}", response_model=PharmacyConfigResponse)
async def get_pharmacy_config(
    config: Annotated[PharmacyMerchantConfig, Depends(require_pharmacy_read_access)],
):
    """
    Get a pharmacy configuration by ID.

    Returns full configuration with secrets masked.
    """
    org_name = config.organization.name if config.organization else None
    return pharmacy_to_response(config, org_name)


@router.post("", response_model=PharmacyConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_pharmacy_config(
    data: PharmacyConfigCreate,
    user: Annotated[UserDB, Depends(get_current_user_db)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
):
    """
    Create a new pharmacy configuration.

    Organizations can have multiple pharmacy configurations.
    - System admins can create for any organization
    - Regular users require admin/owner role in the organization
    """
    org_uuid = await require_org_admin_for_create(data.organization_id, user, db)

    repo = PharmacyRepository(db)
    org = await repo.get_organization(org_uuid)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    service = get_service(db)
    config = await service.create(data, org_uuid)
    return pharmacy_to_response(config, org.name)


@router.patch("/{pharmacy_id}", response_model=PharmacyConfigResponse)
async def update_pharmacy_config(
    data: PharmacyConfigUpdate,
    config: Annotated[PharmacyMerchantConfig, Depends(require_pharmacy_admin_access)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
):
    """
    Update a pharmacy configuration.

    Partial update - only provided fields are updated.
    - System admins can update any pharmacy
    - Regular users require admin role in the organization
    """
    service = get_service(db)
    updated = await service.update(config, data)
    org_name = config.organization.name if config.organization else None
    return pharmacy_to_response(updated, org_name)


@router.delete("/{pharmacy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pharmacy_config(
    config: Annotated[PharmacyMerchantConfig, Depends(require_pharmacy_owner_access)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
):
    """
    Delete a pharmacy configuration.

    - System admins can delete any pharmacy
    - Regular users require owner role in the organization
    """
    service = get_service(db)
    await service.delete(config)
