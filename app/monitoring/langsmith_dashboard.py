"""
LangSmith monitoring dashboard and alerting system for Aynux.

This module provides real-time monitoring, alerting, and dashboard capabilities
for the multi-agent conversation system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config.langsmith_config import get_tracer
from app.evaluation.langsmith_evaluators import get_evaluators_instance
from app.evaluation.metrics import MetricsSummary, MetricTrend, get_metrics_collector

logger = logging.getLogger(__name__)


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
    metric_name: str = Field(..., description="Name of the metric that triggered the alert")
    severity: AlertSeverity = Field(..., description="Alert severity level")
    status: AlertStatus = Field(default=AlertStatus.ACTIVE, description="Current alert status")

    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Detailed alert description")
    current_value: float = Field(..., description="Current metric value")
    threshold_value: float = Field(..., description="Threshold that was breached")

    triggered_at: datetime = Field(..., description="When the alert was first triggered")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    acknowledged_at: Optional[datetime] = Field(None, description="When alert was acknowledged")
    resolved_at: Optional[datetime] = Field(None, description="When alert was resolved")

    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional alert context")
    recommendations: List[str] = Field(default_factory=list, description="Recommended actions")


class DashboardData(BaseModel):
    """Complete dashboard data structure."""

    generated_at: datetime = Field(default_factory=datetime.now, description="Dashboard generation timestamp")
    time_period_hours: int = Field(default=24, description="Time period covered by metrics")

    # System overview
    overall_health_score: float = Field(..., description="Overall system health (0-1)")
    system_status: str = Field(..., description="System status: healthy, degraded, critical")

    # Metrics by category
    routing_metrics: Dict[str, MetricsSummary] = Field(default_factory=dict)
    quality_metrics: Dict[str, MetricsSummary] = Field(default_factory=dict)
    performance_metrics: Dict[str, MetricsSummary] = Field(default_factory=dict)
    business_metrics: Dict[str, MetricsSummary] = Field(default_factory=dict)

    # Alerts and issues
    active_alerts: List[Alert] = Field(default_factory=list)
    alert_summary: Dict[str, int] = Field(default_factory=dict)
    top_issues: List[Dict[str, Any]] = Field(default_factory=list)

    # Trends and insights
    key_insights: List[str] = Field(default_factory=list)
    trend_analysis: Dict[str, str] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)

    # Statistics
    total_conversations: int = Field(default=0)
    successful_conversations: int = Field(default=0)
    avg_response_time: float = Field(default=0.0)
    agent_usage_stats: Dict[str, int] = Field(default_factory=dict)


class AynuxMonitor:
    """Main monitoring and alerting system for Aynux."""

    def __init__(self):
        self.tracer = get_tracer()
        self.metrics_collector = get_metrics_collector()
        self.evaluators = get_evaluators_instance()

        # Alert management
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []

        # Monitoring configuration
        self.monitoring_config = {
            "dashboard_refresh_interval": 300,  # 5 minutes
            "alert_check_interval": 60,  # 1 minute
            "metric_retention_hours": 168,  # 1 week
            "max_alerts": 50,
            "auto_resolve_alerts": True,
            "alert_cooldown_minutes": 15,
        }

        # Alert thresholds (inherited from metrics collector)
        self.alert_thresholds = self.metrics_collector.thresholds

        logger.info("Aynux monitoring system initialized")

    async def generate_dashboard(
        self, time_period_hours: int = 24, include_trends: bool = True, include_recommendations: bool = True
    ) -> DashboardData:
        """
        Generate comprehensive dashboard data.

        Args:
            time_period_hours: Time period to analyze
            include_trends: Whether to include trend analysis
            include_recommendations: Whether to include recommendations

        Returns:
            Complete dashboard data structure
        """
        logger.info(f"Generating dashboard for last {time_period_hours} hours")

        try:
            # Collect all metrics concurrently
            routing_task = self.metrics_collector.collect_routing_metrics(time_period_hours)
            quality_task = self.metrics_collector.collect_quality_metrics(time_period_hours)
            performance_task = self.metrics_collector.collect_performance_metrics(time_period_hours)
            business_task = self.metrics_collector.collect_business_metrics(time_period_hours)

            routing_metrics, quality_metrics, performance_metrics, business_metrics = await asyncio.gather(
                routing_task, quality_task, performance_task, business_task
            )

            # Calculate overall health
            all_metrics = {**routing_metrics, **quality_metrics, **performance_metrics, **business_metrics}
            health_score = self._calculate_health_score(all_metrics)
            system_status = self._determine_system_status(health_score, all_metrics)

            # Get active alerts
            await self._update_alerts(all_metrics)
            active_alerts = list(self.active_alerts.values())

            # Generate insights and recommendations
            insights = self._generate_insights(all_metrics) if include_trends else []
            trend_analysis = self._analyze_trends(all_metrics) if include_trends else {}
            recommendations = (
                self._generate_recommendations(all_metrics, active_alerts) if include_recommendations else []
            )

            # Get conversation statistics
            conversation_stats = await self._get_conversation_statistics(time_period_hours)

            dashboard = DashboardData(
                generated_at=datetime.now(),
                time_period_hours=time_period_hours,
                overall_health_score=health_score,
                system_status=system_status,
                routing_metrics=routing_metrics,
                quality_metrics=quality_metrics,
                performance_metrics=performance_metrics,
                business_metrics=business_metrics,
                active_alerts=active_alerts,
                alert_summary=self._summarize_alerts(active_alerts),
                top_issues=self._identify_top_issues(all_metrics, active_alerts),
                key_insights=insights,
                trend_analysis=trend_analysis,
                recommendations=recommendations,
                **conversation_stats,
            )

            logger.info(f"Dashboard generated with {len(all_metrics)} metrics and {len(active_alerts)} alerts")
            return dashboard

        except Exception as e:
            logger.error(f"Error generating dashboard: {e}")
            raise

    async def check_and_update_alerts(self) -> List[Alert]:
        """
        Check metrics against thresholds and update alerts.

        Returns:
            List of new or updated alerts
        """
        try:
            # Get current metrics
            routing_metrics = await self.metrics_collector.collect_routing_metrics(1)  # Last hour
            quality_metrics = await self.metrics_collector.collect_quality_metrics(1)
            performance_metrics = await self.metrics_collector.collect_performance_metrics(1)
            business_metrics = await self.metrics_collector.collect_business_metrics(1)

            all_metrics = {**routing_metrics, **quality_metrics, **performance_metrics, **business_metrics}

            new_alerts = await self._update_alerts(all_metrics)

            if new_alerts:
                logger.info(f"Generated {len(new_alerts)} new alerts")

                # Send notifications for critical alerts
                critical_alerts = [alert for alert in new_alerts if alert.severity == AlertSeverity.CRITICAL]
                if critical_alerts:
                    await self._send_critical_notifications(critical_alerts)

            return new_alerts

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            return []

    async def get_alert_details(self, alert_id: str) -> Optional[Alert]:
        """Get detailed information about a specific alert."""
        return self.active_alerts.get(alert_id)

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        """
        Acknowledge an active alert.

        Args:
            alert_id: ID of the alert to acknowledge
            acknowledged_by: Who acknowledged the alert

        Returns:
            True if successful, False otherwise
        """
        alert = self.active_alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        alert.metadata["acknowledged_by"] = acknowledged_by

        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True

    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """
        Resolve an active alert.

        Args:
            alert_id: ID of the alert to resolve
            resolved_by: Who resolved the alert

        Returns:
            True if successful, False otherwise
        """
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

    async def get_alert_history(
        self, hours: int = 24, severity: Optional[AlertSeverity] = None, limit: int = 100
    ) -> List[Alert]:
        """
        Get alert history with optional filtering.

        Args:
            hours: Hours to look back
            severity: Filter by severity level
            limit: Maximum number of alerts to return

        Returns:
            List of historical alerts
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        filtered_alerts = [
            alert
            for alert in self.alert_history
            if alert.triggered_at >= cutoff_time and (severity is None or alert.severity == severity)
        ]

        # Sort by triggered time (most recent first)
        filtered_alerts.sort(key=lambda x: x.triggered_at, reverse=True)

        return filtered_alerts[:limit]

    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================

    def _calculate_health_score(self, metrics: Dict[str, MetricsSummary]) -> float:
        """Calculate overall system health score from metrics."""
        if not metrics:
            return 0.0

        # Weight different metric categories
        category_weights = {"routing": 0.25, "quality": 0.30, "performance": 0.25, "business": 0.20}

        category_scores = {}

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
                weight = category_weights.get(category, 0.1)
                total_weighted_score += category_avg * weight
                total_weight += weight

        return total_weighted_score / total_weight if total_weight > 0 else 0.0

    def _determine_system_status(self, health_score: float, metrics: Dict[str, MetricsSummary]) -> str:
        """Determine overall system status."""
        critical_count = sum(1 for m in metrics.values() if m.threshold_status == "critical")
        warning_count = sum(1 for m in metrics.values() if m.threshold_status == "warning")

        if critical_count > 0 or health_score < 0.6:
            return "critical"
        elif warning_count > 2 or health_score < 0.8:
            return "degraded"
        else:
            return "healthy"

    async def _update_alerts(self, metrics: Dict[str, MetricsSummary]) -> List[Alert]:
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
                    cooldown_period = timedelta(minutes=self.monitoring_config["alert_cooldown_minutes"])
                    if current_time - existing_alert.updated_at < cooldown_period:
                        continue  # Skip if in cooldown

                    # Update existing alert
                    existing_alert.current_value = metric.current_value
                    existing_alert.updated_at = current_time
                    continue

                # Create new alert
                severity = AlertSeverity.CRITICAL if metric.threshold_status == "critical" else AlertSeverity.WARNING
                threshold_value = self.alert_thresholds.get(metric_name, {}).get(metric.threshold_status, 0.0)

                alert = Alert(
                    id=alert_id,
                    metric_name=metric_name,
                    severity=severity,
                    title=f"{metric_name.replace('_', ' ').title()} {metric.threshold_status.title()}",
                    description=self._generate_alert_description(metric_name, metric, threshold_value),
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
                if self.monitoring_config["auto_resolve_alerts"]:
                    alerts_to_resolve.append(alert_id)

        for alert_id in alerts_to_resolve:
            await self.resolve_alert(alert_id, "auto_resolved")

        return new_alerts

    def _generate_alert_description(self, metric_name: str, metric: MetricsSummary, threshold: float) -> str:
        """Generate a descriptive alert message."""
        descriptions = {
            "intent_routing_accuracy": f"Intent routing accuracy has dropped to {metric.current_value:.1%}, below the\
                {threshold:.1%} threshold. This may cause poor user experience due to incorrect agent routing.",
            "response_quality_score": f"Response quality score is {metric.current_value:.2f}, below the {threshold:.2f}\
                threshold. This indicates responses may not be meeting user expectations.",
            "average_response_time": f"Average response time is {metric.current_value:.1f}s, above the {threshold:.1f}s\
                threshold. Users may experience slow responses.",
            "error_rate": f"Error rate is {metric.current_value:.1%}, above the {threshold:.1%} threshold. \
                System reliability is compromised.",
            "customer_satisfaction": f"Customer satisfaction score is {metric.current_value:.2f}, below the\
                {threshold:.2f} threshold. User experience may be degraded.",
        }

        return descriptions.get(
            metric_name, f"{metric_name} is {metric.current_value:.2f}, which violates the {threshold:.2f} threshold."
        )

    def _summarize_alerts(self, alerts: List[Alert]) -> Dict[str, int]:
        """Summarize alert counts by severity."""
        summary = {"critical": 0, "warning": 0, "info": 0, "total": len(alerts)}

        for alert in alerts:
            summary[alert.severity.value] += 1

        return summary

    def _identify_top_issues(self, metrics: Dict[str, MetricsSummary], alerts: List[Alert]) -> List[Dict[str, Any]]:
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
                        "recommendations": alert.recommendations[:3],  # Top 3 recommendations
                    }
                )

        # Add declining trend issues
        declining_metrics = [
            m for m in metrics.values() if m.trend == MetricTrend.DECLINING and m.trend_confidence > 0.6
        ]

        for metric in declining_metrics[:3]:  # Top 3 declining metrics
            issues.append(
                {
                    "type": "declining_trend",
                    "title": f"{metric.metric_name.replace('_', ' ').title()} Declining",
                    "description": f"This metric has been declining with {metric.trend_confidence:.1%} confidence",
                    "metric": metric.metric_name,
                    "impact": "medium",
                    "recommendations": metric.recommendations[:2],
                }
            )

        return issues[:5]  # Return top 5 issues

    def _generate_insights(self, metrics: Dict[str, MetricsSummary]) -> List[str]:
        """Generate key insights from metrics analysis."""
        insights = []

        # Performance insights
        response_time = metrics.get("average_response_time")
        if response_time and response_time.current_value < 2.0:
            insights.append("💚 System response times are excellent (< 2s average)")
        elif response_time and response_time.current_value > 5.0:
            insights.append("🔴 Response times are concerning - investigate performance bottlenecks")

        # Quality insights
        quality_score = metrics.get("response_quality_score")
        if quality_score and quality_score.current_value > 0.85:
            insights.append("⭐ Response quality is high - users receiving excellent service")
        elif quality_score and quality_score.trend == MetricTrend.IMPROVING:
            insights.append("📈 Response quality is improving - recent optimizations showing results")

        # Routing insights
        routing_accuracy = metrics.get("intent_routing_accuracy")
        if routing_accuracy and routing_accuracy.current_value > 0.95:
            insights.append("🎯 Intent routing is highly accurate - minimal misrouted conversations")

        # Business insights
        conversion = metrics.get("conversion_potential")
        satisfaction = metrics.get("customer_satisfaction")

        if conversion and satisfaction:
            if conversion.current_value > 0.2 and satisfaction.current_value > 0.8:
                insights.append("💼 Strong business metrics - high conversion potential with satisfied customers")

        return insights[:6]  # Top insights

    def _analyze_trends(self, metrics: Dict[str, MetricsSummary]) -> Dict[str, str]:
        """Analyze trends across different metric categories."""
        trends = {}

        for category in ["routing", "quality", "performance", "business"]:
            category_metrics = [m for m in metrics.values() if m.metric_type.value == category]
            if not category_metrics:
                continue

            improving = sum(1 for m in category_metrics if m.trend == MetricTrend.IMPROVING)
            declining = sum(1 for m in category_metrics if m.trend == MetricTrend.DECLINING)
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

    def _generate_recommendations(self, metrics: Dict[str, MetricsSummary], alerts: List[Alert]) -> List[str]:
        """Generate high-level recommendations based on metrics and alerts."""
        recommendations = set()

        # Add recommendations from critical alerts
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                recommendations.update(alert.recommendations[:2])  # Top 2 per alert

        # Add recommendations from declining metrics
        for metric in metrics.values():
            if metric.trend == MetricTrend.DECLINING and metric.trend_confidence > 0.7:
                recommendations.update(metric.recommendations[:1])  # Top 1 per declining metric

        # System-level recommendations
        critical_count = len([a for a in alerts if a.severity == AlertSeverity.CRITICAL])
        if critical_count > 0:
            recommendations.add("🚨 Address critical alerts immediately to restore system health")

        warning_count = len([a for a in alerts if a.severity == AlertSeverity.WARNING])
        if warning_count > 3:
            recommendations.add("⚠️ Multiple warnings detected - schedule maintenance window")

        return list(recommendations)[:8]  # Top 8 recommendations

    async def _get_conversation_statistics(self, _: int) -> Dict[str, Any]:
        """Get conversation statistics for the dashboard."""
        # This would typically query the LangSmith runs
        # For now, return mock data structure
        return {
            "total_conversations": 0,
            "successful_conversations": 0,
            "avg_response_time": 0.0,
            "agent_usage_stats": {},
        }

    async def _send_critical_notifications(self, alerts: List[Alert]):
        """Send notifications for critical alerts."""
        # Implementation would depend on notification channels (email, Slack, etc.)
        for alert in alerts:
            logger.critical(f"CRITICAL ALERT: {alert.title} - {alert.description}")
            # Could integrate with external notification services here

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring system status."""
        return {
            "monitoring_active": True,
            "last_check": datetime.now().isoformat(),
            "active_alerts_count": len(self.active_alerts),
            "alert_history_count": len(self.alert_history),
            "config": self.monitoring_config,
            "langsmith_connected": self.tracer.client is not None,
        }


# Global singleton instance
_monitor_instance: Optional[AynuxMonitor] = None


def get_monitor() -> AynuxMonitor:
    """Get a singleton instance of AynuxMonitor."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = AynuxMonitor()
    return _monitor_instance
