# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Repository para persistencia de response configs multi-dominio.
#              Proporciona operaciones CRUD y queries optimizadas.
# Tenant-Aware: Yes - cada organización tiene sus propias configuraciones.
# Domain-Aware: Yes - soporta pharmacy, healthcare, ecommerce, etc.
# ============================================================================
"""
Response Config Repository - Data persistence layer for multi-domain response configs.

Provides async CRUD operations for ResponseConfig:
- is_critical: Whether to use fixed template (never LLM)
- task_description: Task description for LLM system prompt
- fallback_template_key: Key in fallback_templates.yaml

Follows Single Responsibility Principle - only handles data persistence.

Usage:
    repository = ResponseConfigRepository(db)
    configs = await repository.get_all_configs(org_id, domain_key="pharmacy")
    config = await repository.create_config(org_id, data)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.response_configs import ResponseConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class ResponseConfigRepository:
    """
    Async repository for response config persistence.

    Single Responsibility: Data access layer for response_configs table.
    Multi-tenant: All operations require organization_id.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository with async database session.

        Args:
            db: SQLAlchemy async session
        """
        self._db = db

    # =========================================================================
    # Query Operations (for cache)
    # =========================================================================

    async def get_all_configs(
        self,
        organization_id: UUID,
        domain_key: str = "pharmacy",
        enabled_only: bool = True,
    ) -> Sequence[ResponseConfig]:
        """Get all response configs for an organization.

        Optimized for cache loading - returns all configs in a single query.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope (default: pharmacy)
            enabled_only: Only return enabled configs

        Returns:
            Sequence of ResponseConfig
        """
        stmt = (
            select(ResponseConfig)
            .where(ResponseConfig.organization_id == organization_id)
            .where(ResponseConfig.domain_key == domain_key)
        )

        if enabled_only:
            stmt = stmt.where(ResponseConfig.is_enabled.is_(True))

        stmt = stmt.order_by(
            ResponseConfig.priority.desc(),
            ResponseConfig.intent_key,
        )

        result = await self._db.execute(stmt)
        configs = result.scalars().all()

        logger.debug(
            f"Loaded {len(configs)} response configs for org {organization_id}"
        )
        return configs

    async def get_by_intent_key(
        self,
        organization_id: UUID,
        intent_key: str,
        domain_key: str = "pharmacy",
    ) -> ResponseConfig | None:
        """Get config for a specific intent.

        Args:
            organization_id: Tenant UUID
            intent_key: Intent identifier (e.g., "greeting")
            domain_key: Domain scope

        Returns:
            ResponseConfig or None if not found
        """
        stmt = (
            select(ResponseConfig)
            .where(ResponseConfig.organization_id == organization_id)
            .where(ResponseConfig.domain_key == domain_key)
            .where(ResponseConfig.intent_key == intent_key)
            .where(ResponseConfig.is_enabled.is_(True))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: UUID) -> ResponseConfig | None:
        """Get config by UUID.

        Args:
            config_id: Config UUID

        Returns:
            ResponseConfig or None if not found
        """
        stmt = select(ResponseConfig).where(
            ResponseConfig.id == config_id
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create(
        self,
        organization_id: UUID,
        data: dict[str, Any],
    ) -> ResponseConfig:
        """Create a new response config.

        Args:
            organization_id: Tenant UUID
            data: Config data

        Returns:
            Created ResponseConfig with generated ID
        """
        config = ResponseConfig(
            organization_id=organization_id,
            domain_key=data.get("domain_key", "pharmacy"),
            intent_key=data["intent_key"],
            is_critical=data.get("is_critical", False),
            task_description=data["task_description"],
            fallback_template_key=data["fallback_template_key"],
            display_name=data.get("display_name"),
            description=data.get("description"),
            priority=data.get("priority", 0),
            is_enabled=data.get("is_enabled", True),
        )
        self._db.add(config)
        await self._db.flush()
        await self._db.refresh(config)

        logger.info(
            f"Created response config '{config.intent_key}' for org {organization_id}"
        )
        return config

    async def bulk_create(
        self,
        organization_id: UUID,
        configs_data: list[dict[str, Any]],
    ) -> list[ResponseConfig]:
        """Bulk create response configs.

        Args:
            organization_id: Tenant UUID
            configs_data: List of config data dicts

        Returns:
            List of created ResponseConfig
        """
        configs = []
        for data in configs_data:
            config = ResponseConfig(
                organization_id=organization_id,
                domain_key=data.get("domain_key", "pharmacy"),
                intent_key=data["intent_key"],
                is_critical=data.get("is_critical", False),
                task_description=data["task_description"],
                fallback_template_key=data["fallback_template_key"],
                display_name=data.get("display_name"),
                description=data.get("description"),
                priority=data.get("priority", 0),
                is_enabled=data.get("is_enabled", True),
            )
            self._db.add(config)
            configs.append(config)

        await self._db.flush()

        logger.info(
            f"Bulk created {len(configs)} response configs for org {organization_id}"
        )
        return configs

    async def update(
        self,
        config_id: UUID,
        data: dict[str, Any],
    ) -> ResponseConfig | None:
        """Update an existing response config.

        Args:
            config_id: Config UUID
            data: Fields to update

        Returns:
            Updated ResponseConfig or None if not found
        """
        config = await self.get_by_id(config_id)
        if not config:
            return None

        # Update allowed fields
        allowed_fields = [
            "is_critical",
            "task_description",
            "fallback_template_key",
            "display_name",
            "description",
            "priority",
            "is_enabled",
        ]
        for field in allowed_fields:
            if field in data:
                setattr(config, field, data[field])

        config.updated_at = datetime.now(UTC)
        await self._db.flush()
        await self._db.refresh(config)

        logger.info(f"Updated response config '{config.intent_key}'")
        return config

    async def delete(self, config_id: UUID) -> bool:
        """Delete a response config.

        Args:
            config_id: Config UUID

        Returns:
            True if deleted, False if not found
        """
        config = await self.get_by_id(config_id)
        if not config:
            return False

        intent_key = config.intent_key
        await self._db.delete(config)
        await self._db.flush()

        logger.info(f"Deleted response config '{intent_key}'")
        return True

    async def delete_all_for_org(
        self,
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> int:
        """Delete all response configs for an organization.

        Useful for re-seeding data.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Number of configs deleted
        """
        stmt = delete(ResponseConfig).where(
            ResponseConfig.organization_id == organization_id,
            ResponseConfig.domain_key == domain_key,
        )
        result = await self._db.execute(stmt)
        await self._db.flush()

        logger.info(
            f"Deleted {result.rowcount} response configs for org {organization_id}"
        )
        return result.rowcount

    # =========================================================================
    # Utility Operations
    # =========================================================================

    async def config_exists(
        self,
        organization_id: UUID,
        intent_key: str,
        domain_key: str = "pharmacy",
    ) -> bool:
        """Check if config exists for organization.

        Args:
            organization_id: Tenant UUID
            intent_key: Intent key
            domain_key: Domain scope

        Returns:
            True if exists
        """
        stmt = (
            select(func.count())
            .select_from(ResponseConfig)
            .where(ResponseConfig.organization_id == organization_id)
            .where(ResponseConfig.domain_key == domain_key)
            .where(ResponseConfig.intent_key == intent_key)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one() > 0

    async def count_configs(
        self,
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> int:
        """Count configs for an organization.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Number of configs
        """
        stmt = (
            select(func.count())
            .select_from(ResponseConfig)
            .where(ResponseConfig.organization_id == organization_id)
            .where(ResponseConfig.domain_key == domain_key)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def get_critical_intent_keys(
        self,
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> set[str]:
        """Get all intent keys marked as critical.

        Useful for checking if an intent should use fixed template.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Set of intent keys that are critical
        """
        stmt = (
            select(ResponseConfig.intent_key)
            .where(ResponseConfig.organization_id == organization_id)
            .where(ResponseConfig.domain_key == domain_key)
            .where(ResponseConfig.is_critical.is_(True))
            .where(ResponseConfig.is_enabled.is_(True))
        )
        result = await self._db.execute(stmt)
        return {row[0] for row in result.fetchall()}
