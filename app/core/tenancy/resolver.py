# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Resuelve el tenant desde JWT, WhatsApp ID, header, o slug.
#              Valida membresía de usuario y estado de organización.
# Tenant-Aware: Yes - responsable de identificar el tenant en cada request.
# ============================================================================
"""
TenantResolver - Resolves tenant context from various sources.

Supports multiple resolution strategies:
1. JWT Token: Extract organization_id from JWT claims
2. WhatsApp ID: Lookup organization by contact-domain mapping
3. API Key: Lookup organization by API key (future)
4. Default: Fall back to system organization (generic mode)

Usage:
    resolver = TenantResolver(db_session)
    context = await resolver.resolve_from_jwt(token)
    # or
    context = await resolver.resolve_from_whatsapp(wa_id)
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.db.tenancy import Organization, OrganizationUser, TenantConfig

from .context import TenantContext

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TenantResolutionError(Exception):
    """Raised when tenant resolution fails."""

    pass


class TenantResolver:
    """
    Resolves tenant context from various sources.

    Provides multiple resolution strategies for determining which
    organization/tenant a request belongs to.

    Example:
        >>> resolver = TenantResolver(db_session)
        >>> context = await resolver.resolve_from_jwt(token_payload)
        >>> set_tenant_context(context)
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize resolver with database session.

        Args:
            db: Async SQLAlchemy session for database operations.
        """
        self.db = db

    async def resolve_from_jwt(
        self,
        token_payload: dict,
        *,
        require_org: bool = True,
    ) -> TenantContext:
        """
        Resolve tenant context from JWT token payload.

        Expected JWT claims:
        - org_id or organization_id: UUID of the organization
        - sub or user_id: UUID of the user

        Args:
            token_payload: Decoded JWT payload dictionary.
            require_org: If True, raise error when org not found.

        Returns:
            TenantContext with organization and user information.

        Raises:
            TenantResolutionError: If resolution fails and require_org is True.

        Example:
            >>> payload = {"org_id": "...", "sub": "..."}
            >>> context = await resolver.resolve_from_jwt(payload)
        """
        # Extract organization ID from various possible claim names
        org_id_str = (
            token_payload.get("org_id")
            or token_payload.get("organization_id")
            or token_payload.get("tenant_id")
        )

        # Extract user ID from various possible claim names
        user_id_str = (
            token_payload.get("sub")
            or token_payload.get("user_id")
            or token_payload.get("uid")
        )

        if not org_id_str:
            if require_org:
                raise TenantResolutionError(
                    "No organization ID found in JWT token. "
                    "Expected 'org_id', 'organization_id', or 'tenant_id' claim."
                )
            return TenantContext.create_system_context()

        try:
            org_id = uuid.UUID(org_id_str)
        except ValueError as e:
            raise TenantResolutionError(f"Invalid organization ID format: {org_id_str}") from e

        user_id = None
        if user_id_str:
            try:
                user_id = uuid.UUID(user_id_str)
            except ValueError:
                logger.warning(f"Invalid user ID format in JWT: {user_id_str}")

        return await self._resolve_organization(org_id, user_id)

    async def resolve_from_whatsapp(
        self,
        wa_id: str,
        *,
        require_org: bool = False,
    ) -> TenantContext:
        """
        Resolve tenant context from WhatsApp ID.

        Looks up the contact_domains table to find the organization
        associated with this WhatsApp number.

        Args:
            wa_id: WhatsApp ID (phone number).
            require_org: If True, raise error when org not found.

        Returns:
            TenantContext for the organization, or system context if not found.

        Example:
            >>> context = await resolver.resolve_from_whatsapp("5491123456789")
        """
        from app.models.db.contact_domains import ContactDomain

        # Look up contact domain mapping
        stmt = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
        result = await self.db.execute(stmt)
        contact_domain = result.scalar_one_or_none()

        if not contact_domain:
            if require_org:
                raise TenantResolutionError(
                    f"No organization found for WhatsApp ID: {wa_id}"
                )
            logger.debug(f"No contact domain mapping for wa_id={wa_id}, using system context")
            return TenantContext.create_system_context()

        # Check if contact has organization_id (for multi-tenant)
        if hasattr(contact_domain, "organization_id") and contact_domain.organization_id:
            return await self._resolve_organization(contact_domain.organization_id, None)

        # Fall back to system context
        return TenantContext.create_system_context()

    async def resolve_from_organization_id(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> TenantContext:
        """
        Resolve tenant context directly from organization ID.

        Args:
            org_id: Organization UUID.
            user_id: Optional user UUID within the organization.

        Returns:
            TenantContext with full organization data.

        Example:
            >>> context = await resolver.resolve_from_organization_id(org_uuid)
        """
        return await self._resolve_organization(org_id, user_id)

    async def resolve_from_slug(
        self,
        slug: str,
        user_id: uuid.UUID | None = None,
    ) -> TenantContext:
        """
        Resolve tenant context from organization slug.

        Args:
            slug: URL-friendly organization identifier.
            user_id: Optional user UUID.

        Returns:
            TenantContext for the organization.

        Raises:
            TenantResolutionError: If organization not found.

        Example:
            >>> context = await resolver.resolve_from_slug("acme-corp")
        """
        stmt = (
            select(Organization)
            .where(Organization.slug == slug)
            .options(selectinload(Organization.config))
        )
        result = await self.db.execute(stmt)
        organization = result.scalar_one_or_none()

        if not organization:
            raise TenantResolutionError(f"Organization not found: {slug}")

        return self._build_context(organization, user_id)

    async def _resolve_organization(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> TenantContext:
        """
        Internal method to resolve organization and build context.

        Args:
            org_id: Organization UUID.
            user_id: Optional user UUID.

        Returns:
            TenantContext with full organization and config.

        Raises:
            TenantResolutionError: If organization not found.
        """
        # Check for system organization
        system_org_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        if org_id == system_org_id:
            return TenantContext.create_system_context()

        # Load organization with config
        stmt = (
            select(Organization)
            .where(Organization.id == org_id)
            .options(selectinload(Organization.config))
        )
        result = await self.db.execute(stmt)
        organization = result.scalar_one_or_none()

        if not organization:
            raise TenantResolutionError(f"Organization not found: {org_id}")

        # Validate organization status
        if organization.status == "suspended":
            raise TenantResolutionError(
                f"Organization {organization.slug} is suspended"
            )

        # Validate user membership if user_id provided
        if user_id:
            await self._validate_user_membership(org_id, user_id)

        return self._build_context(organization, user_id)

    async def _validate_user_membership(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> OrganizationUser:
        """
        Validate that user is a member of the organization.

        Args:
            org_id: Organization UUID.
            user_id: User UUID.

        Returns:
            OrganizationUser membership record.

        Raises:
            TenantResolutionError: If user is not a member.
        """
        stmt = select(OrganizationUser).where(
            OrganizationUser.organization_id == org_id,
            OrganizationUser.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            raise TenantResolutionError(
                f"User {user_id} is not a member of organization {org_id}"
            )

        return membership

    def _build_context(
        self,
        organization: Organization,
        user_id: uuid.UUID | None,
    ) -> TenantContext:
        """
        Build TenantContext from organization model.

        Args:
            organization: Organization model instance.
            user_id: Optional user UUID.

        Returns:
            Fully populated TenantContext.
        """
        # Get config if available (loaded via relationship)
        config = organization.config if hasattr(organization, "config") else None

        context = TenantContext(
            organization_id=organization.id,
            organization=organization,
            user_id=user_id,
            config=config,
            mode=organization.mode,
            is_system=False,
        )

        # Populate cached values from config if available
        if config:
            context = context.with_config(config)

        return context


async def get_or_create_system_organization(db: AsyncSession) -> Organization:
    """
    Get or create the system organization for generic mode.

    The system organization is used when running without multi-tenancy.
    It uses a fixed UUID and default configuration.

    Args:
        db: Async database session.

    Returns:
        System Organization instance.

    Example:
        >>> system_org = await get_or_create_system_organization(db)
    """
    system_org_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

    stmt = select(Organization).where(Organization.id == system_org_id)
    result = await db.execute(stmt)
    organization = result.scalar_one_or_none()

    if organization:
        return organization

    # Create system organization
    organization = Organization.create_system_org()
    db.add(organization)
    await db.commit()
    await db.refresh(organization)

    logger.info("Created system organization for generic mode")
    return organization
