"""
Cache Utilities

Provides in-memory caching with TTL support and async-compatible decorators.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Awaitable, Callable, Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


@dataclass
class CacheEntry:
    """A single cache entry with expiration."""

    value: Any
    expires_at: float | None = None  # Unix timestamp, None = no expiration
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Update access tracking."""
        self.access_count += 1
        self.last_accessed = time.time()


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "hit_rate": self.hit_rate,
        }


class MemoryCache:
    """
    In-memory cache with TTL support and LRU eviction.

    Thread-safe and async-compatible cache implementation.

    Example:
        ```python
        cache = MemoryCache(max_size=1000, default_ttl=300)

        # Basic usage
        cache.set("key", "value", ttl=60)
        value = cache.get("key")

        # Async usage
        await cache.async_get("key")
        await cache.async_set("key", "value")
        ```
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float | None = None,
        cleanup_interval: float = 60.0,
    ):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds (None = no expiration)
            cleanup_interval: Interval for automatic cleanup
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    def start_cleanup(self) -> None:
        """Start automatic cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    def stop_cleanup(self) -> None:
        """Stop automatic cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.async_cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        entry = self._cache.get(key)

        if entry is None:
            self._stats.misses += 1
            return default

        if entry.is_expired:
            del self._cache[key]
            self._stats.expirations += 1
            self._stats.misses += 1
            return default

        entry.touch()
        self._stats.hits += 1
        return entry.value

    async def async_get(self, key: str, default: Any = None) -> Any:
        """Async version of get."""
        async with self._lock:
            return self.get(key, default)

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        # Evict if at max size
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()

        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + effective_ttl if effective_ttl else None

        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    async def async_set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Async version of set."""
        async with self._lock:
            self.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def async_delete(self, key: str) -> bool:
        """Async version of delete."""
        async with self._lock:
            return self.delete(key)

    def has(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        entry = self._cache.get(key)
        if entry is None:
            return False
        if entry.is_expired:
            del self._cache[key]
            return False
        return True

    async def async_has(self, key: str) -> bool:
        """Async version of has."""
        async with self._lock:
            return self.has(key)

    def clear(self) -> int:
        """
        Clear all entries from cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        return count

    async def async_clear(self) -> int:
        """Async version of clear."""
        async with self._lock:
            return self.clear()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [k for k, v in self._cache.items() if v.is_expired]
        for key in expired_keys:
            del self._cache[key]
            self._stats.expirations += 1
        return len(expired_keys)

    async def async_cleanup_expired(self) -> int:
        """Async version of cleanup_expired."""
        async with self._lock:
            return self.cleanup_expired()

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find LRU entry
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]
        self._stats.evictions += 1

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def get_info(self) -> dict[str, Any]:
        """Get cache information."""
        return {
            "size": self.size,
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "stats": self._stats.to_dict(),
        }


class CachedFunction(Protocol[T_co]):
    """Protocol for cached function with cache control attributes."""

    cache: MemoryCache
    invalidate: Callable[..., bool]

    def __call__(self, *args: Any, **kwargs: Any) -> Awaitable[T_co]: ...


def cached(
    ttl: float | None = None,
    key_prefix: str = "",
    cache: MemoryCache | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], CachedFunction[T]]:
    """
    Decorator to cache async function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
        cache: Cache instance to use (creates new one if not provided)

    Example:
        ```python
        @cached(ttl=60)
        async def get_user(user_id: int) -> User:
            return await db.get_user(user_id)

        @cached(ttl=300, key_prefix="product")
        async def get_product(product_id: str) -> Product:
            return await api.get_product(product_id)
        ```
    """
    _cache = cache or MemoryCache()

    def decorator(func: Callable[..., Awaitable[T]]) -> CachedFunction[T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            key = _make_cache_key(func.__name__, key_prefix, args, kwargs)

            # Check cache
            cached_value = await _cache.async_get(key)
            if cached_value is not None:
                return cached_value

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            await _cache.async_set(key, result, ttl)
            return result

        # Attach cache instance for manual control
        wrapper.cache = _cache  # type: ignore[attr-defined]
        wrapper.invalidate = lambda *a, **kw: _cache.delete(  # type: ignore[attr-defined]
            _make_cache_key(func.__name__, key_prefix, a, kw)
        )

        return wrapper  # type: ignore[return-value]

    return decorator


def _make_cache_key(func_name: str, prefix: str, args: tuple, kwargs: dict) -> str:
    """Generate a cache key from function call parameters."""
    # Create a hashable representation
    key_parts = [prefix, func_name] if prefix else [func_name]

    # Add args
    for arg in args:
        key_parts.append(_serialize_for_key(arg))

    # Add kwargs (sorted for consistency)
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={_serialize_for_key(v)}")

    key_string = ":".join(key_parts)

    # Hash if too long
    if len(key_string) > 200:
        return hashlib.sha256(key_string.encode()).hexdigest()

    return key_string


def _serialize_for_key(value: Any) -> str:
    """Serialize a value for use in cache key."""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        return hashlib.md5(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]
    except (TypeError, ValueError):
        return str(id(value))


# Global cache instance
_default_cache = MemoryCache(max_size=10000, default_ttl=300)


def get_default_cache() -> MemoryCache:
    """Get the default cache instance."""
    return _default_cache
