# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: Resilience patterns for external API calls
# ============================================================================
"""Resilience patterns for HCWeb SOAP client.

Provides circuit breaker and retry patterns without external dependencies.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Number of failures before opening circuit.
        recovery_timeout: Seconds to wait before testing recovery.
        success_threshold: Successes needed in half-open to close.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2


@dataclass
class CircuitBreakerState:
    """Internal state for circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """Simple circuit breaker implementation.

    Prevents cascading failures by temporarily blocking requests
    when a service is failing.

    Example:
        >>> breaker = CircuitBreaker()
        >>> result = await breaker.call(async_function, arg1, arg2)

    States:
        - CLOSED: Normal operation, requests pass through
        - OPEN: Service failing, requests rejected immediately
        - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        """Initialize circuit breaker.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state.state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        return self._state.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (allowing requests)."""
        return self._state.state == CircuitState.CLOSED

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result if successful.

        Raises:
            CircuitOpenError: If circuit is open.
            Exception: Original exception if circuit allows.
        """
        async with self._lock:
            await self._check_state()

            if self._state.state == CircuitState.OPEN:
                raise CircuitOpenError(f"Circuit breaker is open. " f"Recovery in {self._time_until_recovery():.1f}s")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    async def _check_state(self) -> None:
        """Check and potentially transition state."""
        if self._state.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            elapsed = time.time() - self._state.last_failure_time
            if elapsed >= self._config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info("Circuit breaker transitioning to HALF_OPEN")

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1
                if self._state.success_count >= self._config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    logger.info("Circuit breaker CLOSED (service recovered)")
            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._state.failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._state.failure_count += 1
            self._state.last_failure_time = time.time()

            if self._state.state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens circuit
                self._transition_to(CircuitState.OPEN)
                logger.warning("Circuit breaker OPEN (failure during recovery)")

            elif self._state.state == CircuitState.CLOSED:
                if self._state.failure_count >= self._config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(f"Circuit breaker OPEN after {self._state.failure_count} failures")

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to new state."""
        self._state.state = new_state
        self._state.last_state_change = time.time()
        if new_state == CircuitState.HALF_OPEN:
            self._state.success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._state.failure_count = 0
            self._state.success_count = 0

    def _time_until_recovery(self) -> float:
        """Calculate seconds until recovery attempt."""
        elapsed = time.time() - self._state.last_failure_time
        return max(0, self._config.recovery_timeout - elapsed)

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitBreakerState()
        logger.info("Circuit breaker reset to CLOSED")


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


# ============================================================================
# Input Validation
# ============================================================================


class ValidationError(Exception):
    """Raised when input validation fails."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"Validation error in '{field}': {message}")


def validate_required(value: Any, field_name: str) -> None:
    """Validate that a value is not empty.

    Args:
        value: Value to validate.
        field_name: Field name for error message.

    Raises:
        ValidationError: If value is empty.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(field_name, "Field is required")


def validate_dni(dni: str) -> str:
    """Validate and normalize DNI.

    Args:
        dni: DNI to validate.

    Returns:
        Normalized DNI (digits only).

    Raises:
        ValidationError: If DNI is invalid.
    """
    if not dni:
        raise ValidationError("dni", "DNI is required")

    # Extract digits only
    normalized = "".join(c for c in dni if c.isdigit())

    if not normalized:
        raise ValidationError("dni", "DNI must contain digits")

    if len(normalized) < 6 or len(normalized) > 11:
        raise ValidationError("dni", "DNI must be 6-11 digits")

    return normalized


def validate_phone(phone: str) -> str:
    """Validate and normalize phone number.

    Args:
        phone: Phone number to validate.

    Returns:
        Normalized phone (digits only).

    Raises:
        ValidationError: If phone is invalid.
    """
    if not phone:
        raise ValidationError("phone", "Phone is required")

    # Extract digits only
    normalized = "".join(c for c in phone if c.isdigit())

    if len(normalized) < 8:
        raise ValidationError("phone", "Phone must be at least 8 digits")

    return normalized


def validate_id(value: str, field_name: str) -> str:
    """Validate an ID field.

    Args:
        value: ID value.
        field_name: Field name for error message.

    Returns:
        Validated ID.

    Raises:
        ValidationError: If ID is invalid.
    """
    if not value or not value.strip():
        raise ValidationError(field_name, f"{field_name} is required")

    return value.strip()
