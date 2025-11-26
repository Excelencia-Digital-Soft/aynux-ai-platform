"""
Core Infrastructure Module

Provides cross-cutting infrastructure patterns for fault tolerance and observability.

Components:
- Circuit Breaker: Prevents cascading failures
- Retry: Configurable retry with exponential backoff
- Monitoring: Metrics collection and health checks
- Rate Limiter: Request rate limiting
"""

from app.core.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitState,
    circuit_breaker,
    circuit_breaker_registry,
)
from app.core.infrastructure.monitoring import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    MetricsCollector,
    Timer,
    health_checker,
    metrics_collector,
    timed,
)
from app.core.infrastructure.retry import (
    Retryer,
    RetryConfig,
    RetryExhaustedError,
    RetryStats,
    RetryWithFallback,
    retry,
    retry_async,
)

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitBreakerRegistry",
    "CircuitBreakerStats",
    "CircuitState",
    "circuit_breaker",
    "circuit_breaker_registry",
    # Retry
    "Retryer",
    "RetryConfig",
    "RetryExhaustedError",
    "RetryStats",
    "RetryWithFallback",
    "retry",
    "retry_async",
    # Monitoring
    "HealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    "MetricsCollector",
    "Timer",
    "health_checker",
    "metrics_collector",
    "timed",
]
