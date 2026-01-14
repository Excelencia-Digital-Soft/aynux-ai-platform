# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Repository for routing configuration CRUD operations.
# Tenant-Aware: Yes - queries filter by organization_id.
# Domain-Aware: Yes - queries filter by domain_key.
# ============================================================================
"""
RoutingConfigRepository - Database access for routing configurations.

Provides CRUD operations for routing_configs table with multi-tenant
and multi-domain support. Uses Repository pattern for clean separation
of database access from business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import RoutingConfig, RoutingConfigType

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class RoutingConfigRepository:
    """
    Repository for routing configuration database operations.

    Follows the Repository pattern to encapsulate database access.
    All methods are tenant-aware and domain-aware.

    Usage:
        repo = RoutingConfigRepository(db_session)
        configs = await repo.get_all(org_id, "pharmacy")
        config = await repo.get_by_trigger(org_id, "pharmacy", "global_keyword", "menu")
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
    ) -> Sequence[RoutingConfig]:
        """
        Get all routing configurations for an organization and domain.

        Includes both org-specific and system-wide (NULL org) configs,
        with org-specific taking precedence.

        Args:
            organization_id: Organization UUID (NULL returns system defaults only)
            domain_key: Domain to filter by (default: pharmacy)
            enabled_only: If True, only return enabled configs

        Returns:
            List of RoutingConfig objects ordered by priority (descending)
        """
        conditions = [RoutingConfig.domain_key == domain_key]

        if enabled_only:
            conditions.append(RoutingConfig.is_enabled.is_(True))

        # Include both org-specific and system-wide configs
        if organization_id:
            conditions.append(
                or_(
                    RoutingConfig.organization_id == organization_id,
                    RoutingConfig.organization_id.is_(None),
                )
            )
        else:
            # Only system-wide configs
            conditions.append(RoutingConfig.organization_id.is_(None))

        stmt = select(RoutingConfig).where(and_(*conditions)).order_by(RoutingConfig.priority.desc())

        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_by_type(
        self,
        organization_id: UUID | None,
        domain_key: str,
        config_type: str,
        enabled_only: bool = True,
    ) -> Sequence[RoutingConfig]:
        """
        Get routing configurations of a specific type.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            config_type: Configuration type (global_keyword, button_mapping, etc.)
            enabled_only: If True, only return enabled configs

        Returns:
            List of RoutingConfig objects for the specified type
        """
        conditions = [
            RoutingConfig.domain_key == domain_key,
            RoutingConfig.config_type == config_type,
        ]

        if enabled_only:
            conditions.append(RoutingConfig.is_enabled.is_(True))

        if organization_id:
            conditions.append(
                or_(
                    RoutingConfig.organization_id == organization_id,
                    RoutingConfig.organization_id.is_(None),
                )
            )
        else:
            conditions.append(RoutingConfig.organization_id.is_(None))

        stmt = select(RoutingConfig).where(and_(*conditions)).order_by(RoutingConfig.priority.desc())

        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def get_by_trigger(
        self,
        organization_id: UUID | None,
        domain_key: str,
        config_type: str,
        trigger_value: str,
    ) -> RoutingConfig | None:
        """
        Get a specific routing configuration by trigger value.

        Returns org-specific config if exists, otherwise system default.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            config_type: Configuration type
            trigger_value: Trigger value to find

        Returns:
            RoutingConfig if found, None otherwise
        """
        # First try org-specific
        if organization_id:
            stmt = select(RoutingConfig).where(
                and_(
                    RoutingConfig.organization_id == organization_id,
                    RoutingConfig.domain_key == domain_key,
                    RoutingConfig.config_type == config_type,
                    RoutingConfig.trigger_value == trigger_value,
                    RoutingConfig.is_enabled.is_(True),
                )
            )
            result = await self._db.execute(stmt)
            config = result.scalar_one_or_none()
            if config:
                return config

        # Fall back to system default
        stmt = select(RoutingConfig).where(
            and_(
                RoutingConfig.organization_id.is_(None),
                RoutingConfig.domain_key == domain_key,
                RoutingConfig.config_type == config_type,
                RoutingConfig.trigger_value == trigger_value,
                RoutingConfig.is_enabled.is_(True),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: UUID) -> RoutingConfig | None:
        """
        Get a routing configuration by ID.

        Args:
            config_id: Configuration UUID

        Returns:
            RoutingConfig if found, None otherwise
        """
        stmt = select(RoutingConfig).where(RoutingConfig.id == config_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, config: RoutingConfig) -> RoutingConfig:
        """
        Create a new routing configuration.

        Args:
            config: RoutingConfig instance to create

        Returns:
            Created RoutingConfig with ID
        """
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)
        logger.info(f"Created routing config: {config.config_type}:{config.trigger_value}")
        return config

    async def update(self, config: RoutingConfig) -> RoutingConfig:
        """
        Update an existing routing configuration.

        Args:
            config: RoutingConfig instance with updates

        Returns:
            Updated RoutingConfig
        """
        await self._db.merge(config)
        await self._db.flush()
        logger.info(f"Updated routing config: {config.config_type}:{config.trigger_value}")
        return config

    async def delete(self, config_id: UUID) -> bool:
        """
        Delete a routing configuration.

        Args:
            config_id: Configuration UUID to delete

        Returns:
            True if deleted, False if not found
        """
        config = await self.get_by_id(config_id)
        if config:
            await self._db.delete(config)
            await self._db.flush()
            logger.info(f"Deleted routing config: {config_id}")
            return True
        return False

    async def bulk_create(self, configs: list[RoutingConfig]) -> list[RoutingConfig]:
        """
        Create multiple routing configurations.

        Args:
            configs: List of RoutingConfig instances to create

        Returns:
            List of created RoutingConfig with IDs
        """
        self._db.add_all(configs)
        await self._db.flush()
        for config in configs:
            await self._db.refresh(config)
        logger.info(f"Bulk created {len(configs)} routing configs")
        return configs

    async def get_grouped_by_type(
        self,
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
        enabled_only: bool = True,
    ) -> dict[str, list[RoutingConfig]]:
        """
        Get all configurations grouped by config_type.

        This is the primary method used by RouterSupervisor cache.

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            enabled_only: If True, only return enabled configs

        Returns:
            Dict mapping config_type to list of RoutingConfig:
            {
                "global_keyword": [RoutingConfig(trigger="menu", ...), ...],
                "button_mapping": [RoutingConfig(trigger="btn_pay_full", ...), ...],
                "menu_option": [RoutingConfig(trigger="1", ...), ...],
            }
        """
        configs = await self.get_all(organization_id, domain_key, enabled_only)

        grouped: dict[str, list[RoutingConfig]] = {}
        for config in configs:
            config_type = config.config_type
            if config_type not in grouped:
                grouped[config_type] = []
            grouped[config_type].append(config)

        return grouped

    async def find_matching_trigger(
        self,
        organization_id: UUID | None,
        domain_key: str,
        message: str,
    ) -> RoutingConfig | None:
        """
        Find a matching routing config for a message.

        Checks in priority order:
        1. Global keywords (exact match on message)
        2. Button mappings (exact match on button ID)
        3. Menu options (exact match on number)

        Args:
            organization_id: Organization UUID
            domain_key: Domain to filter by
            message: User message or button ID

        Returns:
            Matching RoutingConfig or None
        """
        message_lower = message.strip().lower()

        # Check each type in priority order
        for config_type in [
            RoutingConfigType.GLOBAL_KEYWORD,
            RoutingConfigType.BUTTON_MAPPING,
            RoutingConfigType.LIST_SELECTION,
            RoutingConfigType.MENU_OPTION,
        ]:
            configs = await self.get_by_type(organization_id, domain_key, config_type)

            for config in configs:
                trigger = config.trigger_value.lower()

                # For global keywords, check if message starts with trigger
                if config_type == RoutingConfigType.GLOBAL_KEYWORD:
                    if message_lower == trigger or message_lower.startswith(trigger):
                        return config

                # For others, exact match
                elif message_lower == trigger:
                    return config

                # Check aliases in metadata
                metadata = config.metadata_
                if metadata and "aliases" in metadata:
                    for alias in metadata["aliases"]:
                        if message_lower == alias.lower():
                            return config

        return None
