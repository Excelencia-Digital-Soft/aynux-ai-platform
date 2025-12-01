"""
Tenant Prompts Admin API - Manage prompts per organization.

Provides endpoints for creating and managing tenant-specific prompt overrides.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.database.async_db import get_async_db
from app.models.db.tenancy import OrganizationUser, TenantPrompt

router = APIRouter(tags=["Tenant Prompts"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class TenantPromptCreate(BaseModel):
    """Schema for creating a tenant prompt override."""

    prompt_key: str = Field(..., min_length=1, max_length=255, description="Prompt identifier (e.g., 'greeting.welcome')")
    template: str = Field(..., min_length=1, description="Prompt template text with {variables}")
    scope: Literal["org", "user"] = Field(default="org", description="Prompt scope level")
    user_id: str | None = Field(None, description="User ID (required if scope='user')")
    description: str | None = Field(None, max_length=1000)
    meta_data: dict = Field(default_factory=dict)


class TenantPromptUpdate(BaseModel):
    """Schema for updating a tenant prompt."""

    template: str | None = Field(None, min_length=1)
    description: str | None = Field(None, max_length=1000)
    meta_data: dict | None = None
    is_active: bool | None = None


class TenantPromptResponse(BaseModel):
    """Schema for tenant prompt response."""

    id: str
    organization_id: str
    prompt_key: str
    scope: str
    user_id: str | None
    template: str
    description: str | None
    version: int
    meta_data: dict
    is_active: bool
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class TenantPromptListResponse(BaseModel):
    """Schema for tenant prompt list response."""

    prompts: list[TenantPromptResponse]
    total: int
    by_scope: dict[str, int]


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/prompts", response_model=TenantPromptListResponse)
async def list_tenant_prompts(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    scope: Literal["org", "user"] | None = Query(None, description="Filter by scope"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all prompt overrides for the organization.

    Requires admin or owner role.
    """
    stmt = select(TenantPrompt).where(TenantPrompt.organization_id == org_id)

    if scope:
        stmt = stmt.where(TenantPrompt.scope == scope)

    stmt = stmt.order_by(TenantPrompt.prompt_key)
    result = await db.execute(stmt)
    prompts = result.scalars().all()

    prompts_list = []
    by_scope: dict[str, int] = {"org": 0, "user": 0}

    for p in prompts:
        prompts_list.append(
            TenantPromptResponse(
                id=str(p.id),
                organization_id=str(p.organization_id),
                prompt_key=p.prompt_key,
                scope=p.scope,
                user_id=str(p.user_id) if p.user_id else None,
                template=p.template,
                description=p.description,
                version=p.version,
                meta_data=p.meta_data or {},
                is_active=p.is_active,
                created_at=p.created_at.isoformat() if p.created_at else None,
                updated_at=p.updated_at.isoformat() if p.updated_at else None,
            )
        )
        if p.scope in by_scope:
            by_scope[p.scope] += 1

    return TenantPromptListResponse(
        prompts=prompts_list,
        total=len(prompts_list),
        by_scope=by_scope,
    )


