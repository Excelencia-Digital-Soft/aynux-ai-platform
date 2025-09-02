"""
LangSmith monitoring dashboard and metrics collection for ConversaShop.
Provides real-time monitoring, alerting, and performance insights.
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import logging

from langsmith import Client
from langsmith.schemas import Run
import pandas as pd
from pydantic import BaseModel, Field

from app.config.langsmith_config import get_tracer, LangSmithConfig
from app.evaluation.langsmith_evaluators import ConversationQualityEvaluator

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container."""
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    success_rate: float
    error_rate: float
    total_requests: int
    requests_per_minute: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "avg_response_time": self.avg_response_time,
            "p95_response_time": self.p95_response_time,
            "p99_response_time": self.p99_response_time,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "total_requests": self.total_requests,
            "requests_per_minute": self.requests_per_minute,
        }


@dataclass
class AgentMetrics:
    """Agent-specific metrics."""
    agent_name: str
    usage_count: int
    success_rate: float
    avg_response_time: float
    routing_accuracy: float
    business_value_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "routing_accuracy": self.routing_accuracy,
            "business_value_score": self.business_value_score,
        }


@dataclass
class QualityMetrics:
    """Quality metrics container."""
    avg_accuracy: float
    avg_relevance: float
    avg_helpfulness: float
    avg_coherence: float
    overall_quality_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "avg_accuracy": self.avg_accuracy,
            "avg_relevance": self.avg_relevance,
            "avg_helpfulness": self.avg_helpfulness,
            "avg_coherence": self.avg_coherence,
            "overall_quality_score": self.overall_quality_score,
        }


class Alert(BaseModel):
    """Alert model."""
    id: str = Field(description="Unique alert identifier")
    level: str = Field(description="Alert level: info, warning, error, critical")
    title: str = Field(description="Alert title")
    message: str = Field(description="Alert message")
    metric: str = Field(description="Metric that triggered the alert")
    value: float = Field(description="Current metric value")
    threshold: float = Field(description="Threshold that was breached")
    timestamp: datetime = Field(description="When the alert was triggered")
    resolved: bool = Field(default=False, description="Whether the alert is resolved")


