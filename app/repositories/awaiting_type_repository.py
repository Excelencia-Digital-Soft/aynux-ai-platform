# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Repository for awaiting type configuration CRUD operations.
# Tenant-Aware: Yes - queries filter by organization_id.
# Domain-Aware: Yes - queries filter by domain_key.
# ============================================================================
"""
AwaitingTypeRepository - Database access for awaiting type configurations.

Provides CRUD operations for awaiting_type_configs table with multi-tenant
and multi-domain support. Uses Repository pattern for clean separation
of database access from business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.awaiting_type_config import AwaitingTypeConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class AwaitingTypeRepository:
    """
    Repository for awaiting type configuration database operations.

    Follows the Repository pattern to encapsulate database access.
    All methods are tenant-aware and domain-aware.

    Usage:
        repo = AwaitingTypeRepository(db_session)
        configs = await repo.get_all(org_id, "pharmacy")
        config = await repo.get_by_awaiting_type(org_id, "pharmacy", "payment_confirmation")
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize repository with database session.

        Args:
            db: AsyncSession for database operations
        """
        self._db = db

    async def get_all(
        self,
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
        enabled_only: bool = True,
    ) -> Sequence[AwaitingTypeConfig]:
        """
        Get all awaiting type configurations for an organization and domain.

        Includes both org-specific and system-wide (NULL org) configs,
        with org-specific taking precedence.

        Args:
            organization_id: Organization UUID (NULL returns system defaults only)
            domain_key: Domain to filter by (default: pharmacy)
            enabled_only: If True, only return enabled configs

        Returns:
            List of AwaitingTypeConfig objects ordered by priority (descending)
        """
        conditions = [AwaitingTypeConfig.domain_key == domain_key]

        if enabled_only:
            conditions.append(AwaitingTypeConfig.is_enabled.is_(True))

        # Include both org-specific and system-wide configs
        if organization_id:
            conditions.append(
                or_(
                    AwaitingTypeConfig.organization_id == organization_id,
                    AwaitingTypeConfig.organization_id.is_(None),
                )
            )
        else:
            # Only system-wide configs
            conditions.append(AwaitingTypeConfig.organization_id.is_(None))

        stmt = select(AwaitingTypeConfig).where(and_(*conditions)).order_by(AwaitingTypeConfig.priority.desc())

        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_by_awaiting_type(
        self,
        organization_id: UUID | None,
        domain_key: str,
        awaiting_type: str,
    ) -> AwaitingTypeConfig | None:
        """
        Get a specific awaiting type configuration.

        Returns org-specific config if exists, otherwise system default.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            awaiting_type: Awaiting type to find

        Returns:
            AwaitingTypeConfig if found, None otherwise
        """
        # First try org-specific
        if organization_id:
            stmt = select(AwaitingTypeConfig).where(
                and_(
                    AwaitingTypeConfig.organization_id == organization_id,
                    AwaitingTypeConfig.domain_key == domain_key,
                    AwaitingTypeConfig.awaiting_type == awaiting_type,
                    AwaitingTypeConfig.is_enabled.is_(True),
                )
            )
            result = await self._db.execute(stmt)
            config = result.scalar_one_or_none()
            if config:
                return config

        # Fall back to system default
        stmt = select(AwaitingTypeConfig).where(
            and_(
                AwaitingTypeConfig.organization_id.is_(None),
                AwaitingTypeConfig.domain_key == domain_key,
                AwaitingTypeConfig.awaiting_type == awaiting_type,
                AwaitingTypeConfig.is_enabled.is_(True),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: UUID) -> AwaitingTypeConfig | None:
        """
        Get an awaiting type configuration by ID.

        Args:
            config_id: Configuration UUID

        Returns:
            AwaitingTypeConfig if found, None otherwise
        """
        stmt = select(AwaitingTypeConfig).where(AwaitingTypeConfig.id == config_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, config: AwaitingTypeConfig) -> AwaitingTypeConfig:
        """
        Create a new awaiting type configuration.

        Args:
            config: AwaitingTypeConfig instance to create

        Returns:
            Created AwaitingTypeConfig with ID
        """
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)
        logger.info(f"Created awaiting type config: {config.awaiting_type}:{config.target_node}")
        return config

    async def update(self, config: AwaitingTypeConfig) -> AwaitingTypeConfig:
        """
        Update an existing awaiting type configuration.

        Args:
            config: AwaitingTypeConfig instance with updates

        Returns:
            Updated AwaitingTypeConfig
        """
        await self._db.merge(config)
        await self._db.flush()
        logger.info(f"Updated awaiting type config: {config.awaiting_type}:{config.target_node}")
        return config

    async def delete(self, config_id: UUID) -> bool:
        """
        Delete an awaiting type configuration.

        Args:
            config_id: Configuration UUID to delete

        Returns:
            True if deleted, False if not found
        """
        config = await self.get_by_id(config_id)
        if config:
            await self._db.delete(config)
            await self._db.flush()
            logger.info(f"Deleted awaiting type config: {config_id}")
            return True
        return False

    async def bulk_create(self, configs: list[AwaitingTypeConfig]) -> list[AwaitingTypeConfig]:
        """
        Create multiple awaiting type configurations.

        Args:
            configs: List of AwaitingTypeConfig instances to create

        Returns:
            List of created AwaitingTypeConfig with IDs
        """
        self._db.add_all(configs)
        await self._db.flush()
        for config in configs:
            await self._db.refresh(config)
        logger.info(f"Bulk created {len(configs)} awaiting type configs")
        return configs

    async def get_keyed_by_type(
        self,
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
        enabled_only: bool = True,
    ) -> dict[str, AwaitingTypeConfig]:
        """
        Get all configurations keyed by awaiting_type.

        This is the primary method used by AwaitingTypeCache.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            enabled_only: If True, only return enabled configs

        Returns:
            Dict mapping awaiting_type to AwaitingTypeConfig:
            {
                "dni": AwaitingTypeConfig(target_node="auth_plex", ...),
                "amount": AwaitingTypeConfig(target_node="payment_processor", ...),
            }
        """
        configs = await self.get_all(organization_id, domain_key, enabled_only)

        keyed: dict[str, AwaitingTypeConfig] = {}
        for config in configs:
            awaiting_type = config.awaiting_type
            # Only keep the first (highest priority) config for each type
            if awaiting_type not in keyed:
                keyed[awaiting_type] = config

        return keyed

    async def exists(
        self,
        organization_id: UUID | None,
        domain_key: str,
        awaiting_type: str,
    ) -> bool:
        """
        Check if an awaiting type configuration exists.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            awaiting_type: Awaiting type to check

        Returns:
            True if exists, False otherwise
        """
        config = await self.get_by_awaiting_type(organization_id, domain_key, awaiting_type)
        return config is not None

    async def get_all_awaiting_types(
        self,
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
    ) -> list[str]:
        """
        Get list of all awaiting types for an organization/domain.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by

        Returns:
            List of awaiting_type strings
        """
        configs = await self.get_all(organization_id, domain_key, enabled_only=True)
        return list({config.awaiting_type for config in configs})
