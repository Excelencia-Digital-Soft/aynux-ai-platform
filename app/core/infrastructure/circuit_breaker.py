"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by detecting repeated failures and temporarily
blocking requests to failing services.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failure threshold exceeded, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 3  # Successes in half-open to close
    timeout_seconds: float = 30.0  # Time before attempting recovery
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_changes: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rejected_requests": self.rejected_requests,
            "state_changes": self.state_changes,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "success_rate": self.success_rate,
        }

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Failure threshold reached, all requests rejected
    - HALF_OPEN: Testing recovery, limited requests allowed

    Example:
        ```python
        breaker = CircuitBreaker(name="external_api")

        @breaker
        async def call_external_api():
            return await http_client.get(url)

        # Or manual usage
        async with breaker:
            result = await http_client.get(url)
        ```
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitBreakerStats()
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state."""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get statistics."""
        return self._stats

    @property
    def is_available(self) -> bool:
        """Check if circuit breaker allows requests."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self._should_attempt_reset():
                return True
            return False
        # HALF_OPEN allows limited requests
        return True

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._opened_at is None:
            return True
        elapsed = time.time() - self._opened_at
        return elapsed >= self.config.timeout_seconds

    async def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self._stats.state_changes += 1

            logger.info(
                f"Circuit breaker '{self.name}' state change: {old_state.value} -> {new_state.value}",
                extra={
                    "circuit_breaker": self.name,
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "stats": self._stats.to_dict(),
                },
            )

            if new_state == CircuitState.OPEN:
                self._opened_at = time.time()
            elif new_state == CircuitState.CLOSED:
                self._opened_at = None
                self._stats.consecutive_failures = 0

    async def _record_success(self) -> None:
        """Record a successful request."""
        async with self._lock:
            self._stats.successful_requests += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to(CircuitState.CLOSED)

    async def _record_failure(self, exception: Exception) -> None:
        """Record a failed request."""
        # Check if exception is excluded
        if isinstance(exception, self.config.excluded_exceptions):
            return

        async with self._lock:
            self._stats.failed_requests += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = datetime.now()

            if self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                await self._transition_to(CircuitState.OPEN)

    async def _before_request(self) -> None:
        """Check state before allowing request."""
        async with self._lock:
            self._stats.total_requests += 1

            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to(CircuitState.HALF_OPEN)
                else:
                    self._stats.rejected_requests += 1
                    retry_after = self.config.timeout_seconds - (time.time() - (self._opened_at or 0))
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is open. Retry after {retry_after:.1f}s",
                        retry_after=retry_after,
                    )

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of the function

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original exception from function
        """
        await self._before_request()

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure(e)
            raise

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter async context manager."""
        await self._before_request()
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any) -> bool:
        """Exit async context manager."""
        if exc_val is None:
            await self._record_success()
        else:
            await self._record_failure(exc_val)
        return False  # Don't suppress exceptions

    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        """Decorator for async functions."""

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.execute(func, *args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._stats = CircuitBreakerStats()
        logger.info(f"Circuit breaker '{self.name}' reset")

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        return {
            "name": self.name,
            "state": self._state.value,
            "is_available": self.is_available,
            "stats": self._stats.to_dict(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
            },
        }


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Example:
        ```python
        registry = CircuitBreakerRegistry()
        breaker = registry.get_or_create("external_api")

        @breaker
        async def call_api():
            ...
        ```
    """

    _instance: "CircuitBreakerRegistry | None" = None
    _initialized: bool = False

    def __new__(cls) -> "CircuitBreakerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not CircuitBreakerRegistry._initialized:
            self._breakers: dict[str, CircuitBreaker] = {}
            CircuitBreakerRegistry._initialized = True

    def get_or_create(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker by name.

        Args:
            name: Circuit breaker name
            config: Configuration (only used on creation)

        Returns:
            Circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuit breakers."""
        return {name: breaker.get_status() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()


def circuit_breaker(
    name: str | None = None,
    failure_threshold: int = 5,
    success_threshold: int = 3,
    timeout_seconds: float = 30.0,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to add circuit breaker to a function.

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Failures before opening
        success_threshold: Successes to close
        timeout_seconds: Recovery timeout

    Example:
        ```python
        @circuit_breaker(name="api", failure_threshold=3)
        async def call_api():
            return await client.get(url)
        ```
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        breaker_name = name or func.__name__
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
        )
        breaker = circuit_breaker_registry.get_or_create(breaker_name, config)
        return breaker(func)

    return decorator
