# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Cache multi-capa para response configs multi-dominio. L1 Memory
#              (60s TTL) + L2 Redis (5min TTL) por organization_id y domain_key.
# Tenant-Aware: Yes - cada organización tiene su propio cache aislado.
# Domain-Aware: Yes - soporta pharmacy, healthcare, ecommerce, etc.
# ============================================================================
"""
Response Config Cache - Multi-layer caching for multi-domain response configurations.

Features:
- L1: In-memory cache (60s TTL, per-instance, per-organization)
- L2: Redis cache (5min TTL, distributed, per-organization)
- Automatic invalidation on config changes
- Thread-safe with asyncio locks

Usage:
    from app.core.cache.response_config_cache import response_config_cache

    # Get config (auto-refreshes if expired)
    config = await response_config_cache.get_config(db, org_id, "greeting")

    # Get all configs
    configs = await response_config_cache.get_all_configs(db, org_id)

    # Invalidate on config changes
    await response_config_cache.invalidate(org_id)
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
class ResponseConfigDTO:
    """
    Immutable response configuration DTO.

    Used for cache storage to prevent accidental modification.
    """

    intent_key: str
    is_critical: bool
    task_description: str
    fallback_template_key: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent_key": self.intent_key,
            "is_critical": self.is_critical,
            "task_description": self.task_description,
            "fallback_template_key": self.fallback_template_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResponseConfigDTO":
        """Create from dictionary."""
        return cls(
            intent_key=data["intent_key"],
            is_critical=data["is_critical"],
            task_description=data["task_description"],
            fallback_template_key=data["fallback_template_key"],
        )


class ResponseConfigCache:
    """
    Multi-layer cache for pharmacy response configurations.

    Thread-safe per-organization caching with TTL-based expiration.
    L1 (Memory) → L2 (Redis) → L3 (Database)
    """

    REDIS_KEY_PREFIX = "pharmacy:response_configs"
    MEMORY_TTL_SECONDS = 60  # 1 minute
    REDIS_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize cache with per-organization storage."""
        # Per-organization memory cache: {org_id: {"configs": dict, "timestamp": datetime}}
        self._memory_cache: dict[UUID, dict[str, Any]] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
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

    async def _get_lock(self, organization_id: UUID) -> asyncio.Lock:
        """Get or create lock for specific organization."""
        async with self._global_lock:
            if organization_id not in self._locks:
                self._locks[organization_id] = asyncio.Lock()
            return self._locks[organization_id]

    async def get_all_configs(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> dict[str, ResponseConfigDTO]:
        """
        Get all response configs with multi-layer caching.

        Flow: L1 (Memory) → L2 (Redis) → L3 (Database)

        Args:
            db: AsyncSession for database access (optional - creates own session if None)
            organization_id: Tenant UUID
            domain_key: Domain scope (default: pharmacy)

        Returns:
            Dict mapping intent_key to ResponseConfigDTO
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # L1: Check memory cache
            memory_data = self._get_from_memory(organization_id)
            if memory_data is not None:
                self._stats["memory_hits"] += 1
                return memory_data

            self._stats["memory_misses"] += 1

            # L2: Check Redis cache
            redis_data = await self._get_from_redis(organization_id)
            if redis_data is not None:
                self._stats["redis_hits"] += 1
                # Populate L1 from L2
                self._set_memory(organization_id, redis_data)
                return redis_data

            self._stats["redis_misses"] += 1

            # L3: Load from database
            if db is None:
                configs = await self._load_from_database_with_session(
                    organization_id, domain_key
                )
            else:
                configs = await self._load_from_database(db, organization_id, domain_key)

            self._stats["db_loads"] += 1

            # Populate both caches
            await self._set_redis(organization_id, configs)
            self._set_memory(organization_id, configs)

            return configs

    async def get_config(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        intent_key: str,
        domain_key: str = "pharmacy",
    ) -> ResponseConfigDTO | None:
        """
        Get single response config by intent key.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            intent_key: Intent identifier (e.g., "greeting")
            domain_key: Domain scope (default: pharmacy)

        Returns:
            ResponseConfigDTO or None if not found
        """
        configs = await self.get_all_configs(db, organization_id, domain_key)
        return configs.get(intent_key)

    async def _load_from_database_with_session(
        self,
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, ResponseConfigDTO]:
        """Load configs creating own database session."""
        from app.database.async_db import get_async_db_context

        async with get_async_db_context() as db:
            return await self._load_from_database(db, organization_id, domain_key)

    async def _load_from_database(
        self,
        db: "AsyncSession",
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, ResponseConfigDTO]:
        """Load configs from database."""
        from app.repositories.response_config_repository import ResponseConfigRepository

        repo = ResponseConfigRepository(db)
        db_configs = await repo.get_all_configs(organization_id, domain_key)

        configs = {
            str(config.intent_key): ResponseConfigDTO(
                intent_key=str(config.intent_key),
                is_critical=bool(config.is_critical),
                task_description=str(config.task_description),
                fallback_template_key=str(config.fallback_template_key),
            )
            for config in db_configs
        }

        logger.debug(
            f"Loaded {len(configs)} response configs from DB for org {organization_id}"
        )

        return configs

    def _get_from_memory(self, organization_id: UUID) -> dict[str, ResponseConfigDTO] | None:
        """Get configs from memory cache if not expired."""
        if organization_id not in self._memory_cache:
            return None

        cache_entry = self._memory_cache[organization_id]
        timestamp = cache_entry.get("timestamp")

        if timestamp is None:
            return None

        elapsed = (datetime.now(UTC) - timestamp).total_seconds()
        if elapsed >= self.MEMORY_TTL_SECONDS:
            # Expired
            del self._memory_cache[organization_id]
            return None

        return cache_entry.get("configs")

    def _set_memory(
        self, organization_id: UUID, configs: dict[str, ResponseConfigDTO]
    ) -> None:
        """Store configs in memory cache."""
        self._memory_cache[organization_id] = {
            "configs": configs,
            "timestamp": datetime.now(UTC),
        }

    async def _get_from_redis(
        self, organization_id: UUID
    ) -> dict[str, ResponseConfigDTO] | None:
        """Get configs from Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return None

            key = f"{self.REDIS_KEY_PREFIX}:{organization_id}"
            data = redis.get(key)

            if data:
                parsed = json.loads(data)
                return {
                    k: ResponseConfigDTO.from_dict(v)
                    for k, v in parsed.items()
                }
        except Exception as e:
            logger.warning(f"Redis get failed for org {organization_id}: {e}")

        return None

    async def _set_redis(
        self, organization_id: UUID, configs: dict[str, ResponseConfigDTO]
    ) -> None:
        """Store configs in Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return

            key = f"{self.REDIS_KEY_PREFIX}:{organization_id}"
            serializable = {k: v.to_dict() for k, v in configs.items()}
            redis.setex(key, self.REDIS_TTL_SECONDS, json.dumps(serializable))

        except Exception as e:
            logger.warning(f"Redis set failed for org {organization_id}: {e}")

    async def invalidate(self, organization_id: UUID) -> None:
        """
        Invalidate cache for a specific organization.

        Clears both L1 (Memory) and L2 (Redis) caches.

        Args:
            organization_id: Tenant UUID to invalidate
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # Clear memory cache
            if organization_id in self._memory_cache:
                del self._memory_cache[organization_id]

            # Clear Redis cache
            try:
                from app.integrations.databases.redis import get_redis_client

                redis = get_redis_client()
                if redis:
                    key = f"{self.REDIS_KEY_PREFIX}:{organization_id}"
                    redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis invalidation failed for org {organization_id}: {e}")

            self._stats["invalidations"] += 1
            logger.info(f"Response config cache invalidated for org {organization_id}")

    async def invalidate_all(self) -> int:
        """
        Invalidate cache for all organizations.

        Use with caution - mainly for admin operations.

        Returns:
            Number of organizations invalidated
        """
        async with self._global_lock:
            count = len(self._memory_cache)

            # Clear all memory caches
            self._memory_cache.clear()

            # Clear all Redis keys
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
            logger.info(f"Response config cache invalidated for all {count} organizations")

            return count

    async def warm(
        self,
        db: "AsyncSession",
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> dict[str, ResponseConfigDTO]:
        """
        Warm cache for a specific organization.

        Force-loads from database and populates both caches.

        Args:
            db: AsyncSession
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Loaded configs
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # Force load from database
            configs = await self._load_from_database(db, organization_id, domain_key)

            # Populate both caches
            await self._set_redis(organization_id, configs)
            self._set_memory(organization_id, configs)

            logger.info(f"Response config cache warmed for org {organization_id}")
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
            "memory_hit_rate": (
                self._stats["memory_hits"] / total_memory if total_memory > 0 else 0
            ),
            "redis_hits": self._stats["redis_hits"],
            "redis_misses": self._stats["redis_misses"],
            "redis_hit_rate": (
                self._stats["redis_hits"] / total_redis if total_redis > 0 else 0
            ),
            "db_loads": self._stats["db_loads"],
            "invalidations": self._stats["invalidations"],
            "cached_organizations": len(self._memory_cache),
        }

    def get_cached_organizations(self) -> list[str]:
        """Get list of organization IDs currently in memory cache.

        Returns:
            List of organization UUID strings
        """
        return [str(org_id) for org_id in self._memory_cache.keys()]


# Singleton instance
response_config_cache = ResponseConfigCache()
