# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Centralized configuration loader for routing.
#              Loads and provides routing and awaiting type configurations.
# Tenant-Aware: Yes - loads configs per organization_id.
# Domain-Aware: Yes - supports pharmacy, healthcare, ecommerce via domain_key.
# ============================================================================
"""
Routing Configuration Loader - Centralized config loading and access.

Loads configurations from cache and provides typed access to routing rules,
awaiting types, escape intents, and intent-node mappings.

Usage:
    loader = RoutingConfigLoader(db)
    await loader.load(org_id, "pharmacy")

    configs = loader.routing_configs
    awaiting = loader.awaiting_configs
    escape_intents = loader.escape_intents
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.cache.awaiting_type_cache import AwaitingTypeConfigDTO, awaiting_type_cache
from app.core.cache.routing_config_cache import RoutingConfigDTO, routing_config_cache

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RoutingConfigLoader:
    """
    Centralized loader for routing configurations.

    Single Responsibility: Load and provide access to routing configs.

    Loads:
    - Routing configs (global_keyword, button_mapping, menu_option, etc.)
    - Awaiting type configs (dni, amount, payment_confirmation, etc.)
    - Escape intents (from database, replaces hardcoded ESCAPE_INTENTS)
    - Intent-to-node mappings (for default node lookup)
    """

    def __init__(self, db: "AsyncSession") -> None:
        """
        Initialize loader with database session.

        Args:
            db: AsyncSession for database operations (used by cache)
        """
        self._db = db
        self._routing_configs: dict[str, list[RoutingConfigDTO]] | None = None
        self._awaiting_configs: dict[str, AwaitingTypeConfigDTO] | None = None
        self._escape_intents: frozenset[str] | None = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if configurations have been loaded."""
        return self._loaded

    @property
    def routing_configs(self) -> dict[str, list[RoutingConfigDTO]]:
        """
        Get loaded routing configs grouped by type.

        Returns:
            Dict mapping config_type to list of RoutingConfigDTO
        """
        if self._routing_configs is None:
            return {}
        return self._routing_configs

    @property
    def awaiting_configs(self) -> dict[str, AwaitingTypeConfigDTO]:
        """
        Get loaded awaiting type configs keyed by awaiting_type.

        Returns:
            Dict mapping awaiting_type to AwaitingTypeConfigDTO
        """
        if self._awaiting_configs is None:
            return {}
        return self._awaiting_configs

    @property
    def escape_intents(self) -> frozenset[str]:
        """
        Get escape intents loaded from database.

        Escape intents can interrupt awaited input (cancel, menu, salir, etc.).
        Replaces the hardcoded ESCAPE_INTENTS constant.

        Returns:
            Frozenset of intent keys that can escape awaited input
        """
        if self._escape_intents is None:
            return frozenset()
        return self._escape_intents

    async def load(
        self,
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
    ) -> None:
        """
        Load all configurations from cache.

        Args:
            organization_id: Tenant UUID (None for system defaults)
            domain_key: Domain scope (default: pharmacy)
        """
        if self._loaded:
            return

        # Load routing configs
        self._routing_configs = await routing_config_cache.get_configs(
            self._db, organization_id, domain_key
        )
        config_count = sum(len(v) for v in self._routing_configs.values())
        logger.debug(f"Loaded routing configs for org {organization_id}: {config_count} total")

        # Load awaiting type configs
        self._awaiting_configs = await awaiting_type_cache.get_configs(
            self._db, organization_id, domain_key
        )
        awaiting_count = len(self._awaiting_configs)
        logger.debug(f"Loaded awaiting type configs for org {organization_id}: {awaiting_count}")

        # Build escape intents from routing configs
        self._escape_intents = self._build_escape_intents()
        logger.debug(f"Built escape intents: {len(self._escape_intents)} intents")

        self._loaded = True

    def _build_escape_intents(self) -> frozenset[str]:
        """
        Build escape intents set from database configs.

        Escape intents are identified by:
        1. metadata.is_escape_intent = true on global_keyword configs
        2. config_type = "escape_intent"

        Returns:
            Frozenset of escape intent keys
        """
        escape_set: set[str] = set()

        if not self._routing_configs:
            return frozenset(escape_set)

        # Check global_keyword configs for is_escape_intent metadata
        for config in self._routing_configs.get("global_keyword", []):
            if config.metadata and config.metadata.get("is_escape_intent"):
                escape_set.add(config.target_intent)

        # Also check for explicit escape_intent config type
        for config in self._routing_configs.get("escape_intent", []):
            escape_set.add(config.target_intent)

        return frozenset(escape_set)

    def get_default_node(self, intent: str) -> str:
        """
        Get default node for intent from intent_node_mapping config.

        Args:
            intent: Intent to look up

        Returns:
            Node name to route to (defaults to "main_menu_node")
        """
        if self._routing_configs:
            for config in self._routing_configs.get("intent_node_mapping", []):
                if config.trigger_value == intent:
                    return config.target_node or "main_menu_node"
        return "main_menu_node"

    def intent_requires_auth(self, intent: str) -> bool:
        """
        Check if intent requires authentication.

        Args:
            intent: Intent to check

        Returns:
            True if intent requires authentication
        """
        if self._routing_configs:
            for config in self._routing_configs.get("intent_node_mapping", []):
                if config.trigger_value == intent:
                    return config.requires_auth
        return False

    def get_awaiting_config(self, awaiting_type: str) -> AwaitingTypeConfigDTO | None:
        """
        Get awaiting type configuration.

        Args:
            awaiting_type: The awaiting input type

        Returns:
            AwaitingTypeConfigDTO or None
        """
        if self._awaiting_configs:
            return self._awaiting_configs.get(awaiting_type)
        return None

    def get_configs_by_type(self, config_type: str) -> list[RoutingConfigDTO]:
        """
        Get routing configs of a specific type.

        Args:
            config_type: Configuration type (global_keyword, button_mapping, etc.)

        Returns:
            List of RoutingConfigDTO for the type
        """
        if self._routing_configs:
            return self._routing_configs.get(config_type, [])
        return []

    def get_state_updates(self) -> dict[str, Any]:
        """
        Get any state updates from loading (for debugging).

        Returns:
            Dict with load stats
        """
        return {
            "routing_config_count": sum(len(v) for v in self.routing_configs.values()),
            "awaiting_config_count": len(self.awaiting_configs),
            "escape_intent_count": len(self.escape_intents),
        }


__all__ = ["RoutingConfigLoader"]
