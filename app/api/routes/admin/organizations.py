# ============================================================================
# SCOPE: MULTI-TENANT
# Description: CRUD API para organizaciones (tenants) del sistema multi-tenant.
#              Crear, listar, actualizar, eliminar organizaciones.
# Tenant-Aware: Yes - es la API de gestión de tenants.
# ============================================================================
"""
Organization Admin API - CRUD operations for organizations.

Provides endpoints for managing organizations in the multi-tenant system.
"""

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import (
    get_current_user_db,
    get_organization_by_id,
    require_admin,
    require_owner,
    token_service,
    verify_org_membership,
)
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization, OrganizationUser, TenantConfig
from app.models.db.user import UserDB

router = APIRouter(tags=["Organizations"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class OrganizationCreate(BaseModel):
    """Schema for creating a new organization."""

    name: str = Field(..., min_length=2, max_length=255, description="Organization name")
    slug: str | None = Field(
        None, min_length=2, max_length=50, pattern=r"^[a-z0-9-]+$", description="URL-friendly identifier"
    )
    display_name: str | None = Field(None, max_length=255, description="Display name for UI")
    llm_model: str = Field(default="llama3.2:1b", description="Default LLM model")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="LLM temperature")


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""

    name: str | None = Field(None, min_length=2, max_length=255)
    display_name: str | None = Field(None, max_length=255)
    llm_model: str | None = None
    llm_temperature: float | None = Field(None, ge=0.0, le=1.0)
    llm_max_tokens: int | None = Field(None, ge=100, le=8192)
    features: dict | None = None
    max_users: int | None = Field(None, ge=1, le=1000)
    max_documents: int | None = Field(None, ge=1, le=100000)
    max_agents: int | None = Field(None, ge=1, le=100)


class OrganizationResponse(BaseModel):
    """Schema for organization response."""

    id: str
    slug: str
    name: str
    display_name: str | None
    mode: str
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    features: dict
    max_users: int
    max_documents: int
    max_agents: int
    status: str
    trial_ends_at: str | None
    created_at: str | None
    updated_at: str | None
    role: str | None = None  # User's role in this org (for list)

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """Schema for organization list response."""

    organizations: list[OrganizationResponse]
    total: int


class SwitchOrganizationResponse(BaseModel):
    """Schema for switch organization response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    organization: OrganizationResponse


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from organization name."""
    # Convert to lowercase and replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)  # Remove special chars
    slug = re.sub(r"[\s_]+", "-", slug)  # Replace spaces/underscores with hyphens
    slug = re.sub(r"-+", "-", slug)  # Remove multiple hyphens
    slug = slug.strip("-")  # Remove leading/trailing hyphens
    return slug[:50]  # Limit length


async def ensure_unique_slug(db: AsyncSession, slug: str, exclude_id: uuid.UUID | None = None) -> str:
    """Ensure slug is unique, appending numbers if necessary."""
    original_slug = slug
    counter = 1

    while True:
        stmt = select(Organization).where(Organization.slug == slug)
        if exclude_id:
            stmt = stmt.where(Organization.id != exclude_id)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if not existing:
            return slug

        slug = f"{original_slug}-{counter}"
        counter += 1

        if counter > 100:
            # Fallback to UUID suffix
            return f"{original_slug}-{uuid.uuid4().hex[:8]}"


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all organizations the current user belongs to.

    Returns organizations with the user's role in each.
    """
    # Get all memberships for this user
    stmt = (
        select(OrganizationUser)
        .where(OrganizationUser.user_id == user.id)
        .options(selectinload(OrganizationUser.organization))
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    organizations = []
    for membership in memberships:
        org = membership.organization
        if org:
            org_dict = org.to_dict()
            org_dict["role"] = membership.role
            organizations.append(OrganizationResponse(**org_dict))

    return OrganizationListResponse(organizations=organizations, total=len(organizations))


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    user: UserDB = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new organization.

    The creating user becomes the owner of the organization.
    A default TenantConfig is also created.
    """
    # Generate slug if not provided
    slug = data.slug or generate_slug(data.name)
    slug = await ensure_unique_slug(db, slug)

    # Create organization
    org = Organization(
        id=uuid.uuid4(),
        slug=slug,
        name=data.name,
        display_name=data.display_name,
        mode="multi_tenant",
        llm_model=data.llm_model,
        llm_temperature=data.llm_temperature,
        status="active",
        features={},
    )
    db.add(org)

    # Create owner membership
    membership = OrganizationUser(
        id=uuid.uuid4(),
        organization_id=org.id,
        user_id=user.id,
        role="owner",
        personal_settings={},
    )
    db.add(membership)

    # Create default TenantConfig
    config = TenantConfig(
        id=uuid.uuid4(),
        organization_id=org.id,
        enabled_domains=["excelencia"],
        default_domain="excelencia",
        enabled_agent_types=[
            "greeting_agent",
            "product_agent",
            "support_agent",
            "fallback_agent",
            "farewell_agent",
        ],
        rag_enabled=True,
        rag_similarity_threshold=0.7,
        rag_max_results=5,
        prompt_scope="org",
        advanced_config={},
    )
    db.add(config)

    await db.commit()
    await db.refresh(org)

    org_dict = org.to_dict()
    org_dict["role"] = "owner"
    return OrganizationResponse(**org_dict)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    membership: OrganizationUser = Depends(verify_org_membership),
    org: Organization = Depends(get_organization_by_id),
):
    """
    Get organization details.

    Requires membership in the organization.
    """
    org_dict = org.to_dict()
    org_dict["role"] = membership.role
    return OrganizationResponse(**org_dict)


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    data: OrganizationUpdate,
    membership: OrganizationUser = Depends(require_admin),
    org: Organization = Depends(get_organization_by_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update organization settings.

    Requires admin or owner role.
    """
    # Update fields if provided
    if data.name is not None:
        org.name = data.name
    if data.display_name is not None:
        org.display_name = data.display_name
    if data.llm_model is not None:
        org.llm_model = data.llm_model
    if data.llm_temperature is not None:
        org.llm_temperature = data.llm_temperature
    if data.llm_max_tokens is not None:
        org.llm_max_tokens = data.llm_max_tokens
    if data.features is not None:
        org.features = data.features
    if data.max_users is not None:
        org.max_users = data.max_users
    if data.max_documents is not None:
        org.max_documents = data.max_documents
    if data.max_agents is not None:
        org.max_agents = data.max_agents

    org.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(org)

    org_dict = org.to_dict()
    org_dict["role"] = membership.role
    return OrganizationResponse(**org_dict)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    membership: OrganizationUser = Depends(require_owner),
    org: Organization = Depends(get_organization_by_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete an organization.

    Requires owner role. This will cascade delete all related data.
    """
    await db.delete(org)
    await db.commit()


@router.post("/{org_id}/switch", response_model=SwitchOrganizationResponse)
async def switch_organization(
    membership: OrganizationUser = Depends(verify_org_membership),
    org: Organization = Depends(get_organization_by_id),
    user: UserDB = Depends(get_current_user_db),
):
    """
    Switch to a different organization.

    Returns new tokens with the organization context.
    Requires membership in the target organization.
    """
    # Create new tokens with organization context
    access_token = token_service.create_access_token_with_org(
        user_id=str(user.id),
        username=user.username,
        org_id=str(org.id),
        role=membership.role,
        scopes=user.scopes or [],
    )
    refresh_token = token_service.create_refresh_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "org_id": str(org.id),
            "role": membership.role,
            "scopes": user.scopes or [],
        }
    )

    org_dict = org.to_dict()
    org_dict["role"] = membership.role

    return SwitchOrganizationResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        organization=OrganizationResponse(**org_dict),
    )
