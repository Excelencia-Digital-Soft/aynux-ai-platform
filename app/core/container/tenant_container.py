# ============================================================================
# SCOPE: MIXED (TenantConfigCache=GLOBAL, TenantDependencyContainer=MULTI-TENANT)
# Description: Contenedor de dependencias con scope de tenant. Envuelve servicios
#              globales (LLM, VectorStore) con contexto de organización.
# Tenant-Aware: Yes - todos los métodos respetan TenantContext.
# ============================================================================
"""
TenantDependencyContainer - Tenant-aware dependency injection container.

Provides tenant-scoped services with Redis caching for TenantConfig.
Maintains dual-mode operation: falls back to global container for generic mode.

Features:
- Redis-cached TenantConfig with configurable TTL
- Tenant-scoped VectorStore (TenantVectorStore)
- Tenant-scoped PromptManager (TenantPromptManager)
- Per-tenant LLM configuration
- Cache invalidation support

Usage:
    # From TenantContext (in request handling)
    container = TenantDependencyContainer.from_context()
    vector_store = container.get_vector_store()
    prompt_manager = container.create_prompt_manager()

    # Explicit organization
    container = TenantDependencyContainer(ctx)
    llm = container.get_llm()
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from sqlalchemy import select

from app.core.interfaces.llm import ILLM
from app.core.interfaces.vector_store import IVectorStore
from app.core.tenancy.context import TenantContext, require_tenant_context
from app.core.tenancy.prompt_manager import TenantPromptManager
from app.core.tenancy.vector_store import TenantVectorStore
from app.database.async_db import get_async_db_context
from app.integrations.databases.redis import get_redis_client
from app.integrations.llm import create_vllm_llm
from app.models.db.tenancy import TenantConfig

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)


class TenantConfigCache:
    """
    [GLOBAL] Redis cache for TenantConfig - singleton compartido.

    Caches tenant configuration to avoid database lookups on every request.
    Supports TTL-based expiration and explicit invalidation.

    Usage:
        cache = TenantConfigCache()
        config = await cache.get(org_id)
        if not config:
            config = await load_from_db(org_id)
            cache.set(org_id, config)

        # On config update
        cache.invalidate(org_id)
    """

    # Cache configuration
    TTL_SECONDS: ClassVar[int] = 300  # 5 minutes
    KEY_PREFIX: ClassVar[str] = "tenant_config:"

    def __init__(self, redis_client: redis.Redis | None = None):
        """
        Initialize cache.

        Args:
            redis_client: Redis client instance (uses singleton if None).
        """
        self._redis = redis_client

    @property
    def redis(self) -> redis.Redis:
        """Get Redis client (lazy initialization)."""
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def _make_key(self, org_id: UUID) -> str:
        """Generate cache key for organization."""
        return f"{self.KEY_PREFIX}{org_id}"

    def get(self, org_id: UUID) -> dict | None:
        """
        Get cached TenantConfig as dict.

        Args:
            org_id: Organization UUID.

        Returns:
            Config dict if cached, None otherwise.
        """
        try:
            key = self._make_key(org_id)
            data: bytes | str | None = self.redis.get(key)  # type: ignore[assignment]

            if data:
                logger.debug(f"Cache HIT for tenant config: {org_id}")
                if isinstance(data, bytes):
                    return json.loads(data.decode("utf-8"))
                return json.loads(data)

            logger.debug(f"Cache MISS for tenant config: {org_id}")
            return None

        except Exception as e:
            logger.warning(f"Redis cache get error for {org_id}: {e}")
            return None

    def set(self, org_id: UUID, config_dict: dict) -> bool:
        """
        Cache TenantConfig as JSON.

        Args:
            org_id: Organization UUID.
            config_dict: Config dictionary to cache.

        Returns:
            True if cached successfully.
        """
        try:
            key = self._make_key(org_id)
            self.redis.setex(
                name=key,
                time=self.TTL_SECONDS,
                value=json.dumps(config_dict),
            )
            logger.debug(f"Cached tenant config: {org_id} (TTL: {self.TTL_SECONDS}s)")
            return True

        except Exception as e:
            logger.warning(f"Redis cache set error for {org_id}: {e}")
            return False

    def invalidate(self, org_id: UUID) -> bool:
        """
        Invalidate cached TenantConfig.

        Should be called when config is updated.

        Args:
            org_id: Organization UUID.

        Returns:
            True if invalidated successfully.
        """
        try:
            key = self._make_key(org_id)
            deleted = self.redis.delete(key)
            logger.info(f"Invalidated tenant config cache: {org_id} (deleted: {deleted})")
            return True

        except Exception as e:
            logger.warning(f"Redis cache invalidation error for {org_id}: {e}")
            return False

    def invalidate_all(self) -> int:
        """
        Invalidate all tenant config caches.

        Returns:
            Number of keys deleted.
        """
        try:
            pattern = f"{self.KEY_PREFIX}*"
            keys: list[bytes] | list[str] = self.redis.keys(pattern)  # type: ignore[assignment]
            if keys:
                deleted: int = self.redis.delete(*keys)  # type: ignore[assignment]
                logger.info(f"Invalidated {deleted} tenant config caches")
                return deleted
            return 0

        except Exception as e:
            logger.warning(f"Redis bulk invalidation error: {e}")
            return 0


class TenantDependencyContainer:
    """
    [MULTI-TENANT] Contenedor de dependencias con scope de request.

    Provides tenant-scoped services based on TenantContext.
    Caches TenantConfig in Redis for performance.

    Usage:
        # From context (in request)
        container = TenantDependencyContainer.from_context()
        vector_store = container.get_vector_store()  # [MULTI-TENANT] Filtrado por org_id

        # Explicit context
        container = TenantDependencyContainer(ctx)
        prompt_manager = container.create_prompt_manager()  # [MULTI-TENANT] Jerárquico

    Attributes:
        ctx: TenantContext for this container instance.

    Note:
        This container is request-scoped. Create a new instance per request
        rather than using as a singleton.
    """

    # Shared cache instance (thread-safe)
    _config_cache: ClassVar[TenantConfigCache | None] = None

    # Cached config for this request
    _cached_config: dict | None = None

    def __init__(self, ctx: TenantContext | None = None):
        """
        Initialize tenant container.

        Args:
            ctx: TenantContext (uses require_tenant_context() if None).

        Raises:
            RuntimeError: If no tenant context available.
        """
        self.ctx = ctx or require_tenant_context()

        # Initialize shared cache if needed
        if TenantDependencyContainer._config_cache is None:
            TenantDependencyContainer._config_cache = TenantConfigCache()

        logger.debug(f"TenantDependencyContainer initialized: org={self.ctx.organization_id}")

    @classmethod
    def from_context(cls) -> TenantDependencyContainer:
        """
        Create container from current TenantContext.

        Returns:
            TenantDependencyContainer instance.

        Raises:
            RuntimeError: If no tenant context set.
        """
        return cls(require_tenant_context())

    @classmethod
    def get_cache(cls) -> TenantConfigCache:
        """
        Get shared config cache instance.

        Returns:
            TenantConfigCache instance.
        """
        if cls._config_cache is None:
            cls._config_cache = TenantConfigCache()
        return cls._config_cache

    @property
    def organization_id(self) -> UUID:
        """Get organization ID from context."""
        return self.ctx.organization_id

    async def get_config(self) -> dict:
        """
        Get TenantConfig for this tenant.

        Checks Redis cache first, falls back to database.
        Caches result for subsequent calls in this request.

        Returns:
            Config dictionary.
        """
        # Check request-level cache
        if self._cached_config is not None:
            return self._cached_config

        org_id = self.organization_id
        cache = self.get_cache()

        # Check Redis cache
        cached = cache.get(org_id)
        if cached:
            self._cached_config = cached
            return cached

        # Load from database
        async with get_async_db_context() as db:
            stmt = select(TenantConfig).where(TenantConfig.organization_id == org_id)
            result = await db.execute(stmt)
            config = result.scalar_one_or_none()

            if config:
                config_dict = config.to_dict()
                cache.set(org_id, config_dict)
                self._cached_config = config_dict
                return config_dict

        # Return defaults if no config found
        default_config = {
            "rag_enabled": True,
            "rag_similarity_threshold": 0.7,
            "rag_max_results": 5,
            "enabled_domains": [],
            "enabled_agent_types": [],
        }
        self._cached_config = default_config
        return default_config

    def get_config_sync(self) -> dict:
        """
        Get TenantConfig synchronously (cache only).

        Only returns cached config. Use get_config() for full resolution.

        Returns:
            Cached config dict or defaults.
        """
        if self._cached_config:
            return self._cached_config

        cache = self.get_cache()
        cached = cache.get(self.organization_id)
        if cached:
            self._cached_config = cached
            return cached

        # Return context-based defaults
        return {
            "rag_enabled": self.ctx.rag_enabled,
            "rag_similarity_threshold": self.ctx.rag_similarity_threshold,
            "rag_max_results": self.ctx.rag_max_results,
            "enabled_domains": list(self.ctx.enabled_domains),
            "enabled_agent_types": list(self.ctx.enabled_agents),
        }

    def get_vector_store(self) -> IVectorStore:
        """
        Get tenant-scoped VectorStore.

        Returns:
            TenantVectorStore instance scoped to this organization.
        """
        return TenantVectorStore(organization_id=self.organization_id)

    def create_prompt_manager(self) -> TenantPromptManager:
        """
        Create tenant-scoped PromptManager.

        Returns:
            TenantPromptManager with scope hierarchy (USER > ORG > GLOBAL > SYSTEM).
        """
        return TenantPromptManager(
            organization_id=self.organization_id,
            user_id=self.ctx.user_id,
        )

    def get_llm(self) -> ILLM:
        """
        Get LLM configured for this tenant.

        Uses vLLM with tenant's temperature setting from TenantContext.

        Returns:
            ILLM instance (VllmLLM) configured for tenant.
        """
        return create_vllm_llm(
            temperature=self.ctx.llm_temperature,
        )

    def get_similarity_threshold(self) -> float:
        """Get RAG similarity threshold for this tenant."""
        return self.ctx.rag_similarity_threshold

    def get_max_results(self) -> int:
        """Get RAG max results for this tenant."""
        return self.ctx.rag_max_results

    def is_rag_enabled(self) -> bool:
        """Check if RAG is enabled for this tenant."""
        return self.ctx.rag_enabled


# ============================================================
# FACTORY FUNCTIONS
# ============================================================


def get_tenant_config_cache() -> TenantConfigCache:
    """
    Get shared TenantConfigCache instance.

    Returns:
        TenantConfigCache singleton.
    """
    return TenantDependencyContainer.get_cache()


def invalidate_tenant_config(org_id: UUID) -> bool:
    """
    Invalidate cached config for an organization.

    Call this when TenantConfig is updated.

    Args:
        org_id: Organization UUID.

    Returns:
        True if invalidated.
    """
    cache = get_tenant_config_cache()
    return cache.invalidate(org_id)


__all__ = [
    "TenantConfigCache",
    "TenantDependencyContainer",
    "get_tenant_config_cache",
    "invalidate_tenant_config",
]
