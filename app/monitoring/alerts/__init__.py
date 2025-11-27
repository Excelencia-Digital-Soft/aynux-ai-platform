"""
Alerts Module.

Advanced alerting system for Aynux LangSmith monitoring.

Components:
- NotificationService: Multi-channel notification delivery
- AlertCorrelationEngine: Pattern detection and alert correlation
- AynuxAlertManager: Main alert management facade
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from app.monitoring.alerts.correlation_engine import AlertCorrelationEngine
from app.monitoring.alerts.models import (
    AlertRule,
    EscalationLevel,
    EscalationPolicy,
    NotificationChannel,
    NotificationTemplate,
)
from app.monitoring.alerts.notification_service import NotificationService
from app.monitoring.langsmith_dashboard import Alert, AlertSeverity

logger = logging.getLogger(__name__)


class AynuxAlertManager:
    """
    Main alert management system.

    Facade that coordinates:
    - NotificationService: Multi-channel notifications
    - AlertCorrelationEngine: Pattern detection
    - Escalation tracking and handling
    """

    def __init__(self):
        self.notification_service = NotificationService()
        self.correlation_engine = AlertCorrelationEngine()

        self.alert_queue: asyncio.Queue = asyncio.Queue()
        self.processing_alerts = False

        self.escalated_alerts: dict[str, dict[str, Any]] = {}

        logger.info("AynuxAlertManager initialized")

    async def start_alert_processing(self):
        """Start the alert processing background task."""
        if self.processing_alerts:
            return

        self.processing_alerts = True
        asyncio.create_task(self._process_alert_queue())
        logger.info("Alert processing started")

    async def stop_alert_processing(self):
        """Stop the alert processing background task."""
        self.processing_alerts = False
        logger.info("Alert processing stopped")

    async def process_alerts(
        self, alerts: list[Alert], context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Process a batch of alerts with correlation analysis and notifications.

        Args:
            alerts: List of alerts to process
            context: Additional context for notifications

        Returns:
            Processing results summary
        """
        logger.info(f"Processing {len(alerts)} alerts")

        correlations = self.correlation_engine.analyze_alert_correlations(alerts)

        notification_results = {}
        for alert in alerts:
            await self.alert_queue.put((alert, context or {}))

            if alert.severity == AlertSeverity.CRITICAL:
                result = await self._process_single_alert(alert, context or {})
                notification_results[alert.id] = result

        return {
            "processed_alerts": len(alerts),
            "correlations_found": len(correlations),
            "correlations": correlations,
            "notification_results": notification_results,
            "processing_timestamp": datetime.now().isoformat(),
        }

    async def _process_alert_queue(self):
        """Background task to process queued alerts."""
        while self.processing_alerts:
            try:
                try:
                    alert, context = await asyncio.wait_for(
                        self.alert_queue.get(), timeout=5.0
                    )
                    await self._process_single_alert(alert, context)
                except asyncio.TimeoutError:
                    continue

            except Exception as e:
                logger.error(f"Error in alert processing queue: {e}")
                await asyncio.sleep(1)

    async def _process_single_alert(
        self, alert: Alert, context: dict[str, Any]
    ) -> dict[str, bool]:
        """Process a single alert with notifications and escalation."""
        try:
            logger.debug(f"Processing alert: {alert.id}")

            notification_results = (
                await self.notification_service.send_alert_notification(
                    alert, context=context
                )
            )

            if alert.severity == AlertSeverity.CRITICAL:
                await self._handle_escalation(alert, context)

            return {
                channel.value: result
                for channel, result in notification_results.items()
            }

        except Exception as e:
            logger.error(f"Error processing alert {alert.id}: {e}")
            return {}

    async def _handle_escalation(
        self, alert: Alert, _: dict[str, Any]
    ):
        """Handle alert escalation if needed."""
        escalation_key = f"{alert.metric_name}_{alert.severity.value}"

        if escalation_key in self.escalated_alerts:
            escalation_info = self.escalated_alerts[escalation_key]
            last_escalation = datetime.fromisoformat(
                escalation_info["last_escalation"]
            )

            if datetime.now() - last_escalation > timedelta(minutes=30):
                escalation_info["level"] += 1
                escalation_info["last_escalation"] = datetime.now().isoformat()

                logger.warning(
                    f"Escalating alert {alert.id} to level {escalation_info['level']}"
                )
        else:
            self.escalated_alerts[escalation_key] = {
                "alert_id": alert.id,
                "level": 1,
                "first_escalation": datetime.now().isoformat(),
                "last_escalation": datetime.now().isoformat(),
            }

            logger.warning(f"Initial escalation for alert {alert.id}")

    def get_alert_statistics(self) -> dict[str, Any]:
        """Get alert processing statistics."""
        return {
            "queue_size": self.alert_queue.qsize(),
            "processing_active": self.processing_alerts,
            "escalated_alerts_count": len(self.escalated_alerts),
            "correlation_history_count": len(
                self.correlation_engine.correlation_history
            ),
            "notification_channels_configured": self._get_configured_channels(),
        }

    def _get_configured_channels(self) -> list[str]:
        """Get list of configured notification channels."""
        channels = []

        if hasattr(self.notification_service.settings, "SMTP_USERNAME"):
            channels.append("email")
        if hasattr(self.notification_service.settings, "SLACK_WEBHOOK_URL"):
            channels.append("slack")
        if hasattr(self.notification_service.settings, "ALERT_WEBHOOK_URL"):
            channels.append("webhook")
        if hasattr(self.notification_service.settings, "SMS_API_KEY"):
            channels.append("sms")

        channels.append("console")

        return channels


# Global singleton instance
_alert_manager_instance: AynuxAlertManager | None = None


def get_alert_manager() -> AynuxAlertManager:
    """Get a singleton instance of AynuxAlertManager."""
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = AynuxAlertManager()
    return _alert_manager_instance


__all__ = [
    # Models
    "NotificationChannel",
    "EscalationLevel",
    "NotificationTemplate",
    "AlertRule",
    "EscalationPolicy",
    # Services
    "NotificationService",
    "AlertCorrelationEngine",
    # Manager
    "AynuxAlertManager",
    "get_alert_manager",
]
