"""
Aynux Monitor.

Single Responsibility: Orchestrate monitoring workflow using composition.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from app.config.langsmith_config import get_tracer
from app.evaluation.metrics import get_metrics_collector

from .alert_manager import AlertManager
from .health_calculator import HealthCalculator
from .insights_generator import InsightsGenerator
from .schemas import (
    DEFAULT_MONITORING_CONFIG,
    Alert,
    AlertSeverity,
    DashboardData,
)

logger = logging.getLogger(__name__)


class AynuxMonitor:
    """
    Main monitoring and alerting system for Aynux.

    Uses composition:
    - AlertManager for alert lifecycle
    - HealthCalculator for health scoring
    - InsightsGenerator for insights and recommendations
    """

    def __init__(self):
        self.tracer = get_tracer()
        self.metrics_collector = get_metrics_collector()

        # Configuration
        self.monitoring_config = DEFAULT_MONITORING_CONFIG.copy()

        # Compose dependencies
        self._alert_manager = AlertManager(
            alert_thresholds=self.metrics_collector.thresholds,
            alert_cooldown_minutes=self.monitoring_config["alert_cooldown_minutes"],
            auto_resolve_alerts=self.monitoring_config["auto_resolve_alerts"],
        )
        self._health_calculator = HealthCalculator()
        self._insights_generator = InsightsGenerator()

        logger.info("Aynux monitoring system initialized")

    @property
    def active_alerts(self) -> dict[str, Alert]:
        """Get active alerts from manager."""
        return self._alert_manager.active_alerts

    @property
    def alert_history(self) -> list[Alert]:
        """Get alert history from manager."""
        return self._alert_manager.alert_history

    async def generate_dashboard(
        self,
        time_period_hours: int = 24,
        include_trends: bool = True,
        include_recommendations: bool = True,
    ) -> DashboardData:
        """Generate comprehensive dashboard data."""
        logger.info(f"Generating dashboard for last {time_period_hours} hours")

        try:
            # Collect all metrics concurrently
            routing_task = self.metrics_collector.collect_routing_metrics(
                time_period_hours
            )
            quality_task = self.metrics_collector.collect_quality_metrics(
                time_period_hours
            )
            performance_task = self.metrics_collector.collect_performance_metrics(
                time_period_hours
            )
            business_task = self.metrics_collector.collect_business_metrics(
                time_period_hours
            )

            (
                routing_metrics,
                quality_metrics,
                performance_metrics,
                business_metrics,
            ) = await asyncio.gather(
                routing_task, quality_task, performance_task, business_task
            )

            # Calculate overall health
            all_metrics = {
                **routing_metrics,
                **quality_metrics,
                **performance_metrics,
                **business_metrics,
            }
            health_score = self._health_calculator.calculate_health_score(all_metrics)
            system_status = self._health_calculator.determine_system_status(
                health_score, all_metrics
            )

            # Update alerts
            await self._alert_manager.update_alerts(all_metrics)
            active_alerts = list(self._alert_manager.active_alerts.values())

            # Generate insights and recommendations
            insights = (
                self._insights_generator.generate_insights(all_metrics)
                if include_trends
                else []
            )
            trend_analysis = (
                self._insights_generator.analyze_trends(all_metrics)
                if include_trends
                else {}
            )
            recommendations = (
                self._insights_generator.generate_recommendations(
                    all_metrics, active_alerts
                )
                if include_recommendations
                else []
            )

            # Get conversation statistics
            conversation_stats = await self._get_conversation_statistics(
                time_period_hours
            )

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
                alert_summary=self._alert_manager.summarize(active_alerts),
                top_issues=self._insights_generator.identify_top_issues(
                    all_metrics, active_alerts
                ),
                key_insights=insights,
                trend_analysis=trend_analysis,
                recommendations=recommendations,
                **conversation_stats,
            )

            logger.info(
                f"Dashboard generated with {len(all_metrics)} metrics "
                f"and {len(active_alerts)} alerts"
            )
            return dashboard

        except Exception as e:
            logger.error(f"Error generating dashboard: {e}")
            raise

    async def check_and_update_alerts(self) -> list[Alert]:
        """Check metrics against thresholds and update alerts."""
        try:
            # Get current metrics
            routing_metrics = await self.metrics_collector.collect_routing_metrics(1)
            quality_metrics = await self.metrics_collector.collect_quality_metrics(1)
            performance_metrics = (
                await self.metrics_collector.collect_performance_metrics(1)
            )
            business_metrics = await self.metrics_collector.collect_business_metrics(1)

            all_metrics = {
                **routing_metrics,
                **quality_metrics,
                **performance_metrics,
                **business_metrics,
            }

            new_alerts = await self._alert_manager.update_alerts(all_metrics)

            if new_alerts:
                logger.info(f"Generated {len(new_alerts)} new alerts")

                # Send notifications for critical alerts
                critical_alerts = [
                    alert
                    for alert in new_alerts
                    if alert.severity == AlertSeverity.CRITICAL
                ]
                if critical_alerts:
                    await self._send_critical_notifications(critical_alerts)

            return new_alerts

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
            return []

    async def get_alert_details(self, alert_id: str) -> Alert | None:
        """Get detailed information about a specific alert."""
        return self._alert_manager.active_alerts.get(alert_id)

    async def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str = "system"
    ) -> bool:
        """Acknowledge an active alert."""
        return await self._alert_manager.acknowledge_alert(alert_id, acknowledged_by)

    async def resolve_alert(
        self, alert_id: str, resolved_by: str = "system"
    ) -> bool:
        """Resolve an active alert."""
        return await self._alert_manager.resolve_alert(alert_id, resolved_by)

    async def get_alert_history(
        self,
        hours: int = 24,
        severity: AlertSeverity | None = None,
        limit: int = 100,
    ) -> list[Alert]:
        """Get alert history with optional filtering."""
        return await self._alert_manager.get_history(hours, severity, limit)

    async def _get_conversation_statistics(self, _: int) -> dict[str, Any]:
        """Get conversation statistics for the dashboard."""
        return {
            "total_conversations": 0,
            "successful_conversations": 0,
            "avg_response_time": 0.0,
            "agent_usage_stats": {},
        }

    async def _send_critical_notifications(self, alerts: list[Alert]):
        """Send notifications for critical alerts."""
        for alert in alerts:
            logger.critical(f"CRITICAL ALERT: {alert.title} - {alert.description}")

    def get_monitoring_status(self) -> dict[str, Any]:
        """Get current monitoring system status."""
        return {
            "monitoring_active": True,
            "last_check": datetime.now().isoformat(),
            "active_alerts_count": len(self._alert_manager.active_alerts),
            "alert_history_count": len(self._alert_manager.alert_history),
            "config": self.monitoring_config,
            "langsmith_connected": self.tracer.client is not None,
        }


# Global singleton instance
_monitor_instance: AynuxMonitor | None = None


def get_monitor() -> AynuxMonitor:
    """Get a singleton instance of AynuxMonitor."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = AynuxMonitor()
    return _monitor_instance
