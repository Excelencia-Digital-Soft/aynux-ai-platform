# ============================================================================
# SCOPE: GLOBAL
# Description: Cache in-memory para agentes habilitados. Evita queries
#              repetidas a la base de datos. TTL de 60 segundos.
# Tenant-Aware: No - cache global de agentes habilitados.
# ============================================================================
"""
Agent Cache - In-memory cache for enabled agent keys.

Provides TTL-based caching for the list of enabled agent keys.
Reduces database queries for frequently accessed agent configuration.

Features:
- TTL-based expiration (60 seconds default)
- Thread-safe singleton pattern
- Automatic refresh on expiration
- Manual invalidation on agent changes

Usage:
    from app.core.cache.agent_cache import agent_cache

    # Get enabled keys (auto-refreshes if expired)
    keys = await agent_cache.get_enabled_keys(db)

    # Invalidate on agent changes
    agent_cache.invalidate()
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AgentCache:
    """
    In-memory cache for enabled agent keys.

    Thread-safe singleton with TTL-based expiration.
    """

    # Default TTL in seconds
    DEFAULT_TTL_SECONDS: int = 60

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """Initialize cache with TTL.

        Args:
            ttl_seconds: Cache TTL in seconds (default: 60)
        """
        self._ttl_seconds = ttl_seconds
        self._enabled_keys: list[str] | None = None
        self._enabled_configs: list[dict] | None = None
        self._last_refresh: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def is_expired(self) -> bool:
        """Check if cache is expired.

        Returns:
            True if cache is expired or empty
        """
        if self._enabled_keys is None or self._last_refresh is None:
            return True

        elapsed = (datetime.now(UTC) - self._last_refresh).total_seconds()
        return elapsed >= self._ttl_seconds

    def invalidate(self) -> None:
        """Invalidate cache, forcing refresh on next access."""
        self._enabled_keys = None
        self._enabled_configs = None
        self._last_refresh = None
        logger.debug("Agent cache invalidated")

    async def get_enabled_keys(self, db: "AsyncSession") -> list[str]:
        """Get list of enabled agent keys.

        Auto-refreshes if cache is expired.

        Args:
            db: AsyncSession for database access

        Returns:
            List of enabled agent keys
        """
        async with self._lock:
            if self.is_expired:
                await self._refresh(db)

            return self._enabled_keys or []

    async def get_enabled_configs(self, db: "AsyncSession") -> list[dict]:
        """Get list of enabled agent configurations.

        Auto-refreshes if cache is expired.

        Args:
            db: AsyncSession for database access

        Returns:
            List of enabled agent config dicts
        """
        async with self._lock:
            if self.is_expired:
                await self._refresh(db)

            return self._enabled_configs or []

    async def _refresh(self, db: "AsyncSession") -> None:
        """Refresh cache from database.

        Args:
            db: AsyncSession for database access
        """
        from app.repositories.agent_repository import AgentRepository

        try:
            repository = AgentRepository(db)

            # Get enabled keys
            self._enabled_keys = await repository.get_enabled_keys()

            # Get enabled configs
            self._enabled_configs = await repository.get_enabled_for_config()

            self._last_refresh = datetime.now(UTC)

            logger.debug(
                f"Agent cache refreshed: {len(self._enabled_keys)} enabled agents"
            )

        except Exception as e:
            logger.error(f"Error refreshing agent cache: {e}")
            # Keep stale data if refresh fails
            if self._enabled_keys is None:
                self._enabled_keys = []
            if self._enabled_configs is None:
                self._enabled_configs = []

    def get_cached_keys(self) -> list[str]:
        """Get cached keys without refresh (may be stale).

        Use this for non-critical synchronous access.

        Returns:
            Cached list of enabled agent keys (may be stale or empty)
        """
        return self._enabled_keys or []

    def get_cached_configs(self) -> list[dict]:
        """Get cached configs without refresh (may be stale).

        Use this for non-critical synchronous access.

        Returns:
            Cached list of enabled agent configs (may be stale or empty)
        """
        return self._enabled_configs or []


# Singleton instance
agent_cache = AgentCache()
