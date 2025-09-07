"""
Advanced alerting system for ConversaShop LangSmith monitoring.

This module provides intelligent alerting with multiple notification channels,
alert correlation, escalation policies, and automated remediation suggestions.
"""

import asyncio
import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

# Email MIME types with fallback
MimeText = None
MimeMultipart = None
try:
    from email.mime.multipart import MimeMultipart  # type: ignore
    from email.mime.text import MimeText  # type: ignore
except ImportError:
    pass  # Will be None, handled in the email function

from pydantic import BaseModel, Field  # noqa: E402

from app.config.settings import get_settings  # noqa: E402
from app.monitoring.langsmith_dashboard import Alert, AlertSeverity  # noqa: E402

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Available notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    SMS = "sms"


class EscalationLevel(Enum):
    """Alert escalation levels."""

    L1 = "level_1"  # First line support
    L2 = "level_2"  # Engineering team
    L3 = "level_3"  # Senior leadership
    EMERGENCY = "emergency"  # All hands


@dataclass
class NotificationTemplate:
    """Template for alert notifications."""

    subject_template: str
    body_template: str
    channels: List[NotificationChannel]
    escalation_level: EscalationLevel


class AlertRule(BaseModel):
    """Defines conditions and actions for alerts."""

    name: str = Field(..., description="Rule name")
    metric_patterns: List[str] = Field(..., description="Metric name patterns to match")
    conditions: Dict[str, Any] = Field(..., description="Conditions that trigger the rule")
    severity_mapping: Dict[str, AlertSeverity] = Field(..., description="Map conditions to severities")
    notification_channels: List[NotificationChannel] = Field(..., description="Notification channels to use")
    escalation_policy: Optional[str] = Field(None, description="Escalation policy name")
    auto_actions: List[str] = Field(default_factory=list, description="Automated actions to take")
    enabled: bool = Field(default=True, description="Whether the rule is active")


class EscalationPolicy(BaseModel):
    """Defines how alerts should be escalated."""

    name: str = Field(..., description="Policy name")
    levels: List[Dict[str, Any]] = Field(..., description="Escalation levels and timing")
    max_escalations: int = Field(default=3, description="Maximum escalation attempts")
    escalation_delay_minutes: int = Field(default=15, description="Minutes between escalations")
    auto_acknowledge: bool = Field(default=False, description="Auto-acknowledge on escalation")


