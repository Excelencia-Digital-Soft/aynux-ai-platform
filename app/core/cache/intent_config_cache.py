# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Cache multi-capa para intent configuration (mappings, flow agents,
#              keywords). L1 Memory (60s TTL) + L2 Redis (5min TTL) por org_id.
# Tenant-Aware: Yes - cada organización tiene su propio cache aislado.
# ============================================================================
"""
Intent Config Cache - Multi-layer caching for intent routing configurations.

Replaces the hardcoded values in intent_validator.py:
- AGENT_TO_INTENT_MAPPING -> get_intent_mappings()
- FLOW_AGENTS -> get_flow_agents()
- KEYWORD_TO_AGENT -> get_keyword_mappings()

Features:
- L1: In-memory cache (60s TTL, per-instance, per-organization)
- L2: Redis cache (5min TTL, distributed, per-organization)
- Automatic invalidation on config changes
- Thread-safe with asyncio locks
- Multi-tenant isolation

Usage:
    from app.core.cache.intent_config_cache import intent_config_cache

    # Get intent-to-agent mappings
    mappings = await intent_config_cache.get_intent_mappings(db, org_id)

    # Get flow agent keys
    flow_agents = await intent_config_cache.get_flow_agents(db, org_id)

    # Get keyword-to-agent mappings
    keywords = await intent_config_cache.get_keyword_mappings(db, org_id)

    # Invalidate on config changes
    await intent_config_cache.invalidate(org_id)
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


class IntentConfigCache:
    """
    Multi-layer cache for intent routing configurations.

    Thread-safe per-organization caching with TTL-based expiration.
    L1 (Memory) -> L2 (Redis) -> L3 (Database)

    Caches three types of data:
    - intent_mappings: Intent key -> Agent key mappings
    - flow_agents: Set of agent keys with multi-turn flows
    - keyword_mappings: Agent key -> List of keywords
    """

    REDIS_KEY_PREFIX = "intent_config"  # {prefix}:{type}:{org_id}
    MEMORY_TTL_SECONDS = 60  # 1 minute
    REDIS_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        """Initialize cache with per-organization storage."""
        # Per-organization memory caches
        # {org_id: {"data": dict, "timestamp": datetime}}
        self._intent_mappings_cache: dict[UUID, dict[str, Any]] = {}
        self._flow_agents_cache: dict[UUID, dict[str, Any]] = {}
        self._keyword_mappings_cache: dict[UUID, dict[str, Any]] = {}

        self._locks: dict[UUID, asyncio.Lock] = {}
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

    def _make_redis_key(self, cache_type: str, organization_id: UUID) -> str:
        """Create Redis key string."""
        return f"{self.REDIS_KEY_PREFIX}:{cache_type}:{organization_id}"

    async def _get_lock(self, organization_id: UUID) -> asyncio.Lock:
        """Get or create lock for specific organization."""
        async with self._global_lock:
            if organization_id not in self._locks:
                self._locks[organization_id] = asyncio.Lock()
            return self._locks[organization_id]

    # =========================================================================
    # INTENT MAPPINGS (replaces AGENT_TO_INTENT_MAPPING)
    # =========================================================================

    async def get_intent_mappings(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
        domain_key: str | None = None,
    ) -> dict[str, str]:
        """
        Get intent-to-agent mappings from cache.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID
            domain_key: Optional domain filter (None = all domains)

        Returns:
            Dict mapping intent_key -> agent_key
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # L1: Check memory cache
            memory_data = self._get_from_memory(
                self._intent_mappings_cache, organization_id
            )
            if memory_data is not None:
                self._stats["memory_hits"] += 1
                # Filter by domain if specified
                if domain_key:
                    return {
                        k: v for k, v in memory_data.items()
                        if memory_data.get(f"_domain_{k}") in (None, domain_key)
                    }
                return memory_data

            self._stats["memory_misses"] += 1

            # L2: Check Redis cache
            redis_data = await self._get_from_redis("mappings", organization_id)
            if redis_data is not None:
                self._stats["redis_hits"] += 1
                self._set_memory(self._intent_mappings_cache, organization_id, redis_data)
                if domain_key:
                    return {
                        k: v for k, v in redis_data.items()
                        if redis_data.get(f"_domain_{k}") in (None, domain_key)
                    }
                return redis_data

            self._stats["redis_misses"] += 1

            # L3: Load from database
            mappings = await self._load_intent_mappings_from_db(db, organization_id)
            self._stats["db_loads"] += 1

            # Populate both caches
            await self._set_redis("mappings", organization_id, mappings)
            self._set_memory(self._intent_mappings_cache, organization_id, mappings)

            if domain_key:
                return {
                    k: v for k, v in mappings.items()
                    if mappings.get(f"_domain_{k}") in (None, domain_key)
                }
            return mappings

    async def _load_intent_mappings_from_db(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> dict[str, str]:
        """Load intent mappings from database."""
        if db is None:
            from app.database.async_db import get_async_db_context
            async with get_async_db_context() as db:
                return await self._load_intent_mappings_from_db(db, organization_id)

        from sqlalchemy import select
        from app.models.db.intent_configs import IntentAgentMapping

        stmt = (
            select(IntentAgentMapping)
            .where(IntentAgentMapping.organization_id == organization_id)
            .where(IntentAgentMapping.is_enabled == True)  # noqa: E712
            .order_by(IntentAgentMapping.priority.desc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        # Build mapping dict: intent_key -> agent_key
        # Also store domain info with special keys
        mappings = {}
        for row in rows:
            mappings[row.intent_key] = row.agent_key
            if row.domain_key:
                mappings[f"_domain_{row.intent_key}"] = row.domain_key

        logger.debug(
            f"Loaded {len([k for k in mappings if not k.startswith('_')])} "
            f"intent mappings from DB for org {organization_id}"
        )
        return mappings

    # =========================================================================
    # FLOW AGENTS (replaces FLOW_AGENTS)
    # =========================================================================

    async def get_flow_agents(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> set[str]:
        """
        Get flow agent keys from cache.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID

        Returns:
            Set of agent_keys that have multi-turn flows
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # L1: Check memory cache
            memory_data = self._get_from_memory(
                self._flow_agents_cache, organization_id
            )
            if memory_data is not None:
                self._stats["memory_hits"] += 1
                return set(memory_data.get("agents", []))

            self._stats["memory_misses"] += 1

            # L2: Check Redis cache
            redis_data = await self._get_from_redis("flow_agents", organization_id)
            if redis_data is not None:
                self._stats["redis_hits"] += 1
                self._set_memory(self._flow_agents_cache, organization_id, redis_data)
                return set(redis_data.get("agents", []))

            self._stats["redis_misses"] += 1

            # L3: Load from database
            flow_agents = await self._load_flow_agents_from_db(db, organization_id)
            self._stats["db_loads"] += 1

            # Store as dict for JSON serialization
            data = {"agents": list(flow_agents)}

            # Populate both caches
            await self._set_redis("flow_agents", organization_id, data)
            self._set_memory(self._flow_agents_cache, organization_id, data)

            return flow_agents

    async def _load_flow_agents_from_db(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> set[str]:
        """Load flow agents from database."""
        if db is None:
            from app.database.async_db import get_async_db_context
            async with get_async_db_context() as db:
                return await self._load_flow_agents_from_db(db, organization_id)

        from sqlalchemy import select
        from app.models.db.intent_configs import FlowAgentConfig

        stmt = (
            select(FlowAgentConfig.agent_key)
            .where(FlowAgentConfig.organization_id == organization_id)
            .where(FlowAgentConfig.is_enabled == True)  # noqa: E712
            .where(FlowAgentConfig.is_flow_agent == True)  # noqa: E712
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        flow_agents = set(rows)
        logger.debug(
            f"Loaded {len(flow_agents)} flow agents from DB for org {organization_id}"
        )
        return flow_agents

    # =========================================================================
    # KEYWORD MAPPINGS (replaces KEYWORD_TO_AGENT)
    # =========================================================================

    async def get_keyword_mappings(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> dict[str, list[str]]:
        """
        Get keyword-to-agent mappings from cache.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID

        Returns:
            Dict mapping agent_key -> list of keywords
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # L1: Check memory cache
            memory_data = self._get_from_memory(
                self._keyword_mappings_cache, organization_id
            )
            if memory_data is not None:
                self._stats["memory_hits"] += 1
                return memory_data

            self._stats["memory_misses"] += 1

            # L2: Check Redis cache
            redis_data = await self._get_from_redis("keywords", organization_id)
            if redis_data is not None:
                self._stats["redis_hits"] += 1
                self._set_memory(self._keyword_mappings_cache, organization_id, redis_data)
                return redis_data

            self._stats["redis_misses"] += 1

            # L3: Load from database
            keywords = await self._load_keyword_mappings_from_db(db, organization_id)
            self._stats["db_loads"] += 1

            # Populate both caches
            await self._set_redis("keywords", organization_id, keywords)
            self._set_memory(self._keyword_mappings_cache, organization_id, keywords)

            return keywords

    async def _load_keyword_mappings_from_db(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> dict[str, list[str]]:
        """Load keyword mappings from database."""
        if db is None:
            from app.database.async_db import get_async_db_context
            async with get_async_db_context() as db:
                return await self._load_keyword_mappings_from_db(db, organization_id)

        from sqlalchemy import select
        from app.models.db.intent_configs import KeywordAgentMapping

        stmt = (
            select(KeywordAgentMapping)
            .where(KeywordAgentMapping.organization_id == organization_id)
            .where(KeywordAgentMapping.is_enabled == True)  # noqa: E712
            .order_by(KeywordAgentMapping.priority.desc())
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        # Build mapping: agent_key -> [keywords]
        mappings: dict[str, list[str]] = {}
        for row in rows:
            if row.agent_key not in mappings:
                mappings[row.agent_key] = []
            mappings[row.agent_key].append(row.keyword)

        logger.debug(
            f"Loaded keyword mappings for {len(mappings)} agents from DB for org {organization_id}"
        )
        return mappings

    # =========================================================================
    # COMBINED METHODS
    # =========================================================================

    async def get_all_configs(
        self,
        db: "AsyncSession | None",
        organization_id: UUID,
    ) -> dict[str, Any]:
        """
        Get all intent configurations at once.

        Args:
            db: AsyncSession for database access
            organization_id: Tenant UUID

        Returns:
            Dict with intent_mappings, flow_agents, and keyword_mappings
        """
        # Load all three types in parallel
        mappings, flow_agents, keywords = await asyncio.gather(
            self.get_intent_mappings(db, organization_id),
            self.get_flow_agents(db, organization_id),
            self.get_keyword_mappings(db, organization_id),
        )

        return {
            "intent_mappings": mappings,
            "flow_agents": list(flow_agents),
            "keyword_mappings": keywords,
        }

    # =========================================================================
    # CACHE INFRASTRUCTURE
    # =========================================================================

    def _get_from_memory(
        self,
        cache: dict[UUID, dict[str, Any]],
        organization_id: UUID,
    ) -> dict[str, Any] | None:
        """Get data from memory cache if not expired."""
        if organization_id not in cache:
            return None

        cache_entry = cache[organization_id]
        timestamp = cache_entry.get("timestamp")

        if timestamp is None:
            return None

        elapsed = (datetime.now(UTC) - timestamp).total_seconds()
        if elapsed >= self.MEMORY_TTL_SECONDS:
            # Expired
            del cache[organization_id]
            return None

        return cache_entry.get("data")

    def _set_memory(
        self,
        cache: dict[UUID, dict[str, Any]],
        organization_id: UUID,
        data: dict[str, Any],
    ) -> None:
        """Store data in memory cache."""
        cache[organization_id] = {
            "data": data,
            "timestamp": datetime.now(UTC),
        }

    async def _get_from_redis(
        self,
        cache_type: str,
        organization_id: UUID,
    ) -> dict[str, Any] | None:
        """Get data from Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return None

            key = self._make_redis_key(cache_type, organization_id)
            data = redis.get(key)

            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(
                f"Redis get failed for intent_config:{cache_type}:{organization_id}: {e}"
            )

        return None

    async def _set_redis(
        self,
        cache_type: str,
        organization_id: UUID,
        data: dict[str, Any],
    ) -> None:
        """Store data in Redis cache."""
        try:
            from app.integrations.databases.redis import get_redis_client

            redis = get_redis_client()
            if redis is None:
                return

            key = self._make_redis_key(cache_type, organization_id)
            redis.setex(key, self.REDIS_TTL_SECONDS, json.dumps(data))

        except Exception as e:
            logger.warning(
                f"Redis set failed for intent_config:{cache_type}:{organization_id}: {e}"
            )

    async def invalidate(self, organization_id: UUID) -> None:
        """
        Invalidate all caches for an organization.

        Clears both L1 (Memory) and L2 (Redis) caches.

        Args:
            organization_id: Tenant UUID
        """
        lock = await self._get_lock(organization_id)

        async with lock:
            # Clear memory caches
            if organization_id in self._intent_mappings_cache:
                del self._intent_mappings_cache[organization_id]
            if organization_id in self._flow_agents_cache:
                del self._flow_agents_cache[organization_id]
            if organization_id in self._keyword_mappings_cache:
                del self._keyword_mappings_cache[organization_id]

            # Clear Redis caches
            try:
                from app.integrations.databases.redis import get_redis_client

                redis = get_redis_client()
                if redis:
                    for cache_type in ["mappings", "flow_agents", "keywords"]:
                        key = self._make_redis_key(cache_type, organization_id)
                        redis.delete(key)
            except Exception as e:
                logger.warning(
                    f"Redis invalidation failed for org {organization_id}: {e}"
                )

            self._stats["invalidations"] += 1
            logger.info(f"Intent config cache invalidated for org {organization_id}")

    async def invalidate_all(self) -> int:
        """
        Invalidate cache for all organizations.

        Returns:
            Number of organizations invalidated
        """
        async with self._global_lock:
            count = len(self._intent_mappings_cache)

            # Clear all memory caches
            self._intent_mappings_cache.clear()
            self._flow_agents_cache.clear()
            self._keyword_mappings_cache.clear()

            # Clear all Redis keys
            try:
                from app.integrations.databases.redis import get_redis_client

                redis = get_redis_client()
                if redis:
                    pattern = f"{self.REDIS_KEY_PREFIX}:*"
                    keys = redis.keys(pattern)
                    if keys:
                        redis.delete(*keys)
                        count = max(count, len(keys) // 3)  # 3 types per org
            except Exception as e:
                logger.warning(f"Redis bulk invalidation failed: {e}")

            self._stats["invalidations"] += count
            logger.info(f"Intent config cache invalidated for all {count} organizations")

            return count

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
            "cached_organizations": len(self._intent_mappings_cache),
        }


# Singleton instance
intent_config_cache = IntentConfigCache()
