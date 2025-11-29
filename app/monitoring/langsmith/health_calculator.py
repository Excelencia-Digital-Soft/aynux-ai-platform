"""
Health Calculator.

Single Responsibility: Calculate system health score and status.
"""

from app.evaluation.metrics import MetricsSummary


class HealthCalculator:
    """Calculates system health metrics."""

    # Weight different metric categories
    CATEGORY_WEIGHTS = {
        "routing": 0.25,
        "quality": 0.30,
        "performance": 0.25,
        "business": 0.20,
    }

    def calculate_health_score(self, metrics: dict[str, MetricsSummary]) -> float:
        """Calculate overall system health score from metrics."""
        if not metrics:
            return 0.0

        category_scores: dict[str, list[float]] = {}

        # Group metrics by category and calculate category scores
        for _, metric in metrics.items():
            category = metric.metric_type.value
            if category not in category_scores:
                category_scores[category] = []

            # Apply penalty for threshold violations
            score = metric.current_value
            if metric.threshold_status == "warning":
                score *= 0.7
            elif metric.threshold_status == "critical":
                score *= 0.3

            category_scores[category].append(score)

        # Calculate weighted average
        total_weighted_score = 0.0
        total_weight = 0.0

        for category, scores in category_scores.items():
            if scores:
                category_avg = sum(scores) / len(scores)
                weight = self.CATEGORY_WEIGHTS.get(category, 0.1)
                total_weighted_score += category_avg * weight
                total_weight += weight

        return total_weighted_score / total_weight if total_weight > 0 else 0.0

    def determine_system_status(
        self, health_score: float, metrics: dict[str, MetricsSummary]
    ) -> str:
        """Determine overall system status."""
        critical_count = sum(
            1 for m in metrics.values() if m.threshold_status == "critical"
        )
        warning_count = sum(
            1 for m in metrics.values() if m.threshold_status == "warning"
        )

        if critical_count > 0 or health_score < 0.6:
            return "critical"
        elif warning_count > 2 or health_score < 0.8:
            return "degraded"
        else:
            return "healthy"
