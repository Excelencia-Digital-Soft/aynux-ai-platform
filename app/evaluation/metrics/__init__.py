"""
Metrics Module.

Comprehensive metrics collection, analysis, and reporting for LangSmith evaluation.

Components:
- RunAnalyzer: Analyzes LangSmith runs to extract metric values
- MetricsCollector: Collects metrics by category (routing, quality, performance, business)
- MetricsReporter: Generates dashboards and system-level reports
- AynuxMetrics: Facade for backward compatibility
"""

from app.evaluation.metrics.analyzer import MetricValue, RunAnalyzer
from app.evaluation.metrics.collector import MetricsCollector
from app.evaluation.metrics.models import MetricsSummary, MetricTrend, MetricType
from app.evaluation.metrics.reporter import MetricsReporter

# Backward-compatible facade
_metrics_instance: "AynuxMetrics | None" = None


class AynuxMetrics:
    """
    Comprehensive metrics collection and analysis for Aynux.

    Facade that delegates to specialized components:
    - MetricsCollector: Data collection from LangSmith
    - MetricsReporter: Dashboard and report generation
    """

    def __init__(self):
        self._collector = MetricsCollector()
        self._reporter = MetricsReporter(self._collector)

        # Expose thresholds for compatibility
        self.thresholds = self._collector.thresholds

    async def collect_routing_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Delegate to collector."""
        return await self._collector.collect_routing_metrics(
            time_period_hours, project_name
        )

    async def collect_quality_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Delegate to collector."""
        return await self._collector.collect_quality_metrics(
            time_period_hours, project_name
        )

    async def collect_performance_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Delegate to collector."""
        return await self._collector.collect_performance_metrics(
            time_period_hours, project_name
        )

    async def collect_business_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Delegate to collector."""
        return await self._collector.collect_business_metrics(
            time_period_hours, project_name
        )

    async def get_comprehensive_dashboard(
        self, time_period_hours: int = 24
    ) -> dict:
        """Delegate to reporter."""
        return await self._reporter.get_comprehensive_dashboard(time_period_hours)


def get_metrics_collector() -> AynuxMetrics:
    """Get a singleton instance of AynuxMetrics."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = AynuxMetrics()
    return _metrics_instance


__all__ = [
    # Models
    "MetricType",
    "MetricTrend",
    "MetricValue",
    "MetricsSummary",
    # Components
    "RunAnalyzer",
    "MetricsCollector",
    "MetricsReporter",
    # Facade
    "AynuxMetrics",
    "get_metrics_collector",
]
