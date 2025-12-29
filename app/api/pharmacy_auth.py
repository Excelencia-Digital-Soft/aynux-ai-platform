# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Authorization dependencies for pharmacy endpoints.
#              Provides FastAPI Depends for role-based access control.
# Tenant-Aware: Yes - validates user membership in organizations.
# ============================================================================
"""Authorization dependencies for pharmacy endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_db
from app.core.tenancy.pharmacy_repository import PharmacyRepository
from app.database.async_db import get_async_db
from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig
from app.models.db.user import UserDB


def is_system_admin(user: UserDB) -> bool:
    """
    Check if user has system admin scope.

    Args:
        user: UserDB instance

    Returns:
        True if user has "admin" scope, False otherwise
    """
    return "admin" in (user.scopes or [])


async def require_pharmacy_read_access(
    pharmacy_id: str,
    user: Annotated[UserDB, Depends(get_current_user_db)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PharmacyMerchantConfig:
    """
    Get pharmacy and verify user can read it.

    Authorization rules:
    - System admins can access any pharmacy
    - Regular users need membership in the pharmacy's organization

    Args:
        pharmacy_id: UUID string of the pharmacy
        user: Current authenticated user
        db: Database session

    Returns:
        PharmacyMerchantConfig if authorized

    Raises:
        HTTPException 400: Invalid pharmacy ID format
        HTTPException 404: Pharmacy not found
        HTTPException 403: Not authorized to access
    """
    try:
        pharmacy_uuid = uuid.UUID(pharmacy_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pharmacy ID format",
        ) from e

    repo = PharmacyRepository(db)
    config = await repo.get_by_id(pharmacy_uuid)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pharmacy configuration not found",
        )

    if is_system_admin(user):
        return config

    membership = await repo.get_user_membership(user.id, config.organization_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this pharmacy",
        )

    return config


async def require_pharmacy_admin_access(
    pharmacy_id: str,
    user: Annotated[UserDB, Depends(get_current_user_db)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PharmacyMerchantConfig:
    """
    Get pharmacy and verify user can modify it.

    Authorization rules:
    - System admins can modify any pharmacy
    - Regular users need admin/owner role in the organization

    Args:
        pharmacy_id: UUID string of the pharmacy
        user: Current authenticated user
        db: Database session

    Returns:
        PharmacyMerchantConfig if authorized

    Raises:
        HTTPException 400: Invalid pharmacy ID format
        HTTPException 404: Pharmacy not found
        HTTPException 403: Not authorized or insufficient role
    """
    config = await require_pharmacy_read_access(pharmacy_id, user, db)

    if is_system_admin(user):
        return config

    repo = PharmacyRepository(db)
    membership = await repo.get_user_membership(user.id, config.organization_id)

    if not membership or membership.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to update pharmacy configuration",
        )

    return config


async def require_pharmacy_owner_access(
    pharmacy_id: str,
    user: Annotated[UserDB, Depends(get_current_user_db)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PharmacyMerchantConfig:
    """
    Get pharmacy and verify user can delete it.

    Authorization rules:
    - System admins can delete any pharmacy
    - Regular users need owner role in the organization

    Args:
        pharmacy_id: UUID string of the pharmacy
        user: Current authenticated user
        db: Database session

    Returns:
        PharmacyMerchantConfig if authorized

    Raises:
        HTTPException 400: Invalid pharmacy ID format
        HTTPException 404: Pharmacy not found
        HTTPException 403: Not authorized or insufficient role
    """
    config = await require_pharmacy_read_access(pharmacy_id, user, db)

    if is_system_admin(user):
        return config

    repo = PharmacyRepository(db)
    membership = await repo.get_user_membership(user.id, config.organization_id)

    if not membership or membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner role required to delete pharmacy configuration",
        )

    return config


async def require_org_admin_for_create(
    organization_id: str,
    user: UserDB,
    db: AsyncSession,
) -> uuid.UUID:
    """
    Verify user can create pharmacy in organization.

    Authorization rules:
    - System admins can create in any organization
    - Regular users need admin/owner role in the organization

    Note: This is not a FastAPI Depends function - it's called directly
    from the create endpoint since organization_id comes from the request body.

    Args:
        organization_id: UUID string of the organization
        user: Current authenticated user
        db: Database session

    Returns:
        Validated organization UUID

    Raises:
        HTTPException 400: Invalid organization ID format
        HTTPException 403: Not a member or insufficient role
    """
    try:
        org_uuid = uuid.UUID(organization_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format",
        ) from e

    if is_system_admin(user):
        return org_uuid

    repo = PharmacyRepository(db)
    membership = await repo.get_user_membership(user.id, org_uuid)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    if membership.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to create pharmacy configuration",
        )

    return org_uuid
