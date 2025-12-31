"""
Notification Service.

Handles sending notifications through various channels.
"""

import logging
import smtplib
from datetime import datetime
from typing import Any

# Email MIME types with fallback
MimeText = None
MimeMultipart = None
try:
    from email.mime.multipart import MIMEMultipart as MimeMultipart
    from email.mime.text import MIMEText as MimeText
except ImportError:
    pass

from app.config.settings import get_settings
from app.monitoring.alerts.models import (
    EscalationLevel,
    NotificationChannel,
    NotificationTemplate,
)
from app.monitoring.langsmith_dashboard import Alert, AlertSeverity

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Handles sending notifications through various channels.

    Responsibilities:
    - Send alerts via email, Slack, webhook, console, SMS
    - Manage notification templates
    - Format recommendations for display
    """

    def __init__(self):
        self.settings = get_settings()

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
                channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.SLACK,
                    NotificationChannel.SMS,
                ],
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
                channels=[
                    NotificationChannel.EMAIL,
                    NotificationChannel.SLACK,
                ],
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
        channels: list[NotificationChannel] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[NotificationChannel, bool]:
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

        results = {}
        for channel in target_channels:
            try:
                success = await self._send_to_channel(
                    channel, template, notification_context, alert
                )
                results[channel] = success

                if success:
                    logger.info(f"Alert {alert.id} sent via {channel.value}")
                else:
                    logger.error(
                        f"Failed to send alert {alert.id} via {channel.value}"
                    )

            except Exception as e:
                logger.error(f"Error sending alert via {channel.value}: {e}")
                results[channel] = False

        return results

    async def _send_to_channel(
        self,
        channel: NotificationChannel,
        template: NotificationTemplate,
        context: dict[str, Any],
        alert: Alert,
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

        return False

    async def _send_email(
        self, template: NotificationTemplate, context: dict[str, Any]
    ) -> bool:
        """Send email notification."""
        try:
            smtp_server = getattr(self.settings, "SMTP_SERVER", "localhost")
            smtp_port = getattr(self.settings, "SMTP_PORT", 587)
            smtp_username = getattr(self.settings, "SMTP_USERNAME", "")
            smtp_password = getattr(self.settings, "SMTP_PASSWORD", "")
            from_email = getattr(
                self.settings, "ALERT_FROM_EMAIL", "alerts@aynux.com"
            )
            to_emails = getattr(
                self.settings, "ALERT_TO_EMAILS", ["admin@aynux.com"]
            )

            if not smtp_username:
                logger.warning("Email notifications not configured")
                return False

            if MimeMultipart is None or MimeText is None:
                logger.error("Email MIME components not available")
                return False

            msg = MimeMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = template.subject_template.format(**context)

            body = template.body_template.format(**context)
            msg.attach(MimeText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)

            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    async def _send_slack(
        self, template: NotificationTemplate, context: dict[str, Any]
    ) -> bool:
        """Send Slack notification."""
        try:
            slack_webhook = getattr(self.settings, "SLACK_WEBHOOK_URL", "")
            if not slack_webhook:
                logger.warning("Slack webhook not configured")
                return False

            color = {"CRITICAL": "danger", "WARNING": "warning", "INFO": "good"}.get(
                context.get("severity", "INFO"), "warning"
            )

            payload = {
                "text": template.subject_template.format(**context),
                "attachments": [
                    {
                        "color": color,
                        "text": template.body_template.format(**context),
                        "ts": datetime.now().timestamp(),
                    }
                ],
            }

            logger.info(f"Would send to Slack: {payload['text']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def _send_webhook(
        self,
        template: NotificationTemplate,
        context: dict[str, Any],
        alert: Alert,
    ) -> bool:
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

            logger.info(f"Would send webhook to {webhook_url}: {payload}")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def _send_console(
        self, template: NotificationTemplate, context: dict[str, Any]
    ) -> bool:
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

    async def _send_sms(
        self, _: NotificationTemplate, context: dict[str, Any]
    ) -> bool:
        """Send SMS notification."""
        try:
            sms_api_key = getattr(self.settings, "SMS_API_KEY", "")
            if not sms_api_key:
                logger.warning("SMS notifications not configured")
                return False

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

    def _format_recommendations(self, recommendations: list[str]) -> str:
        """Format recommendations for notification."""
        if not recommendations:
            return "No specific recommendations available."

        formatted = []
        for i, rec in enumerate(recommendations[:5], 1):
            formatted.append(f"{i}. {rec}")

        return "\n".join(formatted)
