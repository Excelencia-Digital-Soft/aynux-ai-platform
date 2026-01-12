"""
Pharmacy Rate Limiter Service

Redis-backed sliding window rate limiter for pharmacy chatbot.
Implements per-user rate limiting as defined in docs/pharmacy_flujo_mejorado_v2.md CASO 0.

Rate Limits:
- messages_per_minute: 10 messages/minute
- messages_per_hour: 100 messages/hour
- plex_queries_per_hour: 20 PLEX API queries/hour
- payment_links_per_day: 5 payment links/day
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RateLimitType(str, Enum):
    """Types of rate limits supported."""

    MESSAGES_PER_MINUTE = "messages_per_minute"
    MESSAGES_PER_HOUR = "messages_per_hour"
    PLEX_QUERIES_PER_HOUR = "plex_queries_per_hour"
    PAYMENT_LINKS_PER_DAY = "payment_links_per_day"


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit type."""

    limit: int
    window_seconds: int
    redis_key_suffix: str


# Rate limit configurations as per docs/pharmacy_flujo_mejorado_v2.md
RATE_LIMIT_CONFIGS: dict[RateLimitType, RateLimitConfig] = {
    RateLimitType.MESSAGES_PER_MINUTE: RateLimitConfig(
        limit=10,
        window_seconds=60,
        redis_key_suffix="min",
    ),
    RateLimitType.MESSAGES_PER_HOUR: RateLimitConfig(
        limit=100,
        window_seconds=3600,
        redis_key_suffix="hour",
    ),
    RateLimitType.PLEX_QUERIES_PER_HOUR: RateLimitConfig(
        limit=20,
        window_seconds=3600,
        redis_key_suffix="plex",
    ),
    RateLimitType.PAYMENT_LINKS_PER_DAY: RateLimitConfig(
        limit=5,
        window_seconds=86400,
        redis_key_suffix="links",
    ),
}


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    limit_type: RateLimitType | None = None
    current_count: int = 0
    limit: int = 0
    retry_after_seconds: int | None = None

    @property
    def reason(self) -> str | None:
        """Human-readable reason for rate limiting."""
        if self.allowed:
            return None

        if self.limit_type == RateLimitType.MESSAGES_PER_MINUTE:
            return "Demasiados mensajes por minuto"
        elif self.limit_type == RateLimitType.MESSAGES_PER_HOUR:
            return "Demasiados mensajes por hora"
        elif self.limit_type == RateLimitType.PLEX_QUERIES_PER_HOUR:
            return "Demasiadas consultas al sistema"
        elif self.limit_type == RateLimitType.PAYMENT_LINKS_PER_DAY:
            return "Demasiados links de pago generados hoy"
        return "Limite de uso excedido"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for state merging."""
        return {
            "rate_limited": not self.allowed,
            "rate_limit_reason": self.reason,
        }


class PharmacyRateLimiter:
    """
    Redis-backed sliding window rate limiter for pharmacy chatbot.

    Uses Redis INCR with EXPIRE for simple, reliable rate limiting.
    Falls back to allowing requests if Redis is unavailable.

    Usage:
        limiter = PharmacyRateLimiter()
        result = await limiter.check_message_rate(phone_number)
        if not result.allowed:
            # Handle rate limit exceeded
    """

    KEY_PREFIX = "pharmacy:rate"

    def __init__(self) -> None:
        """Initialize rate limiter."""
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Get async Redis client lazily."""
        if self._redis is None:
            try:
                from app.integrations.databases.redis import get_async_redis_client

                self._redis = await get_async_redis_client()
            except Exception as e:
                logger.warning(f"Redis unavailable for rate limiting: {e}")
                return None
        return self._redis

    def _build_key(self, phone: str, limit_type: RateLimitType) -> str:
        """Build Redis key for rate limit counter."""
        config = RATE_LIMIT_CONFIGS[limit_type]
        return f"{self.KEY_PREFIX}:{phone}:{config.redis_key_suffix}"

    async def _check_limit(
        self,
        phone: str,
        limit_type: RateLimitType,
    ) -> RateLimitResult:
        """
        Check a specific rate limit.

        Args:
            phone: User's phone number
            limit_type: Type of rate limit to check

        Returns:
            RateLimitResult with allowed status and details
        """
        redis = await self._get_redis()
        if redis is None:
            # Fail open if Redis is unavailable
            return RateLimitResult(allowed=True)

        config = RATE_LIMIT_CONFIGS[limit_type]
        key = self._build_key(phone, limit_type)

        try:
            # Get current count
            current = await redis.get(key)
            current_count = int(current) if current else 0

            if current_count >= config.limit:
                # Rate limit exceeded
                ttl = await redis.ttl(key)
                return RateLimitResult(
                    allowed=False,
                    limit_type=limit_type,
                    current_count=current_count,
                    limit=config.limit,
                    retry_after_seconds=max(0, ttl) if ttl > 0 else config.window_seconds,
                )

            return RateLimitResult(
                allowed=True,
                limit_type=limit_type,
                current_count=current_count,
                limit=config.limit,
            )
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open on errors
            return RateLimitResult(allowed=True)

    async def _increment_counter(
        self,
        phone: str,
        limit_type: RateLimitType,
    ) -> None:
        """
        Increment rate limit counter.

        Args:
            phone: User's phone number
            limit_type: Type of rate limit to increment
        """
        redis = await self._get_redis()
        if redis is None:
            return

        config = RATE_LIMIT_CONFIGS[limit_type]
        key = self._build_key(phone, limit_type)

        try:
            # Increment counter
            new_count = await redis.incr(key)

            # Set expiry on first increment
            if new_count == 1:
                await redis.expire(key, config.window_seconds)
        except Exception as e:
            logger.error(f"Rate limit increment failed: {e}")

    async def check_message_rate(self, phone: str) -> RateLimitResult:
        """
        Check if user can send a message.

        Checks both per-minute and per-hour limits.

        Args:
            phone: User's phone number

        Returns:
            RateLimitResult indicating if message is allowed
        """
        # Check per-minute limit first (more restrictive)
        result = await self._check_limit(phone, RateLimitType.MESSAGES_PER_MINUTE)
        if not result.allowed:
            return result

        # Then check per-hour limit
        result = await self._check_limit(phone, RateLimitType.MESSAGES_PER_HOUR)
        if not result.allowed:
            return result

        return RateLimitResult(allowed=True)

    async def record_message(self, phone: str) -> None:
        """
        Record a message for rate limiting.

        Call this after message is processed to increment counters.

        Args:
            phone: User's phone number
        """
        await self._increment_counter(phone, RateLimitType.MESSAGES_PER_MINUTE)
        await self._increment_counter(phone, RateLimitType.MESSAGES_PER_HOUR)

    async def check_plex_query_rate(self, phone: str) -> RateLimitResult:
        """
        Check if user can make a PLEX API query.

        Args:
            phone: User's phone number

        Returns:
            RateLimitResult indicating if query is allowed
        """
        return await self._check_limit(phone, RateLimitType.PLEX_QUERIES_PER_HOUR)

    async def record_plex_query(self, phone: str) -> None:
        """
        Record a PLEX API query for rate limiting.

        Args:
            phone: User's phone number
        """
        await self._increment_counter(phone, RateLimitType.PLEX_QUERIES_PER_HOUR)

    async def check_payment_link_rate(self, phone: str) -> RateLimitResult:
        """
        Check if user can generate a payment link.

        Args:
            phone: User's phone number

        Returns:
            RateLimitResult indicating if link generation is allowed
        """
        return await self._check_limit(phone, RateLimitType.PAYMENT_LINKS_PER_DAY)

    async def record_payment_link(self, phone: str) -> None:
        """
        Record a payment link generation for rate limiting.

        Args:
            phone: User's phone number
        """
        await self._increment_counter(phone, RateLimitType.PAYMENT_LINKS_PER_DAY)

    async def get_all_limits(self, phone: str) -> dict[str, dict[str, Any]]:
        """
        Get current status of all rate limits for a phone.

        Args:
            phone: User's phone number

        Returns:
            Dictionary with status of all rate limits
        """
        result = {}
        for limit_type in RateLimitType:
            check = await self._check_limit(phone, limit_type)
            result[limit_type.value] = {
                "current": check.current_count,
                "limit": check.limit,
                "allowed": check.allowed,
                "retry_after": check.retry_after_seconds,
            }
        return result

    async def reset_limits(self, phone: str) -> None:
        """
        Reset all rate limits for a phone (admin operation).

        Args:
            phone: User's phone number
        """
        redis = await self._get_redis()
        if redis is None:
            return

        for limit_type in RateLimitType:
            key = self._build_key(phone, limit_type)
            try:
                await redis.delete(key)
            except Exception as e:
                logger.error(f"Failed to reset rate limit {key}: {e}")


# Singleton instance
_rate_limiter: PharmacyRateLimiter | None = None


def get_rate_limiter() -> PharmacyRateLimiter:
    """
    Get singleton rate limiter instance.

    Returns:
        PharmacyRateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = PharmacyRateLimiter()
    return _rate_limiter


__all__ = [
    "PharmacyRateLimiter",
    "RateLimitResult",
    "RateLimitType",
    "RateLimitConfig",
    "get_rate_limiter",
]
