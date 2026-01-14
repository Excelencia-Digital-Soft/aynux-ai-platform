# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Multi-layer cache for routing configurations. L1 Memory (60s TTL)
#              + L2 Redis (5min TTL) per organization_id and domain_key.
# Tenant-Aware: Yes - each organization has isolated cache.
# Domain-Aware: Yes - supports pharmacy, healthcare, ecommerce via domain_key.
# ============================================================================
"""
Routing Config Cache - Multi-layer caching for database-driven routing configurations.

Features:
- L1: In-memory cache (60s TTL, per-instance, per-organization)
- L2: Redis cache (5min TTL, distributed, per-organization)
- Automatic invalidation on config changes
- Thread-safe with asyncio locks
- Grouped by config_type for efficient lookups

Usage:
    from app.core.cache.routing_config_cache import routing_config_cache

    # Get all configs grouped by type (auto-refreshes if expired)
    configs = await routing_config_cache.get_configs(db, org_id, "pharmacy")
    # Returns: {"global_keyword": [...], "button_mapping": [...], ...}

    # Invalidate on config changes
    await routing_config_cache.invalidate(org_id, "pharmacy")
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoutingConfigDTO:
    """
    Immutable routing configuration DTO for cache storage.

    Prevents accidental modification of cached values.
    """

    id: str
    config_type: str
    trigger_value: str
    target_intent: str
    target_node: str | None
    priority: int
    requires_auth: bool
    clears_context: bool
    metadata: dict[str, Any] | None
    display_name: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "config_type": self.config_type,
            "trigger_value": self.trigger_value,
            "target_intent": self.target_intent,
            "target_node": self.target_node,
            "priority": self.priority,
            "requires_auth": self.requires_auth,
            "clears_context": self.clears_context,
            "metadata": self.metadata,
            "display_name": self.display_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoutingConfigDTO":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            config_type=data["config_type"],
            trigger_value=data["trigger_value"],
            target_intent=data["target_intent"],
            target_node=data.get("target_node"),
            priority=data.get("priority", 0),
            requires_auth=data.get("requires_auth", False),
            clears_context=data.get("clears_context", False),
            metadata=data.get("metadata"),
            display_name=data.get("display_name"),
        )

    @classmethod
    def from_model(cls, model: Any) -> "RoutingConfigDTO":
        """Create from SQLAlchemy model."""
        return cls(
            id=str(model.id),
            config_type=str(model.config_type),
            trigger_value=str(model.trigger_value),
            target_intent=str(model.target_intent),
            target_node=str(model.target_node) if model.target_node else None,
            priority=int(model.priority) if model.priority else 0,
            requires_auth=bool(model.requires_auth),
            clears_context=bool(model.clears_context),
            metadata=model.metadata_,
            display_name=str(model.display_name) if model.display_name else None,
        )


# Type alias for the grouped configs structure
GroupedConfigs = dict[str, list[RoutingConfigDTO]]


class RoutingConfigCache:
    """
    Multi-layer cache for routing configurations.

    Thread-safe per-organization caching with TTL-based expiration.
    L1 (Memory) -> L2 (Redis) -> L3 (Database)

    Cache key format: "{org_id or 'system'}:{domain_key}"
    """

    REDIS_KEY_PREFIX = "routing:configs"
    MEMORY_TTL_SECONDS = 60  # 1 minute
    REDIS_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize cache with per-organization storage."""
        # Per-key memory cache: {cache_key: {"configs": GroupedConfigs, "timestamp": datetime}}
        self._memory_cache: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Stats for monitoring
        self._stats: dict[str, int] = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "db_loads": 0,
            "invalidations": 0,
        }

    def _get_cache_key(self, organization_id: UUID | None, domain_key: str) -> str:
        """Generate cache key from org_id and domain_key."""
        org_part = str(organization_id) if organization_id else "system"
        return f"{org_part}:{domain_key}"

    async def _get_lock(self, cache_key: str) -> asyncio.Lock:
        """Get or create lock for specific cache key."""
        async with self._global_lock:
            if cache_key not in self._locks:
                self._locks[cache_key] = asyncio.Lock()
            return self._locks[cache_key]

    async def get_configs(
        self,
        db: "AsyncSession | None",
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
    ) -> GroupedConfigs:
        """
        Get all routing configs grouped by config_type.

        Flow: L1 (Memory) -> L2 (Redis) -> L3 (Database)

        Args:
            db: AsyncSession for database access (optional - creates own if None)
            organization_id: Tenant UUID (None for system defaults only)
            domain_key: Domain scope (default: pharmacy)

        Returns:
            Dict mapping config_type to list of RoutingConfigDTO:
            {
                "global_keyword": [RoutingConfigDTO(trigger="menu", ...), ...],
                "button_mapping": [RoutingConfigDTO(trigger="btn_pay_full", ...), ...],
                "menu_option": [RoutingConfigDTO(trigger="1", ...), ...],
            }
        """
        cache_key = self._get_cache_key(organization_id, domain_key)
        lock = await self._get_lock(cache_key)

        async with lock:
            # L1: Check memory cache
            memory_data = self._get_from_memory(cache_key)
            if memory_data is not None:
                self._stats["memory_hits"] += 1
                return memory_data

            self._stats["memory_misses"] += 1

            # L2: Check Redis cache
            redis_data = await self._get_from_redis(cache_key)
            if redis_data is not None:
                self._stats["redis_hits"] += 1
                # Populate L1 from L2
                self._set_memory(cache_key, redis_data)
                return redis_data

            self._stats["redis_misses"] += 1

            # L3: Load from database
            if db is None:
                configs = await self._load_from_database_with_session(organization_id, domain_key)
            else:
                configs = await self._load_from_database(db, organization_id, domain_key)

            self._stats["db_loads"] += 1

            # Populate both caches
            await self._set_redis(cache_key, configs)
            self._set_memory(cache_key, configs)

            return configs

    async def get_by_type(
        self,
        db: "AsyncSession | None",
        organization_id: UUID | None,
        config_type: str,
        domain_key: str = "pharmacy",
    ) -> list[RoutingConfigDTO]:
        """
        Get routing configs of a specific type.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            config_type: Configuration type (global_keyword, button_mapping, etc.)
            domain_key: Domain scope (default: pharmacy)

        Returns:
            List of RoutingConfigDTO for the specified type
        """
        configs = await self.get_configs(db, organization_id, domain_key)
        return configs.get(config_type, [])

    async def find_matching_config(
        self,
        db: "AsyncSession | None",
        organization_id: UUID | None,
        message: str,
        domain_key: str = "pharmacy",
    ) -> RoutingConfigDTO | None:
        """
        Find a matching routing config for a message.

        Checks in priority order based on config_type:
        1. Global keywords (priority=100)
        2. Button mappings (priority=50)
        3. List selections (priority=45)
        4. Menu options (priority=40)

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            message: User message or button ID
            domain_key: Domain scope (default: pharmacy)

        Returns:
            Matching RoutingConfigDTO or None
        """
        configs = await self.get_configs(db, organization_id, domain_key)
        message_lower = message.strip().lower()

        # Check each type in priority order
        type_priority = [
            "global_keyword",
            "button_mapping",
            "list_selection",
            "menu_option",
        ]

        for config_type in type_priority:
            type_configs = configs.get(config_type, [])

            for config in type_configs:
                trigger = config.trigger_value.lower()

                # For global keywords, check if message starts with trigger
                if config_type == "global_keyword":
                    if message_lower == trigger or message_lower.startswith(trigger):
                        return config
                    # Check aliases
                    if config.metadata and "aliases" in config.metadata:
                        for alias in config.metadata["aliases"]:
                            if message_lower == alias.lower():
                                return config
                else:
                    # For others, exact match
                    if message_lower == trigger:
                        return config

        return None

    async def _load_from_database_with_session(
        self,
        organization_id: UUID | None,
        domain_key: str,
    ) -> GroupedConfigs:
        """Load configs creating own database session."""
        from app.database.async_db import get_async_db_context

        async with get_async_db_context() as db:
            return await self._load_from_database(db, organization_id, domain_key)

    async def _load_from_database(
        self,
        db: "AsyncSession",
        organization_id: UUID | None,
        domain_key: str,
    ) -> GroupedConfigs:
        """Load configs from database grouped by type."""
        from app.repositories.routing_config_repository import RoutingConfigRepository

        repo = RoutingConfigRepository(db)
        grouped_models = await repo.get_grouped_by_type(organization_id, domain_key, enabled_only=True)

        # Convert to DTOs
        grouped_dtos: GroupedConfigs = {}
        for config_type, models in grouped_models.items():
            grouped_dtos[config_type] = [RoutingConfigDTO.from_model(model) for model in models]

        logger.debug(
            f"Loaded routing configs from DB for org {organization_id}: "
            f"{sum(len(v) for v in grouped_dtos.values())} total configs"
        )

        return grouped_dtos

    def _get_from_memory(self, cache_key: str) -> GroupedConfigs | None:
        """Get configs from memory cache if not expired."""
        if cache_key not in self._memory_cache:
            return None

        cache_entry = self._memory_cache[cache_key]
        timestamp = cache_entry.get("timestamp")

        if timestamp is None:
            return None

        elapsed = (datetime.now(UTC) - timestamp).total_seconds()
        if elapsed >= self.MEMORY_TTL_SECONDS:
            # Expired
            del self._memory_cache[cache_key]
            return None

        return cache_entry.get("configs")

    def _set_memory(self, cache_key: str, configs: GroupedConfigs) -> None:
        """Store configs in memory cache."""
        self._memory_cache[cache_key] = {
            "configs": configs,
            "timestamp": datetime.now(UTC),
        }

    async def _get_from_redis(self, cache_key: str) -> GroupedConfigs | None:
        """Get configs from Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return None

            key = f"{self.REDIS_KEY_PREFIX}:{cache_key}"
            data = redis.get(key)

            if data:
                parsed = json.loads(data)
                return {k: [RoutingConfigDTO.from_dict(d) for d in v] for k, v in parsed.items()}
        except Exception as e:
            logger.warning(f"Redis get failed for {cache_key}: {e}")

        return None

    async def _set_redis(self, cache_key: str, configs: GroupedConfigs) -> None:
        """Store configs in Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return

            key = f"{self.REDIS_KEY_PREFIX}:{cache_key}"
            serializable = {k: [d.to_dict() for d in v] for k, v in configs.items()}
            redis.setex(key, self.REDIS_TTL_SECONDS, json.dumps(serializable))

        except Exception as e:
            logger.warning(f"Redis set failed for {cache_key}: {e}")

    async def invalidate(
        self,
        organization_id: UUID | None = None,
        domain_key: str | None = None,
    ) -> int:
        """
        Invalidate cache for specific organization/domain or all.

        Args:
            organization_id: Specific org to invalidate (None for system/all)
            domain_key: Specific domain to invalidate (None for all domains)

        Returns:
            Number of cache entries invalidated
        """
        count = 0

        if organization_id is not None and domain_key is not None:
            # Specific invalidation
            cache_key = self._get_cache_key(organization_id, domain_key)
            lock = await self._get_lock(cache_key)

            async with lock:
                if cache_key in self._memory_cache:
                    del self._memory_cache[cache_key]
                    count += 1

                # Clear Redis
                try:
                    from app.integrations.databases.redis import get_redis_client

                    redis = get_redis_client()
                    if redis:
                        key = f"{self.REDIS_KEY_PREFIX}:{cache_key}"
                        redis.delete(key)
                except Exception as e:
                    logger.warning(f"Redis invalidation failed for {cache_key}: {e}")

        else:
            # Bulk invalidation
            async with self._global_lock:
                # Find matching cache keys
                keys_to_delete = []
                for key in self._memory_cache:
                    if domain_key is None or key.endswith(f":{domain_key}"):
                        if organization_id is None or key.startswith(f"{organization_id}:"):
                            keys_to_delete.append(key)

                for key in keys_to_delete:
                    del self._memory_cache[key]
                    count += 1

                # Clear Redis
                try:
                    from app.integrations.databases.redis import get_redis_client

                    redis = get_redis_client()
                    if redis:
                        pattern = f"{self.REDIS_KEY_PREFIX}:*"
                        keys = redis.keys(pattern)
                        if keys:
                            redis.delete(*keys)
                            count = max(count, len(keys))
                except Exception as e:
                    logger.warning(f"Redis bulk invalidation failed: {e}")

        self._stats["invalidations"] += count
        logger.info(
            f"Routing config cache invalidated: {count} entries " f"(org={organization_id}, domain={domain_key})"
        )

        return count

    async def warm(
        self,
        db: "AsyncSession",
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
    ) -> GroupedConfigs:
        """
        Warm cache for a specific organization/domain.

        Force-loads from database and populates both caches.

        Args:
            db: AsyncSession
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Loaded configs
        """
        cache_key = self._get_cache_key(organization_id, domain_key)
        lock = await self._get_lock(cache_key)

        async with lock:
            # Force load from database
            configs = await self._load_from_database(db, organization_id, domain_key)

            # Populate both caches
            await self._set_redis(cache_key, configs)
            self._set_memory(cache_key, configs)

            logger.info(f"Routing config cache warmed for org {organization_id}, " f"domain {domain_key}")
            return configs

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with hit rates and counts
        """
        total_memory = self._stats["memory_hits"] + self._stats["memory_misses"]
        total_redis = self._stats["redis_hits"] + self._stats["redis_misses"]

        return {
            "memory_hits": self._stats["memory_hits"],
            "memory_misses": self._stats["memory_misses"],
            "memory_hit_rate": (self._stats["memory_hits"] / total_memory if total_memory > 0 else 0),
            "redis_hits": self._stats["redis_hits"],
            "redis_misses": self._stats["redis_misses"],
            "redis_hit_rate": (self._stats["redis_hits"] / total_redis if total_redis > 0 else 0),
            "db_loads": self._stats["db_loads"],
            "invalidations": self._stats["invalidations"],
            "cached_keys": len(self._memory_cache),
        }

    def get_cached_keys(self) -> list[str]:
        """Get list of cache keys currently in memory cache.

        Returns:
            List of cache key strings
        """
        return list(self._memory_cache.keys())


# Singleton instance
routing_config_cache = RoutingConfigCache()
