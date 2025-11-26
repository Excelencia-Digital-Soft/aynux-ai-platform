"""
Retry Pattern Implementation

Provides configurable retry logic with exponential backoff and jitter
for transient failure recovery.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Sequence, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to delays
    jitter_factor: float = 0.1  # 10% jitter
    retryable_exceptions: tuple = (Exception,)
    non_retryable_exceptions: tuple = ()


@dataclass
class RetryStats:
    """Statistics for retry operations."""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_delay_seconds: float = 0.0
    last_exception: Exception | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "total_delay_seconds": self.total_delay_seconds,
            "success_rate": self.success_rate,
            "last_exception": str(self.last_exception) if self.last_exception else None,
        }

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_attempts == 0:
            return 1.0
        return self.successful_attempts / self.total_attempts


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(self, message: str, last_exception: Exception | None = None, attempts: int = 0):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


class Retryer:
    """
    Configurable retry mechanism with exponential backoff.

    Features:
    - Exponential backoff with jitter
    - Configurable retry conditions
    - Statistics tracking
    - Async and sync support

    Example:
        ```python
        retryer = Retryer(max_attempts=3, initial_delay=1.0)

        @retryer
        async def unreliable_operation():
            return await external_api.call()

        # Or manual usage
        result = await retryer.execute(unreliable_operation)
        ```
    """

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple | None = None,
        non_retryable_exceptions: tuple | None = None,
        on_retry: Callable[[int, Exception, float], None] | None = None,
    ):
        """
        Initialize retryer.

        Args:
            max_attempts: Maximum number of attempts
            initial_delay: Initial delay between retries
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter
            retryable_exceptions: Exceptions that trigger retry
            non_retryable_exceptions: Exceptions that never retry
            on_retry: Callback called before each retry
        """
        self.config = RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            retryable_exceptions=retryable_exceptions or (Exception,),
            non_retryable_exceptions=non_retryable_exceptions or (),
        )
        self.on_retry = on_retry
        self._stats = RetryStats()

    @property
    def stats(self) -> RetryStats:
        """Get retry statistics."""
        return self._stats

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.

        Uses exponential backoff with optional jitter.
        """
        delay = self.config.initial_delay * (self.config.exponential_base ** (attempt - 1))
        delay = min(delay, self.config.max_delay)

        if self.config.jitter:
            jitter_range = delay * self.config.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    def _should_retry(self, exception: Exception) -> bool:
        """Check if the exception should trigger a retry."""
        # Never retry non-retryable exceptions
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False

        # Check if it's a retryable exception
        return isinstance(exception, self.config.retryable_exceptions)

    async def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of the function

        Raises:
            RetryExhaustedError: If all retries exhausted
            Exception: Non-retryable exception
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.config.max_attempts + 1):
            self._stats.total_attempts += 1

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                self._stats.successful_attempts += 1
                return result

            except Exception as e:
                last_exception = e
                self._stats.last_exception = e

                if not self._should_retry(e):
                    self._stats.failed_attempts += 1
                    raise

                if attempt >= self.config.max_attempts:
                    self._stats.failed_attempts += 1
                    raise RetryExhaustedError(
                        f"All {self.config.max_attempts} retry attempts exhausted",
                        last_exception=e,
                        attempts=attempt,
                    ) from e

                delay = self._calculate_delay(attempt)
                self._stats.total_delay_seconds += delay

                logger.warning(
                    f"Retry attempt {attempt}/{self.config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s",
                    extra={
                        "attempt": attempt,
                        "max_attempts": self.config.max_attempts,
                        "delay": delay,
                        "exception": str(e),
                    },
                )

                if self.on_retry:
                    self.on_retry(attempt, e, delay)

                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        raise RetryExhaustedError(
            f"Retry logic error after {self.config.max_attempts} attempts",
            last_exception=last_exception,
            attempts=self.config.max_attempts,
        )

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for functions."""

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await self.execute(func, *args, **kwargs)

        return wrapper

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = RetryStats()


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple | None = None,
    non_retryable_exceptions: tuple | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add retry logic to a function.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        retryable_exceptions: Exceptions that trigger retry
        non_retryable_exceptions: Exceptions that never retry

    Example:
        ```python
        @retry(max_attempts=3, initial_delay=1.0)
        async def unreliable_operation():
            return await external_api.call()

        @retry(
            max_attempts=5,
            retryable_exceptions=(ConnectionError, TimeoutError),
            non_retryable_exceptions=(ValueError,)
        )
        async def network_call():
            return await http_client.get(url)
        ```
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        retryer = Retryer(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            retryable_exceptions=retryable_exceptions,
            non_retryable_exceptions=non_retryable_exceptions,
        )
        return retryer(func)

    return decorator


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    retryable_exceptions: tuple | None = None,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function with retry logic (one-off usage).

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_attempts: Maximum retry attempts
        initial_delay: Initial delay between retries
        retryable_exceptions: Exceptions that trigger retry
        **kwargs: Keyword arguments for func

    Returns:
        Result of the function

    Example:
        ```python
        result = await retry_async(
            client.get,
            "https://api.example.com",
            max_attempts=3,
            retryable_exceptions=(ConnectionError,)
        )
        ```
    """
    retryer = Retryer(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        retryable_exceptions=retryable_exceptions,
    )
    return await retryer.execute(func, *args, **kwargs)


class RetryWithFallback:
    """
    Retry with fallback to alternative function.

    Example:
        ```python
        retry_fallback = RetryWithFallback(
            primary=call_api_v2,
            fallback=call_api_v1,
            max_attempts=3
        )
        result = await retry_fallback.execute()
        ```
    """

    def __init__(
        self,
        primary: Callable[..., Any],
        fallback: Callable[..., Any],
        max_attempts: int = 3,
        initial_delay: float = 1.0,
    ):
        """
        Initialize retry with fallback.

        Args:
            primary: Primary function to try
            fallback: Fallback function if primary fails
            max_attempts: Max attempts for primary
            initial_delay: Delay between retries
        """
        self.primary = primary
        self.fallback = fallback
        self.retryer = Retryer(max_attempts=max_attempts, initial_delay=initial_delay)

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute primary with fallback."""
        try:
            return await self.retryer.execute(self.primary, *args, **kwargs)
        except RetryExhaustedError:
            logger.warning("Primary function failed after all retries, using fallback")
            if asyncio.iscoroutinefunction(self.fallback):
                return await self.fallback(*args, **kwargs)
            return self.fallback(*args, **kwargs)
