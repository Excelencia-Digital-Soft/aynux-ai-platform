"""
Monitoring and Observability Infrastructure

Provides metrics collection, health checks, and observability utilities.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MetricValue:
    """A single metric measurement."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """
    Simple metrics collection for application monitoring.

    Collects counters, gauges, and histograms for tracking application behavior.

    Example:
        ```python
        metrics = MetricsCollector()

        # Counter
        metrics.increment("requests_total", labels={"endpoint": "/api/chat"})

        # Gauge
        metrics.set_gauge("active_connections", 42)

        # Histogram (timing)
        with metrics.timer("request_duration_seconds"):
            await process_request()
        ```
    """

    def __init__(self):
        """Initialize metrics collector."""
        self._counters: dict[str, dict[str, float]] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """
        Increment a counter.

        Args:
            name: Metric name
            value: Amount to increment (default 1)
            labels: Optional labels for the metric
        """
        key = self._make_key(name, labels)
        if name not in self._counters:
            self._counters[name] = {}
        if key not in self._counters[name]:
            self._counters[name][key] = 0
        self._counters[name][key] += value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Set a gauge value.

        Args:
            name: Metric name
            value: Value to set
            labels: Optional labels for the metric
        """
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """
        Record an observation for a histogram.

        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels for the metric
        """
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def timer(self, name: str, labels: dict[str, str] | None = None) -> "Timer":
        """
        Create a timer context manager.

        Args:
            name: Metric name for the timer
            labels: Optional labels

        Returns:
            Timer context manager
        """
        return Timer(self, name, labels)

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(name, {}).get(key, 0)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key)

    def get_histogram_stats(self, name: str, labels: dict[str, str] | None = None) -> dict[str, float] | None:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key)
        if not values:
            return None

        sorted_values = sorted(values)
        count = len(values)
        return {
            "count": count,
            "sum": sum(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(values) / count,
            "p50": sorted_values[count // 2],
            "p90": sorted_values[int(count * 0.9)] if count >= 10 else sorted_values[-1],
            "p99": sorted_values[int(count * 0.99)] if count >= 100 else sorted_values[-1],
        }

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as a dictionary."""
        return {
            "counters": self._counters,
            "gauges": self._gauges,
            "histograms": {k: self.get_histogram_stats(k.split("{")[0]) for k in self._histograms},
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()

    def _make_key(self, name: str, labels: dict[str, str] | None) -> str:
        """Create a unique key for metric + labels."""
        if not labels:
            return name
        labels_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{labels_str}}}"


class Timer:
    """Context manager for timing operations."""

    def __init__(self, collector: MetricsCollector, name: str, labels: dict[str, str] | None = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time: float | None = None

    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        if self.start_time:
            duration = time.perf_counter() - self.start_time
            self.collector.observe(self.name, duration, self.labels)

    async def __aenter__(self) -> "Timer":
        return self.__enter__()

    async def __aexit__(self, *args: Any) -> None:
        return self.__exit__(*args)


class HealthChecker:
    """
    Health check manager for application components.

    Example:
        ```python
        health = HealthChecker()

        @health.register("database")
        async def check_database():
            await db.execute("SELECT 1")
            return True

        @health.register("redis", critical=True)
        async def check_redis():
            await redis.ping()
            return True

        results = await health.run_all()
        ```
    """

    def __init__(self):
        """Initialize health checker."""
        self._checks: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        critical: bool = False,
        timeout_seconds: float = 5.0,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Register a health check function.

        Args:
            name: Name of the health check
            critical: Whether this check failing makes system unhealthy
            timeout_seconds: Timeout for the check

        Returns:
            Decorator
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._checks[name] = {
                "func": func,
                "critical": critical,
                "timeout": timeout_seconds,
            }
            return func

        return decorator

    def add_check(
        self,
        name: str,
        func: Callable[..., Any],
        critical: bool = False,
        timeout_seconds: float = 5.0,
    ) -> None:
        """
        Add a health check function directly.

        Args:
            name: Name of the health check
            func: Check function
            critical: Whether this check is critical
            timeout_seconds: Timeout for the check
        """
        self._checks[name] = {
            "func": func,
            "critical": critical,
            "timeout": timeout_seconds,
        }

    async def run_check(self, name: str) -> HealthCheckResult:
        """
        Run a single health check.

        Args:
            name: Name of the check to run

        Returns:
            Health check result
        """
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Health check '{name}' not found",
            )

        check = self._checks[name]
        start_time = time.perf_counter()

        try:
            result = await asyncio.wait_for(
                check["func"]() if asyncio.iscoroutinefunction(check["func"]) else asyncio.to_thread(check["func"]),
                timeout=check["timeout"],
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            if isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                return HealthCheckResult(name=name, status=status, latency_ms=latency_ms)
            elif isinstance(result, dict):
                status = result.get("status", HealthStatus.HEALTHY)
                if isinstance(status, str):
                    status = HealthStatus(status)
                return HealthCheckResult(
                    name=name,
                    status=status,
                    latency_ms=latency_ms,
                    message=result.get("message"),
                    details=result.get("details", {}),
                )
            else:
                return HealthCheckResult(name=name, status=HealthStatus.HEALTHY, latency_ms=latency_ms)

        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=f"Health check timed out after {check['timeout']}s",
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency_ms,
                message=str(e),
            )

    async def run_all(self) -> dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dictionary with overall status and individual results
        """
        results = await asyncio.gather(*[self.run_check(name) for name in self._checks])

        overall_status = HealthStatus.HEALTHY
        has_degraded = False

        for result in results:
            check_config = self._checks.get(result.name, {})
            if result.status == HealthStatus.UNHEALTHY:
                if check_config.get("critical", False):
                    overall_status = HealthStatus.UNHEALTHY
                else:
                    has_degraded = True
            elif result.status == HealthStatus.DEGRADED:
                has_degraded = True

        if overall_status == HealthStatus.HEALTHY and has_degraded:
            overall_status = HealthStatus.DEGRADED

        return {
            "status": overall_status.value,
            "checks": {r.name: r.to_dict() for r in results},
            "timestamp": datetime.now().isoformat(),
        }


def timed(
    metric_name: str | None = None,
    labels: dict[str, str] | None = None,
    collector: MetricsCollector | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to time function execution.

    Args:
        metric_name: Name for the metric (defaults to function name)
        labels: Additional labels
        collector: Metrics collector to use

    Example:
        ```python
        @timed("api_request_duration")
        async def handle_request():
            ...
        ```
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        name = metric_name or f"{func.__name__}_duration_seconds"

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            start = time.perf_counter()
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if collector:
                    collector.observe(name, duration, labels)
                logger.debug(f"{name}: {duration:.4f}s", extra={"metric": name, "duration": duration})

        return wrapper

    return decorator


# Global instances
metrics_collector = MetricsCollector()
health_checker = HealthChecker()
