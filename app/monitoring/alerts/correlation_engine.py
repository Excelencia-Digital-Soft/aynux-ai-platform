"""
Alert Correlation Engine.

Correlates related alerts to reduce noise and identify patterns.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.monitoring.langsmith_dashboard import Alert

logger = logging.getLogger(__name__)


class AlertCorrelationEngine:
    """
    Correlates related alerts to reduce noise and identify patterns.

    Responsibilities:
    - Detect performance cascade patterns
    - Identify routing-quality correlations
    - Track business impact correlations
    - Generate correlation-based recommendations
    """

    def __init__(self):
        self.correlation_rules = {
            "performance_cascade": {
                "metrics": [
                    "average_response_time",
                    "p95_response_time",
                    "error_rate",
                ],
                "time_window_minutes": 10,
                "description": "Performance degradation cascade",
            },
            "routing_quality_correlation": {
                "metrics": [
                    "intent_routing_accuracy",
                    "response_quality_score",
                    "task_completion_rate",
                ],
                "time_window_minutes": 15,
                "description": "Routing affecting response quality",
            },
            "business_impact_correlation": {
                "metrics": [
                    "customer_satisfaction",
                    "conversion_potential",
                    "escalation_rate",
                ],
                "time_window_minutes": 30,
                "description": "Business metrics correlation",
            },
        }

        self.correlation_history: list[dict[str, Any]] = []

    def analyze_alert_correlations(
        self, alerts: list[Alert]
    ) -> list[dict[str, Any]]:
        """
        Analyze alerts for correlations and patterns.

        Args:
            alerts: List of active alerts

        Returns:
            List of correlation findings
        """
        correlations = []

        for rule_name, rule in self.correlation_rules.items():
            correlation = self._check_correlation_rule(alerts, rule_name, rule)
            if correlation:
                correlations.append(correlation)

        if correlations:
            self.correlation_history.extend(correlations)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.correlation_history = [
                c
                for c in self.correlation_history
                if datetime.fromisoformat(c["detected_at"]) > cutoff_time
            ]

        return correlations

    def _check_correlation_rule(
        self, alerts: list[Alert], rule_name: str, rule: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check if a specific correlation rule is triggered."""

        matching_alerts = [
            alert
            for alert in alerts
            if any(metric in alert.metric_name for metric in rule["metrics"])
        ]

        if len(matching_alerts) < 2:
            return None

        time_window = timedelta(minutes=rule["time_window_minutes"])
        now = datetime.now()

        recent_alerts = [
            alert
            for alert in matching_alerts
            if now - alert.triggered_at <= time_window
        ]

        if len(recent_alerts) < 2:
            return None

        return {
            "rule_name": rule_name,
            "description": rule["description"],
            "correlated_alerts": [alert.id for alert in recent_alerts],
            "affected_metrics": [alert.metric_name for alert in recent_alerts],
            "severity": max(alert.severity.value for alert in recent_alerts),
            "detected_at": now.isoformat(),
            "confidence": self._calculate_correlation_confidence(
                recent_alerts, rule
            ),
            "recommendations": self._generate_correlation_recommendations(
                rule_name, recent_alerts
            ),
        }

    def _calculate_correlation_confidence(
        self, alerts: list[Alert], rule: dict[str, Any]
    ) -> float:
        """Calculate confidence in the correlation."""
        base_confidence = 0.5

        alert_factor = min(1.0, len(alerts) / len(rule["metrics"]))

        avg_age_minutes = sum(
            (datetime.now() - alert.triggered_at).total_seconds() / 60
            for alert in alerts
        ) / len(alerts)

        recency_factor = max(
            0.0, 1.0 - (avg_age_minutes / rule["time_window_minutes"])
        )

        severity_scores = {"info": 0.3, "warning": 0.6, "critical": 1.0}
        avg_severity = sum(
            severity_scores.get(alert.severity.value, 0.5) for alert in alerts
        ) / len(alerts)

        confidence = (
            base_confidence
            + (alert_factor * 0.2)
            + (recency_factor * 0.2)
            + (avg_severity * 0.1)
        )
        return min(1.0, confidence)

    def _generate_correlation_recommendations(
        self, rule_name: str, alerts: list[Alert]
    ) -> list[str]:
        """Generate recommendations based on correlation type."""
        recommendations = {
            "performance_cascade": [
                "Investigate system performance bottlenecks immediately",
                "Check database and API response times",
                "Review resource utilization (CPU, memory, network)",
                "Consider scaling infrastructure if needed",
            ],
            "routing_quality_correlation": [
                "Review intent classification accuracy",
                "Analyze recent conversation patterns for misrouting",
                "Update agent training data if needed",
                "Check for recent changes to routing logic",
            ],
            "business_impact_correlation": [
                "Focus on customer experience improvements",
                "Review conversation outcomes and satisfaction",
                "Consider business process optimizations",
                "Monitor conversion rates closely",
            ],
        }

        base_recs = recommendations.get(
            rule_name, ["Investigate correlated system issues"]
        )

        for alert in alerts:
            base_recs.extend(alert.recommendations[:2])

        return list(set(base_recs))[:6]
