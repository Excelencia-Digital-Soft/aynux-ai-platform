"""
LangSmith Monitoring Schemas.

Single Responsibility: Data models for monitoring alerts and dashboard.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.evaluation.metrics import MetricsSummary


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(BaseModel):
    """Represents a monitoring alert."""

    id: str = Field(..., description="Unique alert identifier")
    metric_name: str = Field(
        ..., description="Name of the metric that triggered the alert"
    )
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(
        default=AlertStatus.ACTIVE, description="Current alert status"
    )

    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Detailed alert description")
    current_value: float = Field(..., description="Current metric value")
    threshold_value: float = Field(..., description="Threshold that was breached")

    triggered_at: datetime = Field(
        ..., description="When the alert was first triggered"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update timestamp"
    )
    acknowledged_at: datetime | None = Field(
        None, description="When alert was acknowledged"
    )
    resolved_at: datetime | None = Field(None, description="When alert was resolved")

    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional alert context"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended actions"
    )


class DashboardData(BaseModel):
    """Complete dashboard data structure."""

    generated_at: datetime = Field(
        default_factory=datetime.now, description="Dashboard generation timestamp"
    )
    time_period_hours: int = Field(
        default=24, description="Time period covered by metrics"
    )

    # System overview
    overall_health_score: float = Field(
        ..., description="Overall system health (0-1)"
    )
    system_status: str = Field(
        ..., description="System status: healthy, degraded, critical"
    )

    # Metrics by category
    routing_metrics: dict[str, MetricsSummary] = Field(default_factory=dict)
    quality_metrics: dict[str, MetricsSummary] = Field(default_factory=dict)
    performance_metrics: dict[str, MetricsSummary] = Field(default_factory=dict)
    business_metrics: dict[str, MetricsSummary] = Field(default_factory=dict)

    # Alerts and issues
    active_alerts: list[Alert] = Field(default_factory=list)
    alert_summary: dict[str, int] = Field(default_factory=dict)
    top_issues: list[dict[str, Any]] = Field(default_factory=list)

    # Trends and insights
    key_insights: list[str] = Field(default_factory=list)
    trend_analysis: dict[str, str] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)

    # Statistics
    total_conversations: int = Field(default=0)
    successful_conversations: int = Field(default=0)
    avg_response_time: float = Field(default=0.0)
    agent_usage_stats: dict[str, int] = Field(default_factory=dict)


# Default monitoring configuration
DEFAULT_MONITORING_CONFIG = {
    "dashboard_refresh_interval": 300,  # 5 minutes
    "alert_check_interval": 60,  # 1 minute
    "metric_retention_hours": 168,  # 1 week
    "max_alerts": 50,
    "auto_resolve_alerts": True,
    "alert_cooldown_minutes": 15,
}
