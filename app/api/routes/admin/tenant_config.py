"""
Tenant Configuration Admin API - Manage tenant-specific settings.

Provides endpoints for managing domains, RAG, LLM, and other tenant configurations.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_organization_by_id, require_admin
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization, OrganizationUser, TenantConfig

router = APIRouter(tags=["Tenant Configuration"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class TenantConfigResponse(BaseModel):
    """Schema for tenant configuration response."""

    id: str
    organization_id: str
    enabled_domains: list[str]
    default_domain: str
    enabled_agent_types: list[str]
    agent_timeout_seconds: int
    rag_enabled: bool
    rag_similarity_threshold: float
    rag_max_results: int
    prompt_scope: str
    whatsapp_phone_number_id: str | None
    whatsapp_verify_token: str | None  # Masked
    advanced_config: dict
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class TenantConfigUpdate(BaseModel):
    """Schema for updating tenant configuration."""

    enabled_domains: list[str] | None = None
    default_domain: str | None = None
    enabled_agent_types: list[str] | None = None
    agent_timeout_seconds: int | None = Field(None, ge=5, le=300)
    rag_enabled: bool | None = None
    rag_similarity_threshold: float | None = Field(None, ge=0.0, le=1.0)
    rag_max_results: int | None = Field(None, ge=1, le=50)
    prompt_scope: Literal["system", "global", "org"] | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str | None = None
    advanced_config: dict | None = None


class LLMConfigUpdate(BaseModel):
    """Schema for updating LLM configuration."""

    llm_model: str | None = None
    llm_temperature: float | None = Field(None, ge=0.0, le=1.0)
    llm_max_tokens: int | None = Field(None, ge=100, le=8192)


class RAGConfigUpdate(BaseModel):
    """Schema for updating RAG configuration."""

    rag_enabled: bool | None = None
    rag_similarity_threshold: float | None = Field(None, ge=0.0, le=1.0)
    rag_max_results: int | None = Field(None, ge=1, le=50)


class DomainsConfigUpdate(BaseModel):
    """Schema for updating domains configuration."""

    enabled_domains: list[str] = Field(..., min_length=1)
    default_domain: str | None = None


class AgentsConfigUpdate(BaseModel):
    """Schema for updating agents configuration."""

    enabled_agent_types: list[str]


# ============================================================
# HELPER FUNCTIONS
# ============================================================


async def get_or_create_config(db: AsyncSession, org_id: uuid.UUID) -> TenantConfig:
    """Get existing config or create default one."""
    stmt = select(TenantConfig).where(TenantConfig.organization_id == org_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        config = TenantConfig.create_default(org_id)
        db.add(config)
        await db.commit()
        await db.refresh(config)

    return config


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/config", response_model=TenantConfigResponse)
async def get_tenant_config(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get tenant configuration.

    Requires admin or owner role.
    """
    config = await get_or_create_config(db, org_id)
    return TenantConfigResponse(**config.to_dict())


@router.put("/{org_id}/config", response_model=TenantConfigResponse)
async def update_tenant_config(
    data: TenantConfigUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update tenant configuration.

    Requires admin or owner role.
    """
    config = await get_or_create_config(db, org_id)

    # Update fields if provided
    if data.enabled_domains is not None:
        config.enabled_domains = data.enabled_domains
    if data.default_domain is not None:
        # Validate default_domain is in enabled_domains
        domains = data.enabled_domains if data.enabled_domains is not None else config.enabled_domains
        if data.default_domain not in domains:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"default_domain '{data.default_domain}' must be in enabled_domains",
            )
        config.default_domain = data.default_domain
    if data.enabled_agent_types is not None:
        config.enabled_agent_types = data.enabled_agent_types
    if data.agent_timeout_seconds is not None:
        config.agent_timeout_seconds = data.agent_timeout_seconds
    if data.rag_enabled is not None:
        config.rag_enabled = data.rag_enabled
    if data.rag_similarity_threshold is not None:
        config.rag_similarity_threshold = data.rag_similarity_threshold
    if data.rag_max_results is not None:
        config.rag_max_results = data.rag_max_results
    if data.prompt_scope is not None:
        config.prompt_scope = data.prompt_scope
    if data.whatsapp_phone_number_id is not None:
        config.whatsapp_phone_number_id = data.whatsapp_phone_number_id
    if data.whatsapp_verify_token is not None:
        config.whatsapp_verify_token = data.whatsapp_verify_token
    if data.advanced_config is not None:
        config.advanced_config = data.advanced_config

    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return TenantConfigResponse(**config.to_dict())


@router.put("/{org_id}/config/llm", response_model=dict)
async def update_llm_config(
    data: LLMConfigUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    org: Organization = Depends(get_organization_by_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update LLM configuration for the organization.

    LLM settings are stored on the Organization model.
    Requires admin or owner role.
    """
    if data.llm_model is not None:
        org.llm_model = data.llm_model
    if data.llm_temperature is not None:
        org.llm_temperature = data.llm_temperature
    if data.llm_max_tokens is not None:
        org.llm_max_tokens = data.llm_max_tokens

    org.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(org)

    return {
        "llm_model": org.llm_model,
        "llm_temperature": org.llm_temperature,
        "llm_max_tokens": org.llm_max_tokens,
    }


@router.put("/{org_id}/config/rag", response_model=dict)
async def update_rag_config(
    data: RAGConfigUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update RAG configuration.

    Requires admin or owner role.
    """
    config = await get_or_create_config(db, org_id)

    if data.rag_enabled is not None:
        config.rag_enabled = data.rag_enabled
    if data.rag_similarity_threshold is not None:
        config.rag_similarity_threshold = data.rag_similarity_threshold
    if data.rag_max_results is not None:
        config.rag_max_results = data.rag_max_results

    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return {
        "rag_enabled": config.rag_enabled,
        "rag_similarity_threshold": config.rag_similarity_threshold,
        "rag_max_results": config.rag_max_results,
    }


@router.put("/{org_id}/config/domains", response_model=dict)
async def update_domains_config(
    data: DomainsConfigUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update enabled domains configuration.

    Requires admin or owner role.
    """
    config = await get_or_create_config(db, org_id)

    config.enabled_domains = data.enabled_domains

    # Update default domain if provided, otherwise ensure it's valid
    if data.default_domain:
        if data.default_domain not in data.enabled_domains:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"default_domain '{data.default_domain}' must be in enabled_domains",
            )
        config.default_domain = data.default_domain
    elif config.default_domain not in data.enabled_domains:
        # Current default is no longer valid, use first enabled
        config.default_domain = data.enabled_domains[0]

    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return {
        "enabled_domains": config.enabled_domains,
        "default_domain": config.default_domain,
    }


@router.put("/{org_id}/config/agents", response_model=dict)
async def update_agents_config(
    data: AgentsConfigUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update enabled agents configuration.

    Requires admin or owner role.
    Empty list means all builtin agents are enabled.
    """
    config = await get_or_create_config(db, org_id)

    config.enabled_agent_types = data.enabled_agent_types
    config.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(config)

    return {
        "enabled_agent_types": config.enabled_agent_types,
    }
