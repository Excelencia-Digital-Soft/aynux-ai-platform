"""
Alert Models and Enums.

Shared models for the alerting system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.monitoring.langsmith_dashboard import AlertSeverity


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
    channels: list[NotificationChannel]
    escalation_level: EscalationLevel


class AlertRule(BaseModel):
    """Defines conditions and actions for alerts."""

    name: str = Field(..., description="Rule name")
    metric_patterns: list[str] = Field(
        ..., description="Metric name patterns to match"
    )
    conditions: dict[str, Any] = Field(
        ..., description="Conditions that trigger the rule"
    )
    severity_mapping: dict[str, AlertSeverity] = Field(
        ..., description="Map conditions to severities"
    )
    notification_channels: list[NotificationChannel] = Field(
        ..., description="Notification channels to use"
    )
    escalation_policy: str | None = Field(
        None, description="Escalation policy name"
    )
    auto_actions: list[str] = Field(
        default_factory=list, description="Automated actions to take"
    )
    enabled: bool = Field(default=True, description="Whether the rule is active")


class EscalationPolicy(BaseModel):
    """Defines how alerts should be escalated."""

    name: str = Field(..., description="Policy name")
    levels: list[dict[str, Any]] = Field(
        ..., description="Escalation levels and timing"
    )
    max_escalations: int = Field(
        default=3, description="Maximum escalation attempts"
    )
    escalation_delay_minutes: int = Field(
        default=15, description="Minutes between escalations"
    )
    auto_acknowledge: bool = Field(
        default=False, description="Auto-acknowledge on escalation"
    )
