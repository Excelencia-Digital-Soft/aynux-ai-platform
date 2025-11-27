"""
Metrics Data Models.

Shared models and enums for the metrics system.
"""

from enum import Enum

from pydantic import BaseModel, Field


class MetricType(Enum):
    """Types of metrics collected."""

    ROUTING = "routing"
    QUALITY = "quality"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    TECHNICAL = "technical"


class MetricTrend(Enum):
    """Trend directions for metrics."""

    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    UNKNOWN = "unknown"


class MetricsSummary(BaseModel):
    """Summary statistics for a metric over a time period."""

    metric_name: str = Field(..., description="Name of the metric")
    metric_type: MetricType = Field(..., description="Category of metric")
    time_period: str = Field(..., description="Time period analyzed")

    current_value: float = Field(..., description="Most recent metric value")
    average_value: float = Field(..., description="Average value over period")
    min_value: float = Field(..., description="Minimum value in period")
    max_value: float = Field(..., description="Maximum value in period")

    sample_count: int = Field(..., description="Number of data points")
    trend: MetricTrend = Field(..., description="Trend direction")
    trend_confidence: float = Field(..., description="Confidence in trend (0-1)")

    threshold_status: str = Field(
        default="ok", description="Status vs thresholds: ok, warning, critical"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )
