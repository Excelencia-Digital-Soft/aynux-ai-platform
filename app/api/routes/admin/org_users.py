"""
Organization Users Admin API - Manage users within organizations.

Provides endpoints for inviting users, managing roles, and removing members.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_user_db,
    get_organization_by_id,
    require_admin,
    require_owner,
)
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization, OrganizationUser
from app.models.db.user import UserDB

router = APIRouter(tags=["Organization Users"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class UserInvite(BaseModel):
    """Schema for inviting a user to an organization."""

    email: EmailStr = Field(..., description="Email of the user to invite")
    role: Literal["admin", "member"] = Field(default="member", description="Role to assign")


class UserRoleUpdate(BaseModel):
    """Schema for updating a user's role."""

    role: Literal["owner", "admin", "member"] = Field(..., description="New role to assign")


class OrgUserResponse(BaseModel):
    """Schema for organization user response."""

    id: str
    user_id: str
    username: str
    email: str
    full_name: str | None
    role: str
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class OrgUserListResponse(BaseModel):
    """Schema for organization users list response."""

    users: list[OrgUserResponse]
    total: int


class InviteResponse(BaseModel):
    """Schema for invite response."""

    message: str
    user_id: str
    role: str


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/users", response_model=OrgUserListResponse)
async def list_organization_users(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all users in an organization.

    Requires admin or owner role.
    """
    stmt = (
        select(OrganizationUser)
        .where(OrganizationUser.organization_id == org_id)
        .options(selectinload(OrganizationUser.user))
        .order_by(OrganizationUser.created_at)
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    users = []
    for m in memberships:
        if m.user:
            users.append(
                OrgUserResponse(
                    id=str(m.id),
                    user_id=str(m.user_id),
                    username=m.user.username,
                    email=m.user.email,
                    full_name=m.user.full_name,
                    role=m.role,
                    created_at=m.created_at.isoformat() if m.created_at else None,
                    updated_at=m.updated_at.isoformat() if m.updated_at else None,
                )
            )

    return OrgUserListResponse(users=users, total=len(users))


@router.post("/{org_id}/users/invite", response_model=InviteResponse)
async def invite_user(
    data: UserInvite,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    org: Organization = Depends(get_organization_by_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Invite a user to the organization.

    If the user exists, they are added to the organization.
    Requires admin or owner role.
    """
    # Check user quota
    stmt = select(OrganizationUser).where(OrganizationUser.organization_id == org_id)
    result = await db.execute(stmt)
    current_count = len(result.scalars().all())

    if current_count >= org.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Límite de usuarios alcanzado ({org.max_users})",
        )

    # Find user by email
    stmt = select(UserDB).where(UserDB.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con email {data.email} no encontrado. El usuario debe registrarse primero.",
        )

    # Check if already a member
    stmt = select(OrganizationUser).where(
        OrganizationUser.organization_id == org_id,
        OrganizationUser.user_id == user.id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya es miembro de esta organización",
        )

    # Create membership
    new_membership = OrganizationUser(
        id=uuid.uuid4(),
        organization_id=org_id,
        user_id=user.id,
        role=data.role,
        personal_settings={},
    )
    db.add(new_membership)
    await db.commit()

    return InviteResponse(
        message=f"Usuario {user.email} agregado exitosamente",
        user_id=str(user.id),
        role=data.role,
    )


@router.get("/{org_id}/users/{user_id}", response_model=OrgUserResponse)
async def get_organization_user(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    user_id: uuid.UUID = Path(..., description="User ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific user's membership in the organization.

    Requires admin or owner role.
    """
    stmt = (
        select(OrganizationUser)
        .where(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == user_id,
        )
        .options(selectinload(OrganizationUser.user))
    )
    result = await db.execute(stmt)
    target_membership = result.scalar_one_or_none()

    if not target_membership or not target_membership.user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en esta organización",
        )

    return OrgUserResponse(
        id=str(target_membership.id),
        user_id=str(target_membership.user_id),
        username=target_membership.user.username,
        email=target_membership.user.email,
        full_name=target_membership.user.full_name,
        role=target_membership.role,
        created_at=target_membership.created_at.isoformat() if target_membership.created_at else None,
        updated_at=target_membership.updated_at.isoformat() if target_membership.updated_at else None,
    )


@router.put("/{org_id}/users/{user_id}", response_model=OrgUserResponse)
async def update_user_role(
    data: UserRoleUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    user_id: uuid.UUID = Path(..., description="User ID"),
    membership: OrganizationUser = Depends(require_owner),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update a user's role in the organization.

    Requires owner role. Owner cannot change their own role.
    """
    # Get target user's membership
    stmt = (
        select(OrganizationUser)
        .where(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == user_id,
        )
        .options(selectinload(OrganizationUser.user))
    )
    result = await db.execute(stmt)
    target_membership = result.scalar_one_or_none()

    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en esta organización",
        )

    # Prevent owner from changing their own role
    if target_membership.user_id == membership.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol",
        )

    # Prevent creating a second owner (transfer ownership would be a separate endpoint)
    if data.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes asignar el rol de propietario. Usa transferir propiedad en su lugar.",
        )

    target_membership.role = data.role
    target_membership.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(target_membership)

    return OrgUserResponse(
        id=str(target_membership.id),
        user_id=str(target_membership.user_id),
        username=target_membership.user.username,
        email=target_membership.user.email,
        full_name=target_membership.user.full_name,
        role=target_membership.role,
        created_at=target_membership.created_at.isoformat() if target_membership.created_at else None,
        updated_at=target_membership.updated_at.isoformat() if target_membership.updated_at else None,
    )


@router.delete("/{org_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    user_id: uuid.UUID = Path(..., description="User ID"),
    membership: OrganizationUser = Depends(require_admin),
    current_user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Remove a user from the organization.

    Admins can remove members. Only owner can remove admins.
    Owner cannot be removed. Users can remove themselves.
    """
    # Get target user's membership
    stmt = select(OrganizationUser).where(
        OrganizationUser.organization_id == org_id,
        OrganizationUser.user_id == user_id,
    )
    result = await db.execute(stmt)
    target_membership = result.scalar_one_or_none()

    if not target_membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en esta organización",
        )

    # Cannot remove the owner
    if target_membership.is_owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar al propietario de la organización",
        )

    # Admin removing admin requires owner permission
    if target_membership.role == "admin" and membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el propietario puede eliminar administradores",
        )

    await db.delete(target_membership)
    await db.commit()
