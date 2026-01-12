# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Configuration provider for pharmacy response generation.
#              Retrieves intent configuration from database via cache.
# Tenant-Aware: Yes - configuration is per organization.
# ============================================================================
"""
Pharmacy Config Provider - Database configuration access.

Responsibilities:
- Retrieve response configuration from cache/database
- Provide is_critical, task_description, fallback_template_key
- Enforce no-defaults policy (raises error if config missing)

CRITICAL: NO HARDCODING of intent configurations.
All intent config MUST come from database.
Missing config raises ResponseConfigNotFoundError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.core.cache.response_config_cache import (
    ResponseConfigDTO,
    response_config_cache,
)
from app.domains.pharmacy.agents.utils.exceptions import (
    ResponseConfigNotFoundError,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PharmacyConfigProvider:
    """
    Provides response configuration from database/cache.

    Single Responsibility: Database configuration access.

    Multi-tenant: All operations require organization_id.
    NO DEFAULTS - config MUST exist in database.
    """

    async def get_config(
        self,
        db: AsyncSession | None,
        organization_id: UUID,
        intent: str,
    ) -> ResponseConfigDTO:
        """
        Get response configuration from cache/database.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            intent: Intent key

        Returns:
            ResponseConfigDTO with is_critical, task_description, etc.

        Raises:
            ResponseConfigNotFoundError: If config not found in database
        """
        config = await response_config_cache.get_config(
            db, organization_id, intent
        )

        if config is None:
            raise ResponseConfigNotFoundError(
                intent_key=intent,
                organization_id=organization_id,
            )

        return config

    async def is_critical(
        self,
        db: AsyncSession | None,
        organization_id: UUID,
        intent: str,
    ) -> bool:
        """
        Check if intent is critical (uses fixed template, never LLM).

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            intent: Intent key

        Returns:
            True if intent should use fixed template
        """
        config = await self.get_config(db, organization_id, intent)
        return config.is_critical

    async def get_task_description(
        self,
        db: AsyncSession | None,
        organization_id: UUID,
        intent: str,
    ) -> str:
        """
        Get task description for LLM system prompt.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            intent: Intent key

        Returns:
            Task description string
        """
        config = await self.get_config(db, organization_id, intent)
        return config.task_description

    async def get_fallback_key(
        self,
        db: AsyncSession | None,
        organization_id: UUID,
        intent: str,
    ) -> str:
        """
        Get fallback template key for intent.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            intent: Intent key

        Returns:
            Fallback template key
        """
        config = await self.get_config(db, organization_id, intent)
        return config.fallback_template_key


__all__ = ["PharmacyConfigProvider"]