class NotificationService:
    """Handles sending notifications through various channels."""

    def __init__(self):
        self.settings = get_settings()

        # Notification templates
        self.templates = {
            AlertSeverity.CRITICAL: NotificationTemplate(
                subject_template="🚨 CRITICAL Alert: {metric_name}",
                body_template="""
CRITICAL ALERT TRIGGERED

Metric: {metric_name}
Current Value: {current_value}
Threshold: {threshold_value}
Severity: {severity}

Description: {description}

Immediate Actions Required:
{recommendations}

Alert Details:
- Triggered: {triggered_at}
- System Health: {system_health}
- Trend: {trend}

Dashboard: {dashboard_url}
                """,
                channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK, NotificationChannel.SMS],
                escalation_level=EscalationLevel.L2,
            ),
            AlertSeverity.WARNING: NotificationTemplate(
                subject_template="⚠️ Warning: {metric_name}",
                body_template="""
WARNING ALERT

Metric: {metric_name}
Current Value: {current_value}
Threshold: {threshold_value}

Description: {description}

Recommended Actions:
{recommendations}

Alert triggered at: {triggered_at}
                """,
                channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                escalation_level=EscalationLevel.L1,
            ),
            AlertSeverity.INFO: NotificationTemplate(
                subject_template="ℹ️ Info: {metric_name}",
                body_template="""
INFORMATIONAL ALERT

Metric: {metric_name}
Current Value: {current_value}
Description: {description}

This is for your awareness - no immediate action required.
                """,
                channels=[NotificationChannel.EMAIL],
                escalation_level=EscalationLevel.L1,
            ),
        }

        logger.info("NotificationService initialized")

    async def send_alert_notification(
        self,
        alert: Alert,
        channels: Optional[List[NotificationChannel]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[NotificationChannel, bool]:
        """
        Send alert notification through specified channels.

        Args:
            alert: Alert to send notification for
            channels: Specific channels to use (overrides template defaults)
            context: Additional context for template rendering

        Returns:
            Dictionary mapping channels to success status
        """
        template = self.templates.get(alert.severity)
        if not template:
            logger.error(f"No template found for severity {alert.severity}")
            return {}

        target_channels = channels or template.channels
        context = context or {}

        # Prepare notification context
        notification_context = {
            "metric_name": alert.metric_name,
            "current_value": alert.current_value,
            "threshold_value": alert.threshold_value,
            "severity": alert.severity.value.upper(),
            "description": alert.description,
            "recommendations": self._format_recommendations(alert.recommendations),
            "triggered_at": alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "trend": alert.metadata.get("trend", "unknown"),
            "system_health": context.get("system_health", "unknown"),
            "dashboard_url": context.get("dashboard_url", "N/A"),
            **context,
        }

        # Send through each channel
        results = {}
        for channel in target_channels:
            try:
                success = await self._send_to_channel(channel, template, notification_context, alert)
                results[channel] = success

                if success:
                    logger.info(f"Alert {alert.id} sent via {channel.value}")
                else:
                    logger.error(f"Failed to send alert {alert.id} via {channel.value}")

            except Exception as e:
                logger.error(f"Error sending alert via {channel.value}: {e}")
                results[channel] = False

        return results

    async def _send_to_channel(
        self, channel: NotificationChannel, template: NotificationTemplate, context: Dict[str, Any], alert: Alert
    ) -> bool:
        """Send notification to a specific channel."""

        if channel == NotificationChannel.EMAIL:
            return await self._send_email(template, context)

        elif channel == NotificationChannel.SLACK:
            return await self._send_slack(template, context)

        elif channel == NotificationChannel.WEBHOOK:
            return await self._send_webhook(template, context, alert)

        elif channel == NotificationChannel.CONSOLE:
            return self._send_console(template, context)

        elif channel == NotificationChannel.SMS:
            return await self._send_sms(template, context)

    async def _send_email(self, template: NotificationTemplate, context: Dict[str, Any]) -> bool:
        """Send email notification."""
        try:
            # Email configuration (would typically come from settings)
            smtp_server = getattr(self.settings, "SMTP_SERVER", "localhost")
            smtp_port = getattr(self.settings, "SMTP_PORT", 587)
            smtp_username = getattr(self.settings, "SMTP_USERNAME", "")
            smtp_password = getattr(self.settings, "SMTP_PASSWORD", "")
            from_email = getattr(self.settings, "ALERT_FROM_EMAIL", "alerts@conversashop.com")
            to_emails = getattr(self.settings, "ALERT_TO_EMAILS", ["admin@conversashop.com"])

            if not smtp_username:
                logger.warning("Email notifications not configured")
                return False

            # Create message
            if MimeMultipart is None or MimeText is None:
                logger.error("Email MIME components not available")
                return False

            msg = MimeMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = template.subject_template.format(**context)

            body = template.body_template.format(**context)
            msg.attach(MimeText(body, "plain"))

            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    async def _send_slack(self, template: NotificationTemplate, context: Dict[str, Any]) -> bool:
        """Send Slack notification."""
        try:
            slack_webhook = getattr(self.settings, "SLACK_WEBHOOK_URL", "")
            if not slack_webhook:
                logger.warning("Slack webhook not configured")
                return False

            # Format message for Slack
            color = {"CRITICAL": "danger", "WARNING": "warning", "INFO": "good"}.get(
                context.get("severity", "INFO"), "warning"
            )

            payload = {
                "text": template.subject_template.format(**context),
                "attachments": [
                    {"color": color, "text": template.body_template.format(**context), "ts": datetime.now().timestamp()}
                ],
            }

            # Send to Slack (would use aiohttp in real implementation)
            # For now, just log
            logger.info(f"Would send to Slack: {payload['text']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def _send_webhook(self, template: NotificationTemplate, context: Dict[str, Any], alert: Alert) -> bool:
        """Send webhook notification."""
        try:
            webhook_url = getattr(self.settings, "ALERT_WEBHOOK_URL", "")
            if not webhook_url:
                logger.warning("Webhook URL not configured")
                return False

            payload = {
                "alert_id": alert.id,
                "metric_name": alert.metric_name,
                "severity": alert.severity.value,
                "title": template.subject_template.format(**context),
                "description": alert.description,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "triggered_at": alert.triggered_at.isoformat(),
                "metadata": alert.metadata,
                "context": context,
            }

            # Send webhook (would use aiohttp in real implementation)
            logger.info(f"Would send webhook to {webhook_url}: {payload}")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def _send_console(self, template: NotificationTemplate, context: Dict[str, Any]) -> bool:
        """Send console notification (log message)."""
        try:
            subject = template.subject_template.format(**context)
            body = template.body_template.format(**context)

            severity = context.get("severity", "INFO")
            if severity == "CRITICAL":
                logger.critical(f"CONSOLE ALERT: {subject}\n{body}")
            elif severity == "WARNING":
                logger.warning(f"CONSOLE ALERT: {subject}\n{body}")
            else:
                logger.info(f"CONSOLE ALERT: {subject}\n{body}")

            return True

        except Exception as e:
            logger.error(f"Failed to send console notification: {e}")
            return False

    async def _send_sms(self, _: NotificationTemplate, context: Dict[str, Any]) -> bool:
        """Send SMS notification."""
        try:
            # SMS would typically integrate with Twilio or similar service
            sms_api_key = getattr(self.settings, "SMS_API_KEY", "")
            if not sms_api_key:
                logger.warning("SMS notifications not configured")
                return False

            # For critical alerts, send abbreviated SMS
            message = (
                f"CRITICAL ALERT: {context['metric_name']} = {context['current_value']}"
                f" (threshold: {context['threshold_value']})"
            )
            phone_numbers = getattr(self.settings, "ALERT_PHONE_NUMBERS", [])

            logger.info(f"Would send SMS to {phone_numbers}: {message}")
            return True

        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")
            return False

    def _format_recommendations(self, recommendations: List[str]) -> str:
        """Format recommendations for notification."""
        if not recommendations:
            return "No specific recommendations available."

        formatted = []
        for i, rec in enumerate(recommendations[:5], 1):  # Limit to top 5
            formatted.append(f"{i}. {rec}")

        return "\n".join(formatted)


class AlertCorrelationEngine:
    """Correlates related alerts to reduce noise and identify patterns."""

    def __init__(self):
        # Correlation rules
        self.correlation_rules = {
            "performance_cascade": {
                "metrics": ["average_response_time", "p95_response_time", "error_rate"],
                "time_window_minutes": 10,
                "description": "Performance degradation cascade",
            },
            "routing_quality_correlation": {
                "metrics": ["intent_routing_accuracy", "response_quality_score", "task_completion_rate"],
                "time_window_minutes": 15,
                "description": "Routing affecting response quality",
            },
            "business_impact_correlation": {
                "metrics": ["customer_satisfaction", "conversion_potential", "escalation_rate"],
                "time_window_minutes": 30,
                "description": "Business metrics correlation",
            },
        }

        self.correlation_history: List[Dict[str, Any]] = []

    def analyze_alert_correlations(self, alerts: List[Alert]) -> List[Dict[str, Any]]:
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

        # Store in history
        if correlations:
            self.correlation_history.extend(correlations)
            # Keep only recent history
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.correlation_history = [
                c for c in self.correlation_history if datetime.fromisoformat(c["detected_at"]) > cutoff_time
            ]

        return correlations

    def _check_correlation_rule(
        self, alerts: List[Alert], rule_name: str, rule: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Check if a specific correlation rule is triggered."""

        # Find alerts matching the rule metrics
        matching_alerts = [alert for alert in alerts if any(metric in alert.metric_name for metric in rule["metrics"])]

        if len(matching_alerts) < 2:
            return None

        # Check if alerts are within the time window
        time_window = timedelta(minutes=rule["time_window_minutes"])
        now = datetime.now()

        recent_alerts = [alert for alert in matching_alerts if now - alert.triggered_at <= time_window]

        if len(recent_alerts) < 2:
            return None

        # Create correlation finding
        return {
            "rule_name": rule_name,
            "description": rule["description"],
            "correlated_alerts": [alert.id for alert in recent_alerts],
            "affected_metrics": [alert.metric_name for alert in recent_alerts],
            "severity": max(alert.severity.value for alert in recent_alerts),
            "detected_at": now.isoformat(),
            "confidence": self._calculate_correlation_confidence(recent_alerts, rule),
            "recommendations": self._generate_correlation_recommendations(rule_name, recent_alerts),
        }

    def _calculate_correlation_confidence(self, alerts: List[Alert], rule: Dict[str, Any]) -> float:
        """Calculate confidence in the correlation."""
        base_confidence = 0.5

        # More alerts = higher confidence
        alert_factor = min(1.0, len(alerts) / len(rule["metrics"]))

        # Recent alerts = higher confidence
        avg_age_minutes = sum((datetime.now() - alert.triggered_at).total_seconds() / 60 for alert in alerts) / len(
            alerts
        )

        recency_factor = max(0.0, 1.0 - (avg_age_minutes / rule["time_window_minutes"]))

        # Severity factor
        severity_scores = {"info": 0.3, "warning": 0.6, "critical": 1.0}
        avg_severity = sum(severity_scores.get(alert.severity.value, 0.5) for alert in alerts) / len(alerts)

        confidence = base_confidence + (alert_factor * 0.2) + (recency_factor * 0.2) + (avg_severity * 0.1)
        return min(1.0, confidence)

    def _generate_correlation_recommendations(self, rule_name: str, alerts: List[Alert]) -> List[str]:
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

        base_recs = recommendations.get(rule_name, ["Investigate correlated system issues"])

        # Add alert-specific recommendations
        for alert in alerts:
            base_recs.extend(alert.recommendations[:2])

        # Remove duplicates and limit
        return list(set(base_recs))[:6]


class ConversaShopAlertManager:
    """Main alert management system combining notifications, correlation, and escalation."""

    def __init__(self):
        self.notification_service = NotificationService()
        self.correlation_engine = AlertCorrelationEngine()

        # Alert processing queue
        self.alert_queue: asyncio.Queue = asyncio.Queue()
        self.processing_alerts = False

        # Escalation tracking
        self.escalated_alerts: Dict[str, Dict[str, Any]] = {}

        logger.info("ConversaShopAlertManager initialized")

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

    async def process_alerts(self, alerts: List[Alert], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a batch of alerts with correlation analysis and notifications.

        Args:
            alerts: List of alerts to process
            context: Additional context for notifications

        Returns:
            Processing results summary
        """
        logger.info(f"Processing {len(alerts)} alerts")

        # Analyze correlations first
        correlations = self.correlation_engine.analyze_alert_correlations(alerts)

        # Process individual alerts
        notification_results = {}
        for alert in alerts:
            # Add to processing queue
            await self.alert_queue.put((alert, context or {}))

            # For critical alerts, process immediately
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
                # Wait for alerts with timeout
                try:
                    alert, context = await asyncio.wait_for(self.alert_queue.get(), timeout=5.0)
                    await self._process_single_alert(alert, context)
                except asyncio.TimeoutError:
                    continue

            except Exception as e:
                logger.error(f"Error in alert processing queue: {e}")
                await asyncio.sleep(1)

    async def _process_single_alert(self, alert: Alert, context: Dict[str, Any]) -> Dict[str, bool]:
        """Process a single alert with notifications and escalation."""
        try:
            logger.debug(f"Processing alert: {alert.id}")

            # Send notifications
            notification_results = await self.notification_service.send_alert_notification(alert, context=context)

            # Check if escalation is needed
            if alert.severity == AlertSeverity.CRITICAL:
                await self._handle_escalation(alert, context)

            # Convert NotificationChannel enum keys to strings
            return {channel.value: result for channel, result in notification_results.items()}

        except Exception as e:
            logger.error(f"Error processing alert {alert.id}: {e}")
            return {}

    async def _handle_escalation(self, alert: Alert, _: Dict[str, Any]):
        """Handle alert escalation if needed."""
        escalation_key = f"{alert.metric_name}_{alert.severity.value}"

        if escalation_key in self.escalated_alerts:
            # Already escalated, check if follow-up is needed
            escalation_info = self.escalated_alerts[escalation_key]
            last_escalation = datetime.fromisoformat(escalation_info["last_escalation"])

            if datetime.now() - last_escalation > timedelta(minutes=30):
                # Escalate further if alert persists
                escalation_info["level"] += 1
                escalation_info["last_escalation"] = datetime.now().isoformat()

                logger.warning(f"Escalating alert {alert.id} to level {escalation_info['level']}")
        else:
            # First escalation
            self.escalated_alerts[escalation_key] = {
                "alert_id": alert.id,
                "level": 1,
                "first_escalation": datetime.now().isoformat(),
                "last_escalation": datetime.now().isoformat(),
            }

            logger.warning(f"Initial escalation for alert {alert.id}")

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert processing statistics."""
        return {
            "queue_size": self.alert_queue.qsize(),
            "processing_active": self.processing_alerts,
            "escalated_alerts_count": len(self.escalated_alerts),
            "correlation_history_count": len(self.correlation_engine.correlation_history),
            "notification_channels_configured": self._get_configured_channels(),
        }

    def _get_configured_channels(self) -> List[str]:
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

        channels.append("console")  # Always available

        return channels


# Global singleton instance
_alert_manager_instance: Optional[ConversaShopAlertManager] = None


def get_alert_manager() -> ConversaShopAlertManager:
    """Get a singleton instance of ConversaShopAlertManager."""
    global _alert_manager_instance
    if _alert_manager_instance is None:
        _alert_manager_instance = ConversaShopAlertManager()
    return _alert_manager_instance

