"""
Alert Manager.

Single Responsibility: Create, update, and manage monitoring alerts.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.evaluation.metrics import MetricsSummary

from .schemas import Alert, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages monitoring alerts lifecycle."""

    def __init__(
        self,
        alert_thresholds: dict[str, Any],
        alert_cooldown_minutes: int = 15,
        auto_resolve_alerts: bool = True,
    ):
        self.alert_thresholds = alert_thresholds
        self.alert_cooldown_minutes = alert_cooldown_minutes
        self.auto_resolve_alerts = auto_resolve_alerts

        self.active_alerts: dict[str, Alert] = {}
        self.alert_history: list[Alert] = []

    async def update_alerts(
        self, metrics: dict[str, MetricsSummary]
    ) -> list[Alert]:
        """Update alerts based on current metrics."""
        new_alerts = []
        current_time = datetime.now()

        # Check each metric against thresholds
        for metric_name, metric in metrics.items():
            if metric.threshold_status in ["warning", "critical"]:
                alert_id = f"{metric_name}_{metric.threshold_status}"

                # Check if alert already exists and is in cooldown
                existing_alert = self.active_alerts.get(alert_id)
                if existing_alert:
                    cooldown_period = timedelta(minutes=self.alert_cooldown_minutes)
                    if current_time - existing_alert.updated_at < cooldown_period:
                        continue  # Skip if in cooldown

                    # Update existing alert
                    existing_alert.current_value = metric.current_value
                    existing_alert.updated_at = current_time
                    continue

                # Create new alert
                severity = (
                    AlertSeverity.CRITICAL
                    if metric.threshold_status == "critical"
                    else AlertSeverity.WARNING
                )
                threshold_value = self.alert_thresholds.get(metric_name, {}).get(
                    metric.threshold_status, 0.0
                )

                alert = Alert(
                    id=alert_id,
                    metric_name=metric_name,
                    severity=severity,
                    title=f"{metric_name.replace('_', ' ').title()} {metric.threshold_status.title()}",
                    description=self._generate_description(
                        metric_name, metric, threshold_value
                    ),
                    current_value=metric.current_value,
                    threshold_value=threshold_value,
                    triggered_at=current_time,
                    recommendations=metric.recommendations,
                    metadata={
                        "metric_type": metric.metric_type.value,
                        "trend": metric.trend.value,
                        "trend_confidence": metric.trend_confidence,
                    },
                )

                self.active_alerts[alert_id] = alert
                new_alerts.append(alert)

                logger.warning(f"New {severity.value} alert: {alert.title}")

        # Auto-resolve alerts for metrics that are now healthy
        alerts_to_resolve = []
        for alert_id, alert in self.active_alerts.items():
            metric = metrics.get(alert.metric_name)
            if metric and metric.threshold_status == "ok":
                if self.auto_resolve_alerts:
                    alerts_to_resolve.append(alert_id)

        for alert_id in alerts_to_resolve:
            await self.resolve_alert(alert_id, "auto_resolved")

        return new_alerts

    def _generate_description(
        self, metric_name: str, metric: MetricsSummary, threshold: float
    ) -> str:
        """Generate a descriptive alert message."""
        descriptions = {
            "intent_routing_accuracy": (
                f"Intent routing accuracy has dropped to {metric.current_value:.1%}, "
                f"below the {threshold:.1%} threshold. This may cause poor user "
                "experience due to incorrect agent routing."
            ),
            "response_quality_score": (
                f"Response quality score is {metric.current_value:.2f}, "
                f"below the {threshold:.2f} threshold. This indicates responses "
                "may not be meeting user expectations."
            ),
            "average_response_time": (
                f"Average response time is {metric.current_value:.1f}s, "
                f"above the {threshold:.1f}s threshold. Users may experience "
                "slow responses."
            ),
            "error_rate": (
                f"Error rate is {metric.current_value:.1%}, "
                f"above the {threshold:.1%} threshold. System reliability is compromised."
            ),
            "customer_satisfaction": (
                f"Customer satisfaction score is {metric.current_value:.2f}, "
                f"below the {threshold:.2f} threshold. User experience may be degraded."
            ),
        }

        return descriptions.get(
            metric_name,
            f"{metric_name} is {metric.current_value:.2f}, "
            f"which violates the {threshold:.2f} threshold.",
        )

    async def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str = "system"
    ) -> bool:
        """Acknowledge an active alert."""
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        alert.metadata["acknowledged_by"] = acknowledged_by

        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True

    async def resolve_alert(
        self, alert_id: str, resolved_by: str = "system"
    ) -> bool:
        """Resolve an active alert."""
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.metadata["resolved_by"] = resolved_by

        # Move to history and remove from active
        self.alert_history.append(alert)
        del self.active_alerts[alert_id]

        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return True

    async def get_history(
        self,
        hours: int = 24,
        severity: AlertSeverity | None = None,
        limit: int = 100,
    ) -> list[Alert]:
        """Get alert history with optional filtering."""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_alerts = [
            alert
            for alert in self.alert_history
            if alert.triggered_at >= cutoff_time
            and (severity is None or alert.severity == severity)
        ]

        # Sort by triggered time (most recent first)
        filtered_alerts.sort(key=lambda x: x.triggered_at, reverse=True)

        return filtered_alerts[:limit]

    def summarize(self, alerts: list[Alert]) -> dict[str, int]:
        """Summarize alert counts by severity."""
        summary = {"critical": 0, "warning": 0, "info": 0, "total": len(alerts)}

        for alert in alerts:
            summary[alert.severity.value] += 1

        return summary
