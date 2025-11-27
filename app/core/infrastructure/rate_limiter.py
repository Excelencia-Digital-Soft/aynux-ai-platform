"""
Rate Limiter Infrastructure

Token bucket and sliding window rate limiting implementations.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(message)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 10.0
    burst_size: int = 20
    window_size_seconds: float = 1.0


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.

    Allows burst traffic up to bucket capacity, then limits to steady rate.

    Example:
        ```python
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=20)

        if limiter.acquire():
            # Process request
            pass
        else:
            # Rate limited
            pass
        ```
    """

    def __init__(self, rate: float, capacity: int):
        """
        Initialize token bucket.

        Args:
            rate: Tokens per second
            capacity: Maximum bucket capacity (burst size)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens acquired, False otherwise
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Thread-safe async token acquisition."""
        async with self._lock:
            return self.acquire(tokens)

    async def wait_and_acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Wait until tokens available or timeout.

        Args:
            tokens: Number of tokens needed
            timeout: Maximum wait time in seconds

        Returns:
            True if acquired, False if timeout
        """
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            if await self.acquire_async(tokens):
                return True

            # Calculate wait time for tokens
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(min(wait_time, 0.1))

        return False

    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self.tokens

    def time_until_available(self, tokens: int = 1) -> float:
        """Get time until tokens are available."""
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        return (tokens - self.tokens) / self.rate


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.

    Tracks requests in a sliding time window for more accurate rate limiting.

    Example:
        ```python
        limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60.0)

        if limiter.is_allowed():
            # Process request
            pass
        ```
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """
        Initialize sliding window limiter.

        Args:
            max_requests: Maximum requests in window
            window_seconds: Window size in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[float] = []
        self._lock = asyncio.Lock()

    def _clean_old_requests(self) -> None:
        """Remove requests outside the window."""
        cutoff = time.monotonic() - self.window_seconds
        self.requests = [r for r in self.requests if r > cutoff]

    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        self._clean_old_requests()
        return len(self.requests) < self.max_requests

    def record_request(self) -> bool:
        """
        Record a request if allowed.

        Returns:
            True if request recorded, False if rate limited
        """
        self._clean_old_requests()

        if len(self.requests) >= self.max_requests:
            return False

        self.requests.append(time.monotonic())
        return True

    async def record_request_async(self) -> bool:
        """Thread-safe async request recording."""
        async with self._lock:
            return self.record_request()

    @property
    def current_count(self) -> int:
        """Get current request count in window."""
        self._clean_old_requests()
        return len(self.requests)

    @property
    def remaining(self) -> int:
        """Get remaining requests allowed."""
        return max(0, self.max_requests - self.current_count)

    def time_until_reset(self) -> float:
        """Get time until oldest request expires."""
        self._clean_old_requests()
        if not self.requests:
            return 0.0
        return max(0.0, self.requests[0] + self.window_seconds - time.monotonic())


class RateLimiterRegistry:
    """Registry for managing multiple rate limiters."""

    def __init__(self):
        """Initialize registry."""
        self._limiters: dict[str, TokenBucketRateLimiter | SlidingWindowRateLimiter] = {}
        self._configs: dict[str, RateLimitConfig] = {}

    def register_bucket(
        self,
        name: str,
        rate: float,
        capacity: int,
    ) -> TokenBucketRateLimiter:
        """Register a token bucket limiter."""
        limiter = TokenBucketRateLimiter(rate=rate, capacity=capacity)
        self._limiters[name] = limiter
        return limiter

    def register_window(
        self,
        name: str,
        max_requests: int,
        window_seconds: float,
    ) -> SlidingWindowRateLimiter:
        """Register a sliding window limiter."""
        limiter = SlidingWindowRateLimiter(
            max_requests=max_requests,
            window_seconds=window_seconds,
        )
        self._limiters[name] = limiter
        return limiter

    def get(self, name: str) -> TokenBucketRateLimiter | SlidingWindowRateLimiter | None:
        """Get limiter by name."""
        return self._limiters.get(name)

    def is_allowed(self, name: str) -> bool:
        """Check if request is allowed for named limiter."""
        limiter = self._limiters.get(name)
        if not limiter:
            return True

        if isinstance(limiter, TokenBucketRateLimiter):
            return limiter.acquire()
        else:
            return limiter.record_request()

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all limiters."""
        stats = {}

        for name, limiter in self._limiters.items():
            if isinstance(limiter, TokenBucketRateLimiter):
                stats[name] = {
                    "type": "token_bucket",
                    "available_tokens": limiter.available_tokens,
                    "rate": limiter.rate,
                    "capacity": limiter.capacity,
                }
            else:
                stats[name] = {
                    "type": "sliding_window",
                    "current_count": limiter.current_count,
                    "remaining": limiter.remaining,
                    "max_requests": limiter.max_requests,
                    "window_seconds": limiter.window_seconds,
                }

        return stats


# Global registry instance
_rate_limiter_registry = RateLimiterRegistry()


def get_rate_limiter_registry() -> RateLimiterRegistry:
    """Get the global rate limiter registry."""
    return _rate_limiter_registry


def rate_limit(
    name: str | None = None,
    rate: float = 10.0,
    capacity: int = 20,
    raise_on_limit: bool = True,
):
    """
    Decorator for rate limiting functions.

    Args:
        name: Limiter name (defaults to function name)
        rate: Tokens per second
        capacity: Burst capacity
        raise_on_limit: Raise exception when limited

    Example:
        ```python
        @rate_limit(rate=5.0, capacity=10)
        async def api_call():
            pass
        ```
    """

    def decorator(func: Callable) -> Callable:
        limiter_name = name or func.__name__
        registry = get_rate_limiter_registry()
        limiter = registry.register_bucket(limiter_name, rate, capacity)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not await limiter.acquire_async():
                if raise_on_limit:
                    retry_after = limiter.time_until_available()
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for {limiter_name}",
                        retry_after=retry_after,
                    )
                return None
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not limiter.acquire():
                if raise_on_limit:
                    retry_after = limiter.time_until_available()
                    raise RateLimitExceeded(
                        f"Rate limit exceeded for {limiter_name}",
                        retry_after=retry_after,
                    )
                return None
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
