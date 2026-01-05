"""LRU cache with TTL for intent results.

Extracted from IntentRouter to follow Single Responsibility Principle.
Handles all caching operations for intent analysis results.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)


class IntentCache:
    """LRU cache with TTL for intent routing results.

    Features:
    - TTL-based expiration
    - LRU eviction when max size reached
    - Cache key generation from message + context
    - Hit/miss tracking for metrics
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        """Initialize cache.

        Args:
            max_size: Maximum number of entries before LRU eviction
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._timestamps: dict[str, float] = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get_key(self, message: str, context: dict[str, Any] | None = None) -> str:
        """Generate cache key based on message and context.

        Args:
            message: User message
            context: Optional context dict

        Returns:
            MD5 hash of normalized message + relevant context
        """
        normalized_message = message.lower().strip()

        context_str = ""
        if context:
            conversation_data = context.get("conversation_data", {})
            relevant_context = {
                "language": context.get("language", "es"),
                "user_tier": context.get("customer_data", {}).get("tier", "basic"),
                "previous_agent": conversation_data.get("previous_agent"),
            }
            context_str = json.dumps(relevant_context, sort_keys=True)

        cache_input = f"{normalized_message}|{context_str}"
        return hashlib.md5(cache_input.encode()).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        """Get result from cache if available and not expired.

        Args:
            key: Cache key

        Returns:
            Cached result or None if miss/expired
        """
        current_time = time.time()

        if key not in self._cache:
            self._misses += 1
            return None

        # Check TTL
        cache_time = self._timestamps.get(key, 0)
        if current_time - cache_time > self._ttl:
            # Expired - remove from cache
            del self._cache[key]
            del self._timestamps[key]
            self._misses += 1
            return None

        # Cache hit - move to end (LRU)
        result = self._cache.pop(key)
        self._cache[key] = result
        self._hits += 1

        logger.debug(f"Cache hit for key: {key[:8]}...")
        return result

    def set(self, key: str, result: dict[str, Any]) -> None:
        """Store result in cache with LRU eviction.

        Args:
            key: Cache key
            result: Intent result to cache
        """
        current_time = time.time()

        # LRU eviction if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            del self._timestamps[oldest_key]

        self._cache[key] = result.copy()
        self._timestamps[key] = current_time

        logger.debug(f"Stored in cache: {key[:8]}... (size: {len(self._cache)})")

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        cache_size = len(self._cache)
        self._cache.clear()
        self._timestamps.clear()
        logger.info(f"Intent cache cleared - removed {cache_size} entries")
        return cache_size

    def clear_for_message(self, message: str) -> bool:
        """Clear cache for a specific message.

        Args:
            message: Message to clear cache for

        Returns:
            True if entry was found and cleared, False otherwise
        """
        cache_key = self.get_key(message, {})
        if cache_key in self._cache:
            del self._cache[cache_key]
            del self._timestamps[cache_key]
            logger.info(f"Cleared cache for message: '{message}' (key: {cache_key[:8]}...)")
            return True
        logger.info(f"No cache entry found for message: '{message}'")
        return False

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache size, hit rate, and other stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / max(total_requests, 1)) * 100

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self._max_size,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "cache_ttl": self._ttl,
        }

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

    @property
    def hits(self) -> int:
        """Total cache hits."""
        return self._hits

    @property
    def misses(self) -> int:
        """Total cache misses."""
        return self._misses
