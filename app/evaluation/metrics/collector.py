"""
Metrics Collector for LangSmith.

Collects metrics from LangSmith runs by category.
"""

import logging
from datetime import datetime, timedelta

from app.config.langsmith_config import get_tracer
from app.evaluation.metrics.analyzer import MetricValue, RunAnalyzer
from app.evaluation.metrics.models import MetricsSummary, MetricTrend, MetricType

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects metrics from LangSmith runs.

    Responsibilities:
    - Fetch runs from LangSmith API
    - Coordinate with RunAnalyzer for data extraction
    - Create MetricsSummary objects
    - Manage metric thresholds
    """

    def __init__(self):
        self.tracer = get_tracer()
        self.client = self.tracer.client if self.tracer.client else None
        self._analyzer = RunAnalyzer()

        self.thresholds = {
            # Routing metrics
            "intent_routing_accuracy": {
                "warning": 0.85,
                "critical": 0.75,
                "target": 0.95,
            },
            "agent_selection_accuracy": {
                "warning": 0.80,
                "critical": 0.70,
                "target": 0.90,
            },
            "routing_confidence": {
                "warning": 0.70,
                "critical": 0.60,
                "target": 0.85,
            },
            # Quality metrics
            "response_quality_score": {
                "warning": 0.75,
                "critical": 0.65,
                "target": 0.85,
            },
            "task_completion_rate": {
                "warning": 0.80,
                "critical": 0.70,
                "target": 0.90,
            },
            "conversation_success_rate": {
                "warning": 0.85,
                "critical": 0.75,
                "target": 0.92,
            },
            # Performance metrics
            "average_response_time": {
                "warning": 3.0,
                "critical": 5.0,
                "target": 2.0,
            },
            "p95_response_time": {
                "warning": 5.0,
                "critical": 8.0,
                "target": 3.0,
            },
            "error_rate": {
                "warning": 0.05,
                "critical": 0.10,
                "target": 0.02,
            },
            # Business metrics
            "customer_satisfaction": {
                "warning": 0.70,
                "critical": 0.60,
                "target": 0.85,
            },
            "conversion_potential": {
                "warning": 0.15,
                "critical": 0.10,
                "target": 0.25,
            },
            "escalation_rate": {
                "warning": 0.15,
                "critical": 0.25,
                "target": 0.08,
            },
        }

        logger.info("MetricsCollector initialized")

    async def collect_routing_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Collect and analyze intent routing and agent selection metrics."""
        if not self.client:
            logger.error("LangSmith client not available")
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(
                    project_name=project,
                    start_time=start_time,
                    end_time=end_time,
                    limit=1000,
                )
            )

            if not runs:
                logger.warning(f"No runs found in the last {time_period_hours} hours")
                return {}

            metrics = {}

            routing_data = self._analyzer.analyze_routing_accuracy(runs)
            metrics["intent_routing_accuracy"] = self._create_metric_summary(
                "intent_routing_accuracy",
                MetricType.ROUTING,
                f"{time_period_hours}h",
                routing_data,
            )

            agent_data = self._analyzer.analyze_agent_selection(runs)
            metrics["agent_selection_accuracy"] = self._create_metric_summary(
                "agent_selection_accuracy",
                MetricType.ROUTING,
                f"{time_period_hours}h",
                agent_data,
            )

            confidence_data = self._analyzer.analyze_routing_confidence(runs)
            metrics["routing_confidence"] = self._create_metric_summary(
                "routing_confidence",
                MetricType.ROUTING,
                f"{time_period_hours}h",
                confidence_data,
            )

            logger.info(f"Collected routing metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting routing metrics: {e}")
            return {}

    async def collect_quality_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Collect and analyze response quality and task completion metrics."""
        if not self.client:
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(
                    project_name=project,
                    start_time=start_time,
                    end_time=end_time,
                    limit=1000,
                )
            )

            if not runs:
                return {}

            metrics = {}

            quality_data = self._analyzer.analyze_response_quality(runs)
            metrics["response_quality_score"] = self._create_metric_summary(
                "response_quality_score",
                MetricType.QUALITY,
                f"{time_period_hours}h",
                quality_data,
            )

            completion_data = self._analyzer.analyze_task_completion(runs)
            metrics["task_completion_rate"] = self._create_metric_summary(
                "task_completion_rate",
                MetricType.QUALITY,
                f"{time_period_hours}h",
                completion_data,
            )

            success_data = self._analyzer.analyze_conversation_success(runs)
            metrics["conversation_success_rate"] = self._create_metric_summary(
                "conversation_success_rate",
                MetricType.QUALITY,
                f"{time_period_hours}h",
                success_data,
            )

            logger.info(f"Collected quality metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting quality metrics: {e}")
            return {}

    async def collect_performance_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Collect and analyze system performance metrics."""
        if not self.client:
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(
                    project_name=project,
                    start_time=start_time,
                    end_time=end_time,
                    limit=1000,
                )
            )

            if not runs:
                return {}

            metrics = {}

            response_time_data = self._analyzer.analyze_response_times(runs)
            metrics["average_response_time"] = self._create_metric_summary(
                "average_response_time",
                MetricType.PERFORMANCE,
                f"{time_period_hours}h",
                response_time_data["average"],
            )
            metrics["p95_response_time"] = self._create_metric_summary(
                "p95_response_time",
                MetricType.PERFORMANCE,
                f"{time_period_hours}h",
                response_time_data["p95"],
            )

            error_data = self._analyzer.analyze_error_rates(runs)
            metrics["error_rate"] = self._create_metric_summary(
                "error_rate",
                MetricType.PERFORMANCE,
                f"{time_period_hours}h",
                error_data,
            )

            logger.info(f"Collected performance metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {}

    async def collect_business_metrics(
        self, time_period_hours: int = 24, project_name: str | None = None
    ) -> dict[str, MetricsSummary]:
        """Collect and analyze business-relevant metrics."""
        if not self.client:
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(
                    project_name=project,
                    start_time=start_time,
                    end_time=end_time,
                    limit=1000,
                )
            )

            if not runs:
                return {}

            metrics = {}

            satisfaction_data = self._analyzer.analyze_customer_satisfaction(runs)
            metrics["customer_satisfaction"] = self._create_metric_summary(
                "customer_satisfaction",
                MetricType.BUSINESS,
                f"{time_period_hours}h",
                satisfaction_data,
            )

            conversion_data = self._analyzer.analyze_conversion_potential(runs)
            metrics["conversion_potential"] = self._create_metric_summary(
                "conversion_potential",
                MetricType.BUSINESS,
                f"{time_period_hours}h",
                conversion_data,
            )

            escalation_data = self._analyzer.analyze_escalation_rates(runs)
            metrics["escalation_rate"] = self._create_metric_summary(
                "escalation_rate",
                MetricType.BUSINESS,
                f"{time_period_hours}h",
                escalation_data,
            )

            logger.info(f"Collected business metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")
            return {}

    def _create_metric_summary(
        self,
        metric_name: str,
        metric_type: MetricType,
        time_period: str,
        values: list[MetricValue],
    ) -> MetricsSummary:
        """Create a metric summary from collected values."""
        if not values:
            return MetricsSummary(
                metric_name=metric_name,
                metric_type=metric_type,
                time_period=time_period,
                current_value=0.0,
                average_value=0.0,
                min_value=0.0,
                max_value=0.0,
                sample_count=0,
                trend=MetricTrend.UNKNOWN,
                trend_confidence=0.0,
                threshold_status="unknown",
            )

        metric_values = [v.value for v in values]
        current_value = values[-1].value
        average_value = sum(metric_values) / len(metric_values)
        min_value = min(metric_values)
        max_value = max(metric_values)

        trend, trend_confidence = self._calculate_trend(values)
        threshold_status = self._get_threshold_status(metric_name, current_value)
        recommendations = self._generate_metric_recommendations(
            metric_name, current_value, threshold_status, trend
        )

        return MetricsSummary(
            metric_name=metric_name,
            metric_type=metric_type,
            time_period=time_period,
            current_value=current_value,
            average_value=average_value,
            min_value=min_value,
            max_value=max_value,
            sample_count=len(values),
            trend=trend,
            trend_confidence=trend_confidence,
            threshold_status=threshold_status,
            recommendations=recommendations,
        )

    def _calculate_trend(
        self, values: list[MetricValue]
    ) -> tuple[MetricTrend, float]:
        """Calculate trend direction and confidence."""
        if len(values) < 2:
            return MetricTrend.UNKNOWN, 0.0

        n = len(values)
        recent_half = values[n // 2 :]
        early_half = values[: n // 2] if n > 2 else values[:1]

        if not recent_half or not early_half:
            return MetricTrend.UNKNOWN, 0.0

        recent_avg = sum(v.value for v in recent_half) / len(recent_half)
        early_avg = sum(v.value for v in early_half) / len(early_half)

        change = recent_avg - early_avg
        change_percentage = abs(change) / (early_avg if early_avg != 0 else 1.0)

        if abs(change) < 0.02:
            trend = MetricTrend.STABLE
        elif change > 0:
            trend = MetricTrend.IMPROVING
        else:
            trend = MetricTrend.DECLINING

        confidence = min(1.0, change_percentage * 2 + (n / 20))

        return trend, confidence

    def _get_threshold_status(self, metric_name: str, value: float) -> str:
        """Determine threshold status for a metric value."""
        thresholds = self.thresholds.get(metric_name)
        if not thresholds:
            return "ok"

        if value < thresholds["critical"]:
            return "critical"
        elif value < thresholds["warning"]:
            return "warning"
        else:
            return "ok"

    def _generate_metric_recommendations(
        self,
        metric_name: str,
        value: float,
        status: str,
        trend: MetricTrend,
    ) -> list[str]:
        """Generate specific recommendations for a metric."""
        recommendations = []

        if status == "critical":
            recommendations.append(
                f"🚨 CRITICAL: {metric_name} is below acceptable threshold"
            )
        elif status == "warning":
            recommendations.append(f"⚠️ WARNING: {metric_name} needs attention")

        if trend == MetricTrend.DECLINING:
            recommendations.append(
                f"📉 {metric_name} is trending downward - investigate causes"
            )

        if metric_name == "intent_routing_accuracy" and value < 0.85:
            recommendations.extend(
                [
                    "Review intent classification training data",
                    "Analyze misrouted conversations for patterns",
                    "Consider updating routing thresholds",
                ]
            )
        elif metric_name == "response_quality_score" and value < 0.75:
            recommendations.extend(
                [
                    "Review and update agent prompts",
                    "Analyze low-quality responses for improvement",
                    "Consider additional training examples",
                ]
            )
        elif metric_name == "average_response_time" and value > 3.0:
            recommendations.extend(
                [
                    "Optimize database queries and API calls",
                    "Consider caching frequently accessed data",
                    "Review agent processing efficiency",
                ]
            )

        return recommendations
