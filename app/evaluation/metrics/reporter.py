"""
Metrics Reporter for Dashboard Generation.

Generates comprehensive dashboards and reports from collected metrics.
"""

import logging
from datetime import datetime
from typing import Any

from app.evaluation.metrics.collector import MetricsCollector
from app.evaluation.metrics.models import MetricsSummary, MetricTrend, MetricType

logger = logging.getLogger(__name__)


class MetricsReporter:
    """
    Generates reports and dashboards from metrics.

    Responsibilities:
    - Generate comprehensive dashboards
    - Calculate overall health scores
    - Identify top issues
    - Generate system-level recommendations
    """

    def __init__(self, collector: MetricsCollector | None = None):
        self._collector = collector or MetricsCollector()

    async def get_comprehensive_dashboard(
        self, time_period_hours: int = 24
    ) -> dict[str, Any]:
        """
        Get comprehensive metrics dashboard data.

        Returns:
            Dashboard data with all metrics categories
        """
        logger.info(
            f"Generating comprehensive dashboard for last {time_period_hours} hours"
        )

        routing_metrics = await self._collector.collect_routing_metrics(
            time_period_hours
        )
        quality_metrics = await self._collector.collect_quality_metrics(
            time_period_hours
        )
        performance_metrics = await self._collector.collect_performance_metrics(
            time_period_hours
        )
        business_metrics = await self._collector.collect_business_metrics(
            time_period_hours
        )

        all_metrics = {
            **routing_metrics,
            **quality_metrics,
            **performance_metrics,
            **business_metrics,
        }

        health_score = self._calculate_overall_health(all_metrics)
        issues = self._identify_top_issues(all_metrics)
        recommendations = self._generate_recommendations(all_metrics)

        dashboard = {
            "dashboard_generated_at": datetime.now().isoformat(),
            "time_period_hours": time_period_hours,
            "overall_health_score": health_score,
            "metrics_by_category": {
                "routing": routing_metrics,
                "quality": quality_metrics,
                "performance": performance_metrics,
                "business": business_metrics,
            },
            "top_issues": issues,
            "recommendations": recommendations,
            "alert_count": len(
                [
                    m
                    for m in all_metrics.values()
                    if m.threshold_status in ["warning", "critical"]
                ]
            ),
        }

        logger.info(f"Dashboard generated with {len(all_metrics)} metrics")
        return dashboard

    def _calculate_overall_health(
        self, metrics: dict[str, MetricsSummary]
    ) -> float:
        """Calculate overall system health score."""
        if not metrics:
            return 0.0

        weights = {
            MetricType.ROUTING: 0.3,
            MetricType.QUALITY: 0.3,
            MetricType.PERFORMANCE: 0.2,
            MetricType.BUSINESS: 0.2,
        }

        weighted_scores = []
        for metric in metrics.values():
            weight = weights.get(metric.metric_type, 0.1)

            score = metric.current_value
            if metric.threshold_status == "warning":
                score *= 0.8
            elif metric.threshold_status == "critical":
                score *= 0.5

            weighted_scores.append(score * weight)

        return (
            sum(weighted_scores) / sum(weights.values())
            if weighted_scores
            else 0.0
        )

    def _identify_top_issues(
        self, metrics: dict[str, MetricsSummary]
    ) -> list[dict[str, Any]]:
        """Identify the most critical issues from metrics."""
        issues = []

        for metric in metrics.values():
            if metric.threshold_status in ["warning", "critical"]:
                severity = (
                    "high" if metric.threshold_status == "critical" else "medium"
                )

                issues.append(
                    {
                        "metric": metric.metric_name,
                        "severity": severity,
                        "current_value": metric.current_value,
                        "trend": metric.trend.value,
                        "description": (
                            f"{metric.metric_name} is {metric.threshold_status}"
                        ),
                        "impact": self._assess_issue_impact(metric),
                    }
                )

        issues.sort(
            key=lambda x: (x["severity"] == "high", x["impact"]), reverse=True
        )
        return issues[:5]

    def _assess_issue_impact(self, metric: MetricsSummary) -> str:
        """Assess the business impact of a metric issue."""
        impact_map = {
            "intent_routing_accuracy": "Customer experience degradation",
            "response_quality_score": "Poor customer satisfaction",
            "average_response_time": "User experience impact",
            "error_rate": "System reliability concerns",
            "conversion_potential": "Revenue impact",
            "escalation_rate": "Support team workload increase",
        }
        return impact_map.get(metric.metric_name, "System performance impact")

    def _generate_recommendations(
        self, metrics: dict[str, MetricsSummary]
    ) -> list[str]:
        """Generate high-level system recommendations."""
        recommendations = []

        all_recs = []
        for metric in metrics.values():
            all_recs.extend(metric.recommendations)

        unique_recs = list(set(all_recs))

        if any(m.threshold_status == "critical" for m in metrics.values()):
            recommendations.append(
                "🚨 System requires immediate attention - multiple critical metrics"
            )

        if any(m.trend == MetricTrend.DECLINING for m in metrics.values()):
            recommendations.append(
                "📉 Monitor system trends - performance declining"
            )

        recommendations.extend(unique_recs[:8])
        return recommendations
