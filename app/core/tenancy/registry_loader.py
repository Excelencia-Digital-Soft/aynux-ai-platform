"""
Tenant Registry Loader.

Unified loading of TenantAgentRegistry from database.
DRY consolidation of registry loading logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy.context import get_tenant_context

if TYPE_CHECKING:
    from app.core.schemas.tenant_agent_config import TenantAgentRegistry

logger = logging.getLogger(__name__)


class TenantRegistryLoader:
    """
    Unified loader for tenant agent registries.

    Consolidates logic for loading registries from:
    - Current tenant context (middleware-set)
    - Specific organization ID (bypass routing)

    This class eliminates duplication between context-based and
    org-based registry loading.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize loader.

        Args:
            db: Async database session
        """
        self._db = db
        self._agent_service = None  # Lazy initialization

    @property
    def agent_service(self):
        """
        Lazy load TenantAgentService to avoid circular imports.

        Returns:
            TenantAgentService instance
        """
        if self._agent_service is None:
            from app.core.tenancy.agent_service import TenantAgentService

            self._agent_service = TenantAgentService(db=self._db)
        return self._agent_service

    async def load_from_context(self) -> "TenantAgentRegistry | None":
        """
        Load tenant registry from current context.

        Uses TenantContext set by middleware. If no context is
        available (global mode), returns None.

        Returns:
            TenantAgentRegistry or None if no context
        """
        ctx = get_tenant_context()
        if not ctx or not ctx.organization_id:
            logger.debug("No tenant context available, using global mode")
            return None

        return await self.load_for_organization(ctx.organization_id)

    async def load_for_organization(
        self,
        organization_id: UUID,
    ) -> "TenantAgentRegistry | None":
        """
        Load tenant registry for a specific organization.

        This is the core loading method used by both context-based
        and direct organization-based loading.

        Args:
            organization_id: UUID of the organization

        Returns:
            TenantAgentRegistry or None if loading fails
        """
        try:
            registry = await self.agent_service.get_agent_registry(organization_id)
            logger.info(f"Loaded tenant registry for org {organization_id}")
            return registry

        except ImportError as e:
            logger.warning(f"TenantAgentService not available: {e}")
            return None
        except Exception as e:
            logger.warning(
                f"Error loading tenant registry for org {organization_id}: {e}"
            )
            return None


def get_registry_loader(db: AsyncSession) -> TenantRegistryLoader:
    """
    Factory function for dependency injection.

    Args:
        db: Async database session

    Returns:
        TenantRegistryLoader instance
    """
    return TenantRegistryLoader(db)