@router.post("/{org_id}/prompts", response_model=TenantPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_prompt(
    data: TenantPromptCreate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new prompt override.

    Requires admin or owner role.
    """
    # Validate user_id if scope is "user"
    user_id = None
    if data.scope == "user":
        if not data.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id es requerido cuando scope='user'",
            )
        try:
            user_id = uuid.UUID(data.user_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id inválido",
            ) from e

    # Check if prompt already exists for this scope
    stmt = select(TenantPrompt).where(
        TenantPrompt.organization_id == org_id,
        TenantPrompt.prompt_key == data.prompt_key,
        TenantPrompt.scope == data.scope,
    )
    if user_id:
        stmt = stmt.where(TenantPrompt.user_id == user_id)

    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt '{data.prompt_key}' ya existe para el scope '{data.scope}'",
        )

    prompt = TenantPrompt(
        id=uuid.uuid4(),
        organization_id=org_id,
        prompt_key=data.prompt_key,
        scope=data.scope,
        user_id=user_id,
        template=data.template,
        description=data.description,
        version=1,
        meta_data=data.meta_data,
        is_active=True,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)

    return TenantPromptResponse(
        id=str(prompt.id),
        organization_id=str(prompt.organization_id),
        prompt_key=prompt.prompt_key,
        scope=prompt.scope,
        user_id=str(prompt.user_id) if prompt.user_id else None,
        template=prompt.template,
        description=prompt.description,
        version=prompt.version,
        meta_data=prompt.meta_data or {},
        is_active=prompt.is_active,
        created_at=prompt.created_at.isoformat() if prompt.created_at else None,
        updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
    )


@router.get("/{org_id}/prompts/{prompt_id}", response_model=TenantPromptResponse)
async def get_tenant_prompt(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    prompt_id: uuid.UUID = Path(..., description="Prompt ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific prompt override.

    Requires admin or owner role.
    """
    stmt = select(TenantPrompt).where(
        TenantPrompt.organization_id == org_id,
        TenantPrompt.id == prompt_id,
    )
    result = await db.execute(stmt)
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt no encontrado",
        )

    return TenantPromptResponse(
        id=str(prompt.id),
        organization_id=str(prompt.organization_id),
        prompt_key=prompt.prompt_key,
        scope=prompt.scope,
        user_id=str(prompt.user_id) if prompt.user_id else None,
        template=prompt.template,
        description=prompt.description,
        version=prompt.version,
        meta_data=prompt.meta_data or {},
        is_active=prompt.is_active,
        created_at=prompt.created_at.isoformat() if prompt.created_at else None,
        updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
    )


@router.put("/{org_id}/prompts/{prompt_id}", response_model=TenantPromptResponse)
async def update_tenant_prompt(
    data: TenantPromptUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    prompt_id: uuid.UUID = Path(..., description="Prompt ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update a prompt override.

    Requires admin or owner role.
    Increments version when template is changed.
    """
    stmt = select(TenantPrompt).where(
        TenantPrompt.organization_id == org_id,
        TenantPrompt.id == prompt_id,
    )
    result = await db.execute(stmt)
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt no encontrado",
        )

    if data.template is not None and data.template != prompt.template:
        prompt.template = data.template
        prompt.version += 1  # Increment version on template change

    if data.description is not None:
        prompt.description = data.description
    if data.meta_data is not None:
        prompt.meta_data = data.meta_data
    if data.is_active is not None:
        prompt.is_active = data.is_active

    prompt.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(prompt)

    return TenantPromptResponse(
        id=str(prompt.id),
        organization_id=str(prompt.organization_id),
        prompt_key=prompt.prompt_key,
        scope=prompt.scope,
        user_id=str(prompt.user_id) if prompt.user_id else None,
        template=prompt.template,
        description=prompt.description,
        version=prompt.version,
        meta_data=prompt.meta_data or {},
        is_active=prompt.is_active,
        created_at=prompt.created_at.isoformat() if prompt.created_at else None,
        updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
    )


@router.delete("/{org_id}/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_prompt(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    prompt_id: uuid.UUID = Path(..., description="Prompt ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a prompt override.

    Requires admin or owner role.
    Deleting an override will cause the system to fall back to lower scope prompts.
    """
    stmt = select(TenantPrompt).where(
        TenantPrompt.organization_id == org_id,
        TenantPrompt.id == prompt_id,
    )
    result = await db.execute(stmt)
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt no encontrado",
        )

    await db.delete(prompt)
    await db.commit()


@router.get("/{org_id}/prompts/by-key/{prompt_key}", response_model=TenantPromptResponse)
async def get_prompt_by_key(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    prompt_key: str = Path(..., description="Prompt key"),
    scope: Literal["org", "user"] = Query(default="org", description="Prompt scope"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a prompt by its key and scope.

    Requires admin or owner role.
    """
    stmt = select(TenantPrompt).where(
        TenantPrompt.organization_id == org_id,
        TenantPrompt.prompt_key == prompt_key,
        TenantPrompt.scope == scope,
    )
    result = await db.execute(stmt)
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{prompt_key}' no encontrado para scope '{scope}'",
        )

    return TenantPromptResponse(
        id=str(prompt.id),
        organization_id=str(prompt.organization_id),
        prompt_key=prompt.prompt_key,
        scope=prompt.scope,
        user_id=str(prompt.user_id) if prompt.user_id else None,
        template=prompt.template,
        description=prompt.description,
        version=prompt.version,
        meta_data=prompt.meta_data or {},
        is_active=prompt.is_active,
        created_at=prompt.created_at.isoformat() if prompt.created_at else None,
        updated_at=prompt.updated_at.isoformat() if prompt.updated_at else None,
    )
