# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Multi-layer cache for awaiting type configurations. L1 Memory (60s TTL)
#              + L2 Redis (5min TTL) per organization_id and domain_key.
# Tenant-Aware: Yes - each organization has isolated cache.
# Domain-Aware: Yes - supports pharmacy, healthcare, ecommerce via domain_key.
# ============================================================================
"""
Awaiting Type Config Cache - Multi-layer caching for database-driven awaiting type configurations.

Features:
- L1: In-memory cache (60s TTL, per-instance, per-organization)
- L2: Redis cache (5min TTL, distributed, per-organization)
- Automatic invalidation on config changes
- Thread-safe with asyncio locks
- Keyed by awaiting_type for efficient lookups

Usage:
    from app.core.cache.awaiting_type_cache import awaiting_type_cache

    # Get all configs keyed by awaiting_type (auto-refreshes if expired)
    configs = await awaiting_type_cache.get_configs(db, org_id, "pharmacy")
    # Returns: {"dni": AwaitingTypeConfigDTO(...), "amount": AwaitingTypeConfigDTO(...), ...}

    # Get specific config by awaiting_type
    config = await awaiting_type_cache.get_by_type(db, org_id, "payment_confirmation", "pharmacy")

    # Invalidate on config changes
    await awaiting_type_cache.invalidate(org_id, "pharmacy")
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
class AwaitingTypeConfigDTO:
    """
    Immutable awaiting type configuration DTO for cache storage.

    Prevents accidental modification of cached values.

    Attributes:
        metadata: Extensible configuration dict with:
            - intent_overrides: list[str] - intents that can override awaiting state
    """

    id: str
    awaiting_type: str
    target_node: str
    valid_response_intents: tuple[str, ...]  # Tuple for immutability
    validation_pattern: str | None
    priority: int
    display_name: str | None
    metadata: dict[str, Any] | None = None  # For intent_overrides, etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "awaiting_type": self.awaiting_type,
            "target_node": self.target_node,
            "valid_response_intents": list(self.valid_response_intents),
            "validation_pattern": self.validation_pattern,
            "priority": self.priority,
            "display_name": self.display_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AwaitingTypeConfigDTO":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            awaiting_type=data["awaiting_type"],
            target_node=data["target_node"],
            valid_response_intents=tuple(data.get("valid_response_intents") or []),
            validation_pattern=data.get("validation_pattern"),
            priority=data.get("priority", 0),
            display_name=data.get("display_name"),
            metadata=data.get("metadata"),
        )

    @classmethod
    def from_model(cls, model: Any) -> "AwaitingTypeConfigDTO":
        """Create from SQLAlchemy model."""
        # Use config_metadata (not metadata - that's SQLAlchemy's MetaData class)
        metadata_value = getattr(model, "config_metadata", None)
        return cls(
            id=str(model.id),
            awaiting_type=str(model.awaiting_type),
            target_node=str(model.target_node),
            valid_response_intents=tuple(model.valid_response_intents or []),
            validation_pattern=str(model.validation_pattern) if model.validation_pattern else None,
            priority=int(model.priority) if model.priority else 0,
            display_name=str(model.display_name) if model.display_name else None,
            metadata=metadata_value,
        )


# Type alias for the keyed configs structure
KeyedConfigs = dict[str, AwaitingTypeConfigDTO]


class AwaitingTypeCache:
    """
    Multi-layer cache for awaiting type configurations.

    Thread-safe per-organization caching with TTL-based expiration.
    L1 (Memory) -> L2 (Redis) -> L3 (Database)

    Cache key format: "{org_id or 'system'}:{domain_key}"
    """

    REDIS_KEY_PREFIX = "awaiting:types"
    MEMORY_TTL_SECONDS = 60  # 1 minute
    REDIS_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize cache with per-organization storage."""
        # Per-key memory cache: {cache_key: {"configs": KeyedConfigs, "timestamp": datetime}}
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
    ) -> KeyedConfigs:
        """
        Get all awaiting type configs keyed by awaiting_type.

        Flow: L1 (Memory) -> L2 (Redis) -> L3 (Database)

        Args:
            db: AsyncSession for database access (optional - creates own if None)
            organization_id: Tenant UUID (None for system defaults only)
            domain_key: Domain scope (default: pharmacy)

        Returns:
            Dict mapping awaiting_type to AwaitingTypeConfigDTO:
            {
                "dni": AwaitingTypeConfigDTO(target_node="auth_plex", ...),
                "amount": AwaitingTypeConfigDTO(target_node="payment_processor", ...),
                ...
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
        awaiting_type: str,
        domain_key: str = "pharmacy",
    ) -> AwaitingTypeConfigDTO | None:
        """
        Get a specific awaiting type config.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            awaiting_type: Awaiting input type (dni, amount, etc.)
            domain_key: Domain scope (default: pharmacy)

        Returns:
            AwaitingTypeConfigDTO or None if not found
        """
        configs = await self.get_configs(db, organization_id, domain_key)
        return configs.get(awaiting_type)

    async def _load_from_database_with_session(
        self,
        organization_id: UUID | None,
        domain_key: str,
    ) -> KeyedConfigs:
        """Load configs creating own database session."""
        from app.database.async_db import get_async_db_context

        async with get_async_db_context() as db:
            return await self._load_from_database(db, organization_id, domain_key)

    async def _load_from_database(
        self,
        db: "AsyncSession",
        organization_id: UUID | None,
        domain_key: str,
    ) -> KeyedConfigs:
        """Load configs from database keyed by awaiting_type."""
        from app.repositories.awaiting_type_repository import AwaitingTypeRepository

        repo = AwaitingTypeRepository(db)
        models = await repo.get_all(organization_id, domain_key, enabled_only=True)

        # Convert to DTOs keyed by awaiting_type
        keyed_dtos: KeyedConfigs = {}
        for model in models:
            dto = AwaitingTypeConfigDTO.from_model(model)
            keyed_dtos[dto.awaiting_type] = dto

        logger.debug(f"Loaded awaiting type configs from DB for org {organization_id}: " f"{len(keyed_dtos)} configs")

        return keyed_dtos

    def _get_from_memory(self, cache_key: str) -> KeyedConfigs | None:
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

    def _set_memory(self, cache_key: str, configs: KeyedConfigs) -> None:
        """Store configs in memory cache."""
        self._memory_cache[cache_key] = {
            "configs": configs,
            "timestamp": datetime.now(UTC),
        }

    async def _get_from_redis(self, cache_key: str) -> KeyedConfigs | None:
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
                return {k: AwaitingTypeConfigDTO.from_dict(v) for k, v in parsed.items()}
        except Exception as e:
            logger.warning(f"Redis get failed for {cache_key}: {e}")

        return None

    async def _set_redis(self, cache_key: str, configs: KeyedConfigs) -> None:
        """Store configs in Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return

            key = f"{self.REDIS_KEY_PREFIX}:{cache_key}"
            serializable = {k: v.to_dict() for k, v in configs.items()}
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
            f"Awaiting type cache invalidated: {count} entries " f"(org={organization_id}, domain={domain_key})"
        )

        return count

    async def warm(
        self,
        db: "AsyncSession",
        organization_id: UUID | None,
        domain_key: str = "pharmacy",
    ) -> KeyedConfigs:
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

            logger.info(f"Awaiting type cache warmed for org {organization_id}, domain {domain_key}")
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
awaiting_type_cache = AwaitingTypeCache()
