# ============================================================================
# SCOPE: MULTI-TENANT + MULTI-DOMAIN
# Description: Cache multi-capa para domain intent patterns. L1 Memory
#              (60s TTL) + L2 Redis (5min TTL) por organization_id y domain_key.
# Tenant-Aware: Yes - cada organización tiene su propio cache aislado por dominio.
# ============================================================================
"""
Domain Intent Cache - Multi-layer caching for unified domain intent patterns.

Features:
- L1: In-memory cache (60s TTL, per-instance, per-organization, per-domain)
- L2: Redis cache (5min TTL, distributed, per-organization, per-domain)
- Automatic invalidation on pattern changes
- Thread-safe with asyncio locks
- Multi-domain support (pharmacy, excelencia, ecommerce, healthcare, etc.)

Usage:
    from app.core.cache.domain_intent_cache import domain_intent_cache

    # Get patterns (auto-refreshes if expired)
    patterns = await domain_intent_cache.get_patterns(db, org_id, "pharmacy")

    # Invalidate on pattern changes (domain-specific)
    await domain_intent_cache.invalidate(org_id, "pharmacy")

    # Invalidate all domains for an org
    await domain_intent_cache.invalidate_all_domains(org_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Cache key type for (org_id, domain_key)
CacheKey = tuple[UUID, str]


class DomainIntentCache:
    """
    Multi-layer cache for domain intent patterns.

    Thread-safe per-organization, per-domain caching with TTL-based expiration.
    L1 (Memory) -> L2 (Redis) -> L3 (Database)
    """

    REDIS_KEY_PREFIX = "intent_patterns"  # {prefix}:{org_id}:{domain_key}
    MEMORY_TTL_SECONDS = 60  # 1 minute
    REDIS_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize cache with per-organization, per-domain storage."""
        # Per-organization, per-domain memory cache
        # {(org_id, domain_key): {"patterns": dict, "timestamp": datetime}}
        self._memory_cache: dict[CacheKey, dict[str, Any]] = {}
        self._locks: dict[CacheKey, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Stats for monitoring
        self._stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "db_loads": 0,
            "invalidations": 0,
        }

    def _make_cache_key(self, organization_id: UUID, domain_key: str) -> CacheKey:
        """Create cache key tuple from org_id and domain_key."""
        return (organization_id, domain_key)

    def _make_redis_key(self, organization_id: UUID, domain_key: str) -> str:
        """Create Redis key string."""
        return f"{self.REDIS_KEY_PREFIX}:{organization_id}:{domain_key}"

    async def _get_lock(self, cache_key: CacheKey) -> asyncio.Lock:
        """Get or create lock for specific cache key."""
        async with self._global_lock:
            if cache_key not in self._locks:
                self._locks[cache_key] = asyncio.Lock()
            return self._locks[cache_key]

    async def get_patterns(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, Any]:
        """
        Get intent patterns with multi-layer caching.

        Flow: L1 (Memory) -> L2 (Redis) -> L3 (Database)

        Args:
            db: AsyncSession for database access (optional - creates own session if None)
            organization_id: Tenant UUID
            domain_key: Domain scope (e.g., "pharmacy", "excelencia")

        Returns:
            Structured patterns dict for IntentAnalyzer
        """
        cache_key = self._make_cache_key(organization_id, domain_key)
        lock = await self._get_lock(cache_key)

        async with lock:
            # L1: Check memory cache
            memory_data = self._get_from_memory(cache_key)
            if memory_data is not None:
                self._stats["memory_hits"] += 1
                return memory_data

            self._stats["memory_misses"] += 1

            # L2: Check Redis cache
            redis_data = await self._get_from_redis(organization_id, domain_key)
            if redis_data is not None:
                self._stats["redis_hits"] += 1
                # Populate L1 from L2
                self._set_memory(cache_key, redis_data)
                return redis_data

            self._stats["redis_misses"] += 1

            # L3: Load from database
            if db is None:
                patterns = await self._load_from_database_with_session(
                    organization_id, domain_key
                )
            else:
                patterns = await self._load_from_database(db, organization_id, domain_key)

            self._stats["db_loads"] += 1

            # Populate both caches
            await self._set_redis(organization_id, domain_key, patterns)
            self._set_memory(cache_key, patterns)

            return patterns

    async def _load_from_database_with_session(
        self,
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, Any]:
        """Load patterns creating own database session."""
        from app.database.async_db import get_async_db_context

        async with get_async_db_context() as db:
            return await self._load_from_database(db, organization_id, domain_key)

    def _get_from_memory(self, cache_key: CacheKey) -> dict[str, Any] | None:
        """Get patterns from memory cache if not expired."""
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

        return cache_entry.get("patterns")

    def _set_memory(self, cache_key: CacheKey, patterns: dict[str, Any]) -> None:
        """Store patterns in memory cache."""
        self._memory_cache[cache_key] = {
            "patterns": patterns,
            "timestamp": datetime.now(UTC),
        }

    async def _get_from_redis(
        self, organization_id: UUID, domain_key: str
    ) -> dict[str, Any] | None:
        """Get patterns from Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return None

            key = self._make_redis_key(organization_id, domain_key)
            data = redis.get(key)

            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(
                f"Redis get failed for org {organization_id}, domain {domain_key}: {e}"
            )

        return None

    async def _set_redis(
        self, organization_id: UUID, domain_key: str, patterns: dict[str, Any]
    ) -> None:
        """Store patterns in Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return

            key = self._make_redis_key(organization_id, domain_key)

            # Convert sets to lists for JSON serialization
            serializable = self._make_serializable(patterns)
            redis.setex(key, self.REDIS_TTL_SECONDS, json.dumps(serializable))

        except Exception as e:
            logger.warning(
                f"Redis set failed for org {organization_id}, domain {domain_key}: {e}"
            )

    def _make_serializable(self, patterns: dict[str, Any]) -> dict[str, Any]:
        """Convert sets to lists for JSON serialization."""
        result = patterns.copy()

        # Convert confirmation patterns sets
        if "confirmation_patterns" in result:
            for data in result["confirmation_patterns"].values():
                if isinstance(data.get("exact"), set):
                    data["exact"] = list(data["exact"])
                if isinstance(data.get("contains"), set):
                    data["contains"] = list(data["contains"])

        # Convert greeting patterns
        if "greeting_patterns" in result:
            if isinstance(result["greeting_patterns"].get("exact"), set):
                result["greeting_patterns"]["exact"] = list(
                    result["greeting_patterns"]["exact"]
                )

        # Convert valid_intents
        if isinstance(result.get("valid_intents"), set):
            result["valid_intents"] = list(result["valid_intents"])

        return result

    async def _load_from_database(
        self,
        db: "AsyncSession",
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, Any]:
        """Load patterns from database using new unified repository."""
        from app.repositories.domain_intent_repository import DomainIntentRepository

        repo = DomainIntentRepository(db)
        patterns = await repo.get_all_patterns_structured(organization_id, domain_key)

        logger.debug(
            f"Loaded patterns from DB for org {organization_id}, domain {domain_key}: "
            f"{len(patterns.get('valid_intents', set()))} intents"
        )

        return patterns

    async def invalidate(self, organization_id: UUID, domain_key: str) -> None:
        """
        Invalidate cache for a specific organization and domain.

        Clears both L1 (Memory) and L2 (Redis) caches.

        Args:
            organization_id: Tenant UUID
            domain_key: Domain to invalidate
        """
        cache_key = self._make_cache_key(organization_id, domain_key)
        lock = await self._get_lock(cache_key)

        async with lock:
            # Clear memory cache
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]

            # Clear Redis cache
            try:
                from app.integrations.databases.redis import get_redis_client

                redis = get_redis_client()
                if redis:
                    key = self._make_redis_key(organization_id, domain_key)
                    redis.delete(key)
            except Exception as e:
                logger.warning(
                    f"Redis invalidation failed for org {organization_id}, "
                    f"domain {domain_key}: {e}"
                )

            self._stats["invalidations"] += 1
            logger.info(
                f"Domain intent cache invalidated for org {organization_id}, "
                f"domain {domain_key}"
            )

    async def invalidate_all_domains(self, organization_id: UUID) -> int:
        """
        Invalidate cache for all domains of an organization.

        Args:
            organization_id: Tenant UUID

        Returns:
            Number of domains invalidated
        """
        count = 0

        async with self._global_lock:
            # Find all cache keys for this org
            keys_to_delete = [
                key for key in self._memory_cache.keys()
                if key[0] == organization_id
            ]

            # Clear memory caches
            for key in keys_to_delete:
                del self._memory_cache[key]
                count += 1

            # Clear Redis keys
            try:
                from app.integrations.databases.redis import get_redis_client

                redis = get_redis_client()
                if redis:
                    pattern = f"{self.REDIS_KEY_PREFIX}:{organization_id}:*"
                    keys = redis.keys(pattern)
                    if keys:
                        redis.delete(*keys)
                        count = max(count, len(keys))
            except Exception as e:
                logger.warning(
                    f"Redis bulk invalidation failed for org {organization_id}: {e}"
                )

            self._stats["invalidations"] += count
            logger.info(
                f"Domain intent cache invalidated for all {count} domains of org {organization_id}"
            )

            return count

    async def invalidate_all(self) -> int:
        """
        Invalidate cache for all organizations and domains.

        Use with caution - mainly for admin operations.

        Returns:
            Number of cache entries invalidated
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
            logger.info(f"Domain intent cache invalidated for all {count} entries")

            return count

    async def warm(
        self,
        db: "AsyncSession",
        organization_id: UUID,
        domain_key: str,
    ) -> dict[str, Any]:
        """
        Warm cache for a specific organization and domain.

        Force-loads from database and populates both caches.

        Args:
            db: AsyncSession
            organization_id: Tenant UUID
            domain_key: Domain scope

        Returns:
            Loaded patterns
        """
        cache_key = self._make_cache_key(organization_id, domain_key)
        lock = await self._get_lock(cache_key)

        async with lock:
            # Force load from database
            patterns = await self._load_from_database(db, organization_id, domain_key)

            # Populate both caches
            await self._set_redis(organization_id, domain_key, patterns)
            self._set_memory(cache_key, patterns)

            logger.info(f"Cache warmed for org {organization_id}, domain {domain_key}")
            return patterns

    # =========================================================================
    # HELPER METHODS - Extracted patterns for specific use cases
    # =========================================================================

    async def get_capability_patterns(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> set[str]:
        """Get capability question phrases from cache."""
        patterns = await self.get_patterns(db, organization_id, domain_key)
        capability = patterns.get("intents", {}).get("capability_question", {})
        phrases = capability.get("phrases", [])

        return {p["phrase"].lower() for p in phrases if isinstance(p, dict) and "phrase" in p}

    async def get_payment_patterns(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> tuple[set[str], set[str]]:
        """Get payment verbs and phrases from invoice intent."""
        patterns = await self.get_patterns(db, organization_id, domain_key)
        invoice = patterns.get("intents", {}).get("invoice", {})

        lemmas = invoice.get("lemmas", [])
        payment_verbs = {lemma.lower() for lemma in lemmas if isinstance(lemma, str)}

        phrases = invoice.get("phrases", [])
        payment_phrases = {
            p["phrase"].lower()
            for p in phrases
            if isinstance(p, dict) and "phrase" in p
        }

        return payment_verbs, payment_phrases

    async def get_confirmation_patterns(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> dict[str, dict[str, set[str]]]:
        """Get confirmation patterns (confirm/reject) from cache."""
        patterns = await self.get_patterns(db, organization_id, domain_key)
        return patterns.get("confirmation_patterns", {})

    async def get_greeting_patterns(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str = "pharmacy",
    ) -> dict[str, Any]:
        """Get greeting patterns from cache."""
        patterns = await self.get_patterns(db, organization_id, domain_key)
        return patterns.get("greeting_patterns", {"exact": set(), "prefixes": []})

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
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
            "cached_entries": len(self._memory_cache),
        }

    def get_cached_entries(self) -> list[dict[str, str]]:
        """Get list of cached org/domain pairs."""
        return [
            {"organization_id": str(org_id), "domain_key": domain_key}
            for org_id, domain_key in self._memory_cache.keys()
        ]


# Singleton instance
domain_intent_cache = DomainIntentCache()
