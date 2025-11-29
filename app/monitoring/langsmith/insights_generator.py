"""
Insights Generator.

Single Responsibility: Generate insights, trends, and recommendations from metrics.
"""

from typing import Any

from app.evaluation.metrics import MetricsSummary, MetricTrend

from .schemas import Alert, AlertSeverity


class InsightsGenerator:
    """Generates insights and recommendations from monitoring data."""

    def generate_insights(self, metrics: dict[str, MetricsSummary]) -> list[str]:
        """Generate key insights from metrics analysis."""
        insights = []

        # Performance insights
        response_time = metrics.get("average_response_time")
        if response_time and response_time.current_value < 2.0:
            insights.append("System response times are excellent (< 2s average)")
        elif response_time and response_time.current_value > 5.0:
            insights.append(
                "Response times are concerning - investigate performance bottlenecks"
            )

        # Quality insights
        quality_score = metrics.get("response_quality_score")
        if quality_score and quality_score.current_value > 0.85:
            insights.append(
                "Response quality is high - users receiving excellent service"
            )
        elif quality_score and quality_score.trend == MetricTrend.IMPROVING:
            insights.append(
                "Response quality is improving - recent optimizations showing results"
            )

        # Routing insights
        routing_accuracy = metrics.get("intent_routing_accuracy")
        if routing_accuracy and routing_accuracy.current_value > 0.95:
            insights.append(
                "Intent routing is highly accurate - minimal misrouted conversations"
            )

        # Business insights
        conversion = metrics.get("conversion_potential")
        satisfaction = metrics.get("customer_satisfaction")

        if conversion and satisfaction:
            if conversion.current_value > 0.2 and satisfaction.current_value > 0.8:
                insights.append(
                    "Strong business metrics - high conversion potential "
                    "with satisfied customers"
                )

        return insights[:6]  # Top insights

    def analyze_trends(self, metrics: dict[str, MetricsSummary]) -> dict[str, str]:
        """Analyze trends across different metric categories."""
        trends = {}

        for category in ["routing", "quality", "performance", "business"]:
            category_metrics = [
                m for m in metrics.values() if m.metric_type.value == category
            ]
            if not category_metrics:
                continue

            improving = sum(
                1 for m in category_metrics if m.trend == MetricTrend.IMPROVING
            )
            declining = sum(
                1 for m in category_metrics if m.trend == MetricTrend.DECLINING
            )
            stable = sum(1 for m in category_metrics if m.trend == MetricTrend.STABLE)

            if improving > declining:
                trends[category] = "improving"
            elif declining > improving:
                trends[category] = "declining"
            elif stable > 0:
                trends[category] = "stable"
            else:
                trends[category] = "stable"

        return trends

    def generate_recommendations(
        self,
        metrics: dict[str, MetricsSummary],
        alerts: list[Alert],
    ) -> list[str]:
        """Generate high-level recommendations based on metrics and alerts."""
        recommendations = set()

        # Add recommendations from critical alerts
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                recommendations.update(alert.recommendations[:2])  # Top 2 per alert

        # Add recommendations from declining metrics
        for metric in metrics.values():
            if metric.trend == MetricTrend.DECLINING and metric.trend_confidence > 0.7:
                recommendations.update(
                    metric.recommendations[:1]
                )  # Top 1 per declining metric

        # System-level recommendations
        critical_count = len(
            [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        )
        if critical_count > 0:
            recommendations.add(
                "Address critical alerts immediately to restore system health"
            )

        warning_count = len([a for a in alerts if a.severity == AlertSeverity.WARNING])
        if warning_count > 3:
            recommendations.add(
                "Multiple warnings detected - schedule maintenance window"
            )

        return list(recommendations)[:8]  # Top 8 recommendations

    def identify_top_issues(
        self,
        metrics: dict[str, MetricsSummary],
        alerts: list[Alert],
    ) -> list[dict[str, Any]]:
        """Identify the most critical issues requiring attention."""
        issues = []

        # Add critical alerts as top issues
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                issues.append(
                    {
                        "type": "critical_alert",
                        "title": alert.title,
                        "description": alert.description,
                        "metric": alert.metric_name,
                        "impact": "high",
                        "recommendations": alert.recommendations[:3],
                    }
                )

        # Add declining trend issues
        declining_metrics = [
            m
            for m in metrics.values()
            if m.trend == MetricTrend.DECLINING and m.trend_confidence > 0.6
        ]

        for metric in declining_metrics[:3]:  # Top 3 declining metrics
            issues.append(
                {
                    "type": "declining_trend",
                    "title": f"{metric.metric_name.replace('_', ' ').title()} Declining",
                    "description": (
                        f"This metric has been declining with "
                        f"{metric.trend_confidence:.1%} confidence"
                    ),
                    "metric": metric.metric_name,
                    "impact": "medium",
                    "recommendations": metric.recommendations[:2],
                }
            )

        return issues[:5]  # Return top 5 issues