class LangSmithMonitoringDashboard:
    """
    Comprehensive monitoring dashboard for ConversaShop LangSmith integration.
    """
    
    def __init__(self, config: Optional[LangSmithConfig] = None):
        """Initialize monitoring dashboard."""
        self.tracer = get_tracer()
        self.config = config or self.tracer.config
        self.client = self.tracer.client
        self.evaluator = ConversationQualityEvaluator()
        self.alerts: List[Alert] = []
        
    async def get_performance_metrics(
        self, 
        hours_back: int = 24,
        project_name: Optional[str] = None
    ) -> PerformanceMetrics:
        """
        Get performance metrics for the specified time period.
        
        Args:
            hours_back: Hours to look back for metrics
            project_name: Project name (defaults to configured project)
            
        Returns:
            PerformanceMetrics object
        """
        if not self.client:
            logger.warning("LangSmith client not available")
            return PerformanceMetrics(0, 0, 0, 0, 1, 0, 0)
        
        try:
            # Get runs from the specified time period
            since = datetime.utcnow() - timedelta(hours=hours_back)
            project = project_name or self.config.project_name
            
            runs = list(self.client.list_runs(
                project_name=project,
                start_time=since,
                limit=1000  # Adjust based on needs
            ))
            
            if not runs:
                return PerformanceMetrics(0, 0, 0, 0, 1, 0, 0)
            
            # Calculate metrics
            response_times = [run.latency for run in runs if run.latency is not None]
            successful_runs = [run for run in runs if not run.error]
            total_requests = len(runs)
            successful_requests = len(successful_runs)
            
            # Performance calculations
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            sorted_times = sorted(response_times)
            p95_response_time = sorted_times[int(0.95 * len(sorted_times))] if sorted_times else 0
            p99_response_time = sorted_times[int(0.99 * len(sorted_times))] if sorted_times else 0
            
            success_rate = successful_requests / total_requests if total_requests > 0 else 0
            error_rate = 1 - success_rate
            requests_per_minute = total_requests / (hours_back * 60)
            
            return PerformanceMetrics(
                avg_response_time=avg_response_time,
                p95_response_time=p95_response_time,
                p99_response_time=p99_response_time,
                success_rate=success_rate,
                error_rate=error_rate,
                total_requests=total_requests,
                requests_per_minute=requests_per_minute
            )
            
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return PerformanceMetrics(0, 0, 0, 0, 1, 0, 0)
    
    async def get_agent_metrics(
        self, 
        hours_back: int = 24,
        project_name: Optional[str] = None
    ) -> List[AgentMetrics]:
        """
        Get metrics for individual agents.
        
        Args:
            hours_back: Hours to look back for metrics
            project_name: Project name (defaults to configured project)
            
        Returns:
            List of AgentMetrics objects
        """
        if not self.client:
            logger.warning("LangSmith client not available")
            return []
        
        try:
            # Get runs from the specified time period
            since = datetime.utcnow() - timedelta(hours=hours_back)
            project = project_name or self.config.project_name
            
            runs = list(self.client.list_runs(
                project_name=project,
                start_time=since,
                run_type="agent",  # Filter for agent runs
                limit=1000
            ))
            
            # Group runs by agent
            agent_runs = {}
            for run in runs:
                agent_name = run.name or "unknown"
                if agent_name not in agent_runs:
                    agent_runs[agent_name] = []
                agent_runs[agent_name].append(run)
            
            # Calculate metrics for each agent
            agent_metrics = []
            for agent_name, runs in agent_runs.items():
                if not runs:
                    continue
                
                successful_runs = [run for run in runs if not run.error]
                response_times = [run.latency for run in runs if run.latency is not None]
                
                usage_count = len(runs)
                success_rate = len(successful_runs) / usage_count if usage_count > 0 else 0
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0
                
                # Simplified routing accuracy and business value (would be enhanced with real data)
                routing_accuracy = 0.85  # Placeholder - would calculate from evaluation data
                business_value_score = 0.75  # Placeholder - would calculate from business metrics
                
                agent_metrics.append(AgentMetrics(
                    agent_name=agent_name,
                    usage_count=usage_count,
                    success_rate=success_rate,
                    avg_response_time=avg_response_time,
                    routing_accuracy=routing_accuracy,
                    business_value_score=business_value_score
                ))
            
            return agent_metrics
            
        except Exception as e:
            logger.error(f"Failed to get agent metrics: {e}")
            return []
    
    async def get_quality_metrics(
        self, 
        hours_back: int = 24,
        sample_size: int = 100,
        project_name: Optional[str] = None
    ) -> QualityMetrics:
        """
        Get quality metrics by evaluating recent conversations.
        
        Args:
            hours_back: Hours to look back for metrics
            sample_size: Number of conversations to sample for evaluation
            project_name: Project name (defaults to configured project)
            
        Returns:
            QualityMetrics object
        """
        if not self.client:
            logger.warning("LangSmith client not available")
            return QualityMetrics(0, 0, 0, 0, 0)
        
        try:
            # Get runs from the specified time period
            since = datetime.utcnow() - timedelta(hours=hours_back)
            project = project_name or self.config.project_name
            
            runs = list(self.client.list_runs(
                project_name=project,
                start_time=since,
                limit=sample_size * 2  # Get more than needed to filter
            ))
            
            # Filter runs with both inputs and outputs
            evaluable_runs = [
                run for run in runs 
                if run.inputs and run.outputs and 
                run.inputs.get("message") and run.outputs.get("response")
            ][:sample_size]
            
            if not evaluable_runs:
                return QualityMetrics(0, 0, 0, 0, 0)
            
            # Evaluate quality for each run
            quality_scores = []
            for run in evaluable_runs:
                try:
                    metrics = self.evaluator.evaluate_response_quality(
                        input_message=run.inputs.get("message", ""),
                        actual_response=run.outputs.get("response", ""),
                        context={
                            "agent_used": run.outputs.get("agent_used"),
                            "response_time_ms": run.latency,
                        }
                    )
                    quality_scores.append(metrics)
                except Exception as e:
                    logger.warning(f"Failed to evaluate run {run.id}: {e}")
            
            if not quality_scores:
                return QualityMetrics(0, 0, 0, 0, 0)
            
            # Calculate average quality metrics
            avg_accuracy = sum(m.accuracy for m in quality_scores) / len(quality_scores)
            avg_relevance = sum(m.relevance for m in quality_scores) / len(quality_scores)
            avg_helpfulness = sum(m.helpfulness for m in quality_scores) / len(quality_scores)
            avg_coherence = sum(m.coherence for m in quality_scores) / len(quality_scores)
            overall_quality_score = sum(m.overall_score() for m in quality_scores) / len(quality_scores)
            
            return QualityMetrics(
                avg_accuracy=avg_accuracy,
                avg_relevance=avg_relevance,
                avg_helpfulness=avg_helpfulness,
                avg_coherence=avg_coherence,
                overall_quality_score=overall_quality_score
            )
            
        except Exception as e:
            logger.error(f"Failed to get quality metrics: {e}")
            return QualityMetrics(0, 0, 0, 0, 0)
    
    async def check_alerts(
        self, 
        performance_metrics: PerformanceMetrics,
        quality_metrics: QualityMetrics
    ) -> List[Alert]:
        """
        Check metrics against thresholds and generate alerts.
        
        Args:
            performance_metrics: Performance metrics to check
            quality_metrics: Quality metrics to check
            
        Returns:
            List of new alerts
        """
        new_alerts = []
        current_time = datetime.utcnow()
        
        # Performance-based alerts
        if performance_metrics.error_rate > self.config.alert_thresholds.get("error_rate", 0.05):
            alert = Alert(
                id=f"error_rate_{current_time.isoformat()}",
                level="error",
                title="High Error Rate",
                message=f"Error rate ({performance_metrics.error_rate:.2%}) exceeds threshold",
                metric="error_rate",
                value=performance_metrics.error_rate,
                threshold=self.config.alert_thresholds.get("error_rate", 0.05),
                timestamp=current_time
            )
            new_alerts.append(alert)
        
        if performance_metrics.p95_response_time > self.config.alert_thresholds.get("latency_p95", 5000):
            alert = Alert(
                id=f"latency_p95_{current_time.isoformat()}",
                level="warning",
                title="High Response Time",
                message=f"P95 response time ({performance_metrics.p95_response_time:.0f}ms) exceeds threshold",
                metric="latency_p95",
                value=performance_metrics.p95_response_time,
                threshold=self.config.alert_thresholds.get("latency_p95", 5000),
                timestamp=current_time
            )
            new_alerts.append(alert)
        
        if performance_metrics.success_rate < self.config.alert_thresholds.get("success_rate", 0.95):
            alert = Alert(
                id=f"success_rate_{current_time.isoformat()}",
                level="error",
                title="Low Success Rate",
                message=f"Success rate ({performance_metrics.success_rate:.2%}) below threshold",
                metric="success_rate",
                value=performance_metrics.success_rate,
                threshold=self.config.alert_thresholds.get("success_rate", 0.95),
                timestamp=current_time
            )
            new_alerts.append(alert)
        
        # Quality-based alerts
        if quality_metrics.overall_quality_score < 0.7:
            alert = Alert(
                id=f"quality_score_{current_time.isoformat()}",
                level="warning",
                title="Low Quality Score",
                message=f"Overall quality score ({quality_metrics.overall_quality_score:.2f}) is low",
                metric="quality_score",
                value=quality_metrics.overall_quality_score,
                threshold=0.7,
                timestamp=current_time
            )
            new_alerts.append(alert)
        
        # Add new alerts to the alert list
        self.alerts.extend(new_alerts)
        
        return new_alerts
    
    async def generate_dashboard_data(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Generate comprehensive dashboard data.
        
        Args:
            hours_back: Hours to look back for metrics
            
        Returns:
            Dictionary with all dashboard data
        """
        try:
            # Gather all metrics concurrently
            performance_metrics, agent_metrics, quality_metrics = await asyncio.gather(
                self.get_performance_metrics(hours_back),
                self.get_agent_metrics(hours_back),
                self.get_quality_metrics(hours_back, sample_size=50)
            )
            
            # Check for alerts
            new_alerts = await self.check_alerts(performance_metrics, quality_metrics)
            
            # Get recent unresolved alerts
            recent_alerts = [
                alert for alert in self.alerts 
                if not alert.resolved and 
                (datetime.utcnow() - alert.timestamp).days < 7
            ]
            
            dashboard_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "period_hours": hours_back,
                "performance": performance_metrics.to_dict(),
                "agents": [agent.to_dict() for agent in agent_metrics],
                "quality": quality_metrics.to_dict(),
                "alerts": {
                    "new": [alert.dict() for alert in new_alerts],
                    "recent": [alert.dict() for alert in recent_alerts[-10:]],  # Last 10 alerts
                    "total_unresolved": len(recent_alerts)
                },
                "health_status": self._calculate_health_status(
                    performance_metrics, quality_metrics
                ),
                "recommendations": self._generate_recommendations(
                    performance_metrics, agent_metrics, quality_metrics
                )
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Failed to generate dashboard data: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def _calculate_health_status(
        self, 
        performance_metrics: PerformanceMetrics,
        quality_metrics: QualityMetrics
    ) -> str:
        """Calculate overall health status."""
        # Simple health calculation
        health_score = (
            performance_metrics.success_rate * 0.4 +
            (1 - performance_metrics.error_rate) * 0.3 +
            quality_metrics.overall_quality_score * 0.3
        )
        
        if health_score >= 0.9:
            return "healthy"
        elif health_score >= 0.75:
            return "degraded"
        elif health_score >= 0.5:
            return "unhealthy"
        else:
            return "critical"
    
    def _generate_recommendations(
        self,
        performance_metrics: PerformanceMetrics,
        agent_metrics: List[AgentMetrics],
        quality_metrics: QualityMetrics
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Performance recommendations
        if performance_metrics.error_rate > 0.05:
            recommendations.append(
                "High error rate detected. Review error logs and implement better error handling."
            )
        
        if performance_metrics.p95_response_time > 3000:
            recommendations.append(
                "Response times are high. Consider optimizing LLM calls and database queries."
            )
        
        # Agent recommendations
        if agent_metrics:
            low_success_agents = [
                agent for agent in agent_metrics 
                if agent.success_rate < 0.8
            ]
            if low_success_agents:
                agent_names = ", ".join(agent.agent_name for agent in low_success_agents)
                recommendations.append(
                    f"Low success rate for agents: {agent_names}. Review their implementation."
                )
        
        # Quality recommendations
        if quality_metrics.avg_accuracy < 0.7:
            recommendations.append(
                "Low accuracy scores. Review training data and improve prompt engineering."
            )
        
        if quality_metrics.avg_relevance < 0.7:
            recommendations.append(
                "Low relevance scores. Improve intent routing and context understanding."
            )
        
        return recommendations
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                return True
        return False
    
    async def export_metrics_to_csv(
        self, 
        filepath: str,
        hours_back: int = 24
    ) -> bool:
        """
        Export metrics to CSV file.
        
        Args:
            filepath: Path to save the CSV file
            hours_back: Hours of data to export
            
        Returns:
            True if successful, False otherwise
        """
        try:
            dashboard_data = await self.generate_dashboard_data(hours_back)
            
            # Convert to DataFrame for easy CSV export
            df_data = {
                "timestamp": [dashboard_data["timestamp"]],
                "period_hours": [dashboard_data["period_hours"]],
                "success_rate": [dashboard_data["performance"]["success_rate"]],
                "error_rate": [dashboard_data["performance"]["error_rate"]],
                "avg_response_time": [dashboard_data["performance"]["avg_response_time"]],
                "p95_response_time": [dashboard_data["performance"]["p95_response_time"]],
                "total_requests": [dashboard_data["performance"]["total_requests"]],
                "overall_quality": [dashboard_data["quality"]["overall_quality_score"]],
                "health_status": [dashboard_data["health_status"]],
                "active_alerts": [dashboard_data["alerts"]["total_unresolved"]]
            }
            
            df = pd.DataFrame(df_data)
            df.to_csv(filepath, index=False)
            
            logger.info(f"Metrics exported to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return False


# Export main classes
__all__ = [
    "LangSmithMonitoringDashboard",
    "PerformanceMetrics", 
    "AgentMetrics",
    "QualityMetrics",
    "Alert"
]