"""
Organization Resolution Service.

Resolves organization context for webhook operations.
Single Responsibility: Organization identification and credential lookup.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import (
    CredentialNotFoundError,
    get_tenant_credential_service,
)
from app.models.db.tenancy import Organization

logger = logging.getLogger(__name__)


class OrganizationResolutionError(Exception):
    """Raised when organization cannot be resolved."""

    pass


class OrganizationResolverService:
    """
    Service for resolving organizations in webhook context.

    Responsibilities:
    - Resolve org_id from query params, headers, or defaults
    - Lookup default organization (system)
    - Retrieve verify tokens from credentials
    """

    # Default organization slugs in priority order
    DEFAULT_ORG_SLUGS: list[str] = ["system"]

    def __init__(self, db: AsyncSession):
        """
        Initialize service.

        Args:
            db: Async database session
        """
        self._db = db
        self._credential_service = get_tenant_credential_service()

    async def resolve_organization(
        self,
        query_params: dict[str, str],
        headers: dict[str, str],
    ) -> UUID:
        """
        Resolve organization ID from request context.

        Priority:
        1. Query parameter: org_id
        2. Header: X-Organization-ID
        3. Default organization (system)

        Args:
            query_params: Query parameters from request
            headers: HTTP headers from request

        Returns:
            Organization UUID

        Raises:
            OrganizationResolutionError: If no organization can be resolved
        """
        # Try query parameter
        org_id_str = query_params.get("org_id")
        if org_id_str:
            return self._parse_uuid(org_id_str, "org_id")

        # Try header (case-insensitive)
        org_id_header = headers.get("x-organization-id")
        if org_id_header:
            return self._parse_uuid(org_id_header, "X-Organization-ID")

        # Fallback to default
        default_org = await self.get_default_organization()
        if default_org:
            return UUID(str(default_org.id))

        raise OrganizationResolutionError(
            "No organization found. Provide org_id query param or create default organization."
        )

    async def get_default_organization(self) -> Organization | None:
        """
        Get the default organization for global mode.

        Tries 'system' as the default fallback.

        Returns:
            Organization or None if not found
        """
        for slug in self.DEFAULT_ORG_SLUGS:
            result = await self._db.execute(
                select(Organization).where(Organization.slug == slug)
            )
            org = result.scalar_one_or_none()
            if org:
                return org
        return None

    async def get_verify_token(self, org_id: UUID) -> str:
        """
        Get expected verify token for an organization.

        Args:
            org_id: Organization UUID

        Returns:
            Verify token string

        Raises:
            CredentialNotFoundError: If credentials not found
            ValueError: If credentials incomplete
        """
        creds = await self._credential_service.get_whatsapp_credentials(
            self._db, org_id
        )
        return creds.verify_token

    def _parse_uuid(self, value: str, source: str) -> UUID:
        """
        Parse UUID from string, raising descriptive error.

        Args:
            value: String value to parse
            source: Source name for error message (e.g., "org_id", "X-Organization-ID")

        Returns:
            Parsed UUID

        Raises:
            OrganizationResolutionError: If value is not a valid UUID
        """
        try:
            return UUID(value)
        except ValueError as e:
            raise OrganizationResolutionError(
                f"Invalid {source} format: {value}"
            ) from e


def get_organization_resolver(db: AsyncSession) -> OrganizationResolverService:
    """
    Factory function for dependency injection.

    Args:
        db: Async database session

    Returns:
        OrganizationResolverService instance
    """
    return OrganizationResolverService(db)
