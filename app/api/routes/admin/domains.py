# ============================================================================
# SCOPE: GLOBAL
# Description: Admin API para gestionar dominios de negocio disponibles.
#              Los dominios son compartidos entre agent catalog y bypass rules.
# Tenant-Aware: No - dominios son configuración global del sistema.
# ============================================================================
"""
Domains Admin API - Manage available business domains.

Provides endpoints for:
- Listing all domains with optional filtering
- Creating and updating domains
- Toggling domain enabled status
- Deleting domains

Domains are shared between:
- Agent Catalog (domain_key field)
- Bypass Rules (target_domain field)
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas.domain import (
    DomainCreate,
    DomainListResponse,
    DomainResponse,
    DomainUpdate,
)
from app.database.async_db import get_async_db
from app.models.db.domain import Domain

router = APIRouter(tags=["Domains"])


# ============================================================
# LIST DOMAINS
# ============================================================


@router.get("", response_model=DomainListResponse)
async def list_domains(
    enabled_only: bool = Query(
        False,
        description="If true, only return enabled domains",
    ),
    db: AsyncSession = Depends(get_async_db),
) -> DomainListResponse:
    """
    List all domains, optionally filtered by enabled status.

    Args:
        enabled_only: If true, only return enabled domains
        db: Database session

    Returns:
        List of domains with total count
    """
    query = select(Domain).order_by(Domain.sort_order, Domain.display_name)

    if enabled_only:
        query = query.where(Domain.enabled == True)  # noqa: E712

    result = await db.execute(query)
    domains = result.scalars().all()

    return DomainListResponse(
        domains=[DomainResponse.model_validate(d) for d in domains],
        total=len(domains),
    )


# ============================================================
# GET SINGLE DOMAIN
# ============================================================


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> DomainResponse:
    """
    Get a domain by ID.

    Args:
        domain_id: Domain UUID
        db: Database session

    Returns:
        Domain details

    Raises:
        404: Domain not found
    """
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain with ID {domain_id} not found",
        )

    return DomainResponse.model_validate(domain)


# ============================================================
# CREATE DOMAIN
# ============================================================


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    data: DomainCreate,
    db: AsyncSession = Depends(get_async_db),
) -> DomainResponse:
    """
    Create a new domain.

    Args:
        data: Domain creation data
        db: Database session

    Returns:
        Created domain

    Raises:
        400: Domain key already exists
    """
    # Check if domain_key already exists
    existing = await db.execute(
        select(Domain).where(Domain.domain_key == data.domain_key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domain with key '{data.domain_key}' already exists",
        )

    domain = Domain(**data.model_dump())
    db.add(domain)
    await db.commit()
    await db.refresh(domain)

    return DomainResponse.model_validate(domain)


# ============================================================
# UPDATE DOMAIN
# ============================================================


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: UUID,
    data: DomainUpdate,
    db: AsyncSession = Depends(get_async_db),
) -> DomainResponse:
    """
    Update a domain.

    Args:
        domain_id: Domain UUID
        data: Domain update data
        db: Database session

    Returns:
        Updated domain

    Raises:
        404: Domain not found
    """
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain with ID {domain_id} not found",
        )

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(domain, key, value)

    await db.commit()
    await db.refresh(domain)

    return DomainResponse.model_validate(domain)


# ============================================================
# TOGGLE DOMAIN
# ============================================================


@router.post("/{domain_id}/toggle", response_model=DomainResponse)
async def toggle_domain(
    domain_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> DomainResponse:
    """
    Toggle a domain's enabled status.

    Args:
        domain_id: Domain UUID
        db: Database session

    Returns:
        Updated domain with toggled status

    Raises:
        404: Domain not found
    """
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain with ID {domain_id} not found",
        )

    domain.enabled = not domain.enabled
    await db.commit()
    await db.refresh(domain)

    return DomainResponse.model_validate(domain)


# ============================================================
# DELETE DOMAIN
# ============================================================


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: UUID,
    db: AsyncSession = Depends(get_async_db),
) -> None:
    """
    Delete a domain.

    Warning: This may break agents and bypass rules that reference this domain.
    Consider disabling instead of deleting.

    Args:
        domain_id: Domain UUID
        db: Database session

    Raises:
        404: Domain not found
    """
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain with ID {domain_id} not found",
        )

    await db.delete(domain)
    await db.commit()
