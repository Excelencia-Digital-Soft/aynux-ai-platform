"""
Metrics collection and analysis for LangSmith evaluation in Aynux.

This module provides comprehensive metrics collection, analysis, and reporting
for the multi-agent conversation system performance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langsmith.schemas import Run
from pydantic import BaseModel, Field

from app.config.langsmith_config import get_tracer

logger = logging.getLogger(__name__)


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


@dataclass
class MetricValue:
    """A single metric measurement."""

    timestamp: datetime
    value: float
    metadata: Dict[str, Any]


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

    threshold_status: str = Field(default="ok", description="Status vs thresholds: ok, warning, critical")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")


class AynuxMetrics:
    """Comprehensive metrics collection and analysis for Aynux."""

    def __init__(self):
        self.tracer = get_tracer()
        self.client = self.tracer.client if self.tracer.client else None

        # Metric thresholds and targets
        self.thresholds = {
            # Routing metrics
            "intent_routing_accuracy": {"warning": 0.85, "critical": 0.75, "target": 0.95},
            "agent_selection_accuracy": {"warning": 0.80, "critical": 0.70, "target": 0.90},
            "routing_confidence": {"warning": 0.70, "critical": 0.60, "target": 0.85},
            # Quality metrics
            "response_quality_score": {"warning": 0.75, "critical": 0.65, "target": 0.85},
            "task_completion_rate": {"warning": 0.80, "critical": 0.70, "target": 0.90},
            "conversation_success_rate": {"warning": 0.85, "critical": 0.75, "target": 0.92},
            # Performance metrics
            "average_response_time": {"warning": 3.0, "critical": 5.0, "target": 2.0},  # seconds
            "p95_response_time": {"warning": 5.0, "critical": 8.0, "target": 3.0},
            "error_rate": {"warning": 0.05, "critical": 0.10, "target": 0.02},
            # Business metrics
            "customer_satisfaction": {"warning": 0.70, "critical": 0.60, "target": 0.85},
            "conversion_potential": {"warning": 0.15, "critical": 0.10, "target": 0.25},
            "escalation_rate": {"warning": 0.15, "critical": 0.25, "target": 0.08},
        }

        logger.info("AynuxMetrics initialized")

    async def collect_routing_metrics(
        self, time_period_hours: int = 24, project_name: Optional[str] = None
    ) -> Dict[str, MetricsSummary]:
        """
        Collect and analyze intent routing and agent selection metrics.

        Args:
            time_period_hours: Hours to look back for analysis
            project_name: LangSmith project name to analyze

        Returns:
            Dictionary of routing metrics summaries
        """
        if not self.client:
            logger.error("LangSmith client not available")
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            # Get runs from the specified time period
            runs = list(
                self.client.list_runs(project_name=project, start_time=start_time, end_time=end_time, limit=1000)
            )

            if not runs:
                logger.warning(f"No runs found in the last {time_period_hours} hours")
                return {}

            metrics = {}

            # Intent routing accuracy
            routing_data = self._analyze_routing_accuracy(runs)
            metrics["intent_routing_accuracy"] = self._create_metric_summary(
                "intent_routing_accuracy", MetricType.ROUTING, f"{time_period_hours}h", routing_data
            )

            # Agent selection accuracy
            agent_data = self._analyze_agent_selection(runs)
            metrics["agent_selection_accuracy"] = self._create_metric_summary(
                "agent_selection_accuracy", MetricType.ROUTING, f"{time_period_hours}h", agent_data
            )

            # Routing confidence
            confidence_data = self._analyze_routing_confidence(runs)
            metrics["routing_confidence"] = self._create_metric_summary(
                "routing_confidence", MetricType.ROUTING, f"{time_period_hours}h", confidence_data
            )

            logger.info(f"Collected routing metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting routing metrics: {e}")
            return {}

    async def collect_quality_metrics(
        self, time_period_hours: int = 24, project_name: Optional[str] = None
    ) -> Dict[str, MetricsSummary]:
        """
        Collect and analyze response quality and task completion metrics.
        """
        if not self.client:
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(project_name=project, start_time=start_time, end_time=end_time, limit=1000)
            )

            if not runs:
                return {}

            metrics = {}

            # Response quality score
            quality_data = self._analyze_response_quality(runs)
            metrics["response_quality_score"] = self._create_metric_summary(
                "response_quality_score", MetricType.QUALITY, f"{time_period_hours}h", quality_data
            )

            # Task completion rate
            completion_data = self._analyze_task_completion(runs)
            metrics["task_completion_rate"] = self._create_metric_summary(
                "task_completion_rate", MetricType.QUALITY, f"{time_period_hours}h", completion_data
            )

            # Conversation success rate
            success_data = self._analyze_conversation_success(runs)
            metrics["conversation_success_rate"] = self._create_metric_summary(
                "conversation_success_rate", MetricType.QUALITY, f"{time_period_hours}h", success_data
            )

            logger.info(f"Collected quality metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting quality metrics: {e}")
            return {}

    async def collect_performance_metrics(
        self, time_period_hours: int = 24, project_name: Optional[str] = None
    ) -> Dict[str, MetricsSummary]:
        """
        Collect and analyze system performance metrics.
        """
        if not self.client:
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(project_name=project, start_time=start_time, end_time=end_time, limit=1000)
            )

            if not runs:
                return {}

            metrics = {}

            # Response time metrics
            response_time_data = self._analyze_response_times(runs)
            metrics["average_response_time"] = self._create_metric_summary(
                "average_response_time", MetricType.PERFORMANCE, f"{time_period_hours}h", response_time_data["average"]
            )
            metrics["p95_response_time"] = self._create_metric_summary(
                "p95_response_time", MetricType.PERFORMANCE, f"{time_period_hours}h", response_time_data["p95"]
            )

            # Error rate
            error_data = self._analyze_error_rates(runs)
            metrics["error_rate"] = self._create_metric_summary(
                "error_rate", MetricType.PERFORMANCE, f"{time_period_hours}h", error_data
            )

            logger.info(f"Collected performance metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {}

    async def collect_business_metrics(
        self, time_period_hours: int = 24, project_name: Optional[str] = None
    ) -> Dict[str, MetricsSummary]:
        """
        Collect and analyze business-relevant metrics.
        """
        if not self.client:
            return {}

        project = project_name or self.tracer.config.project_name
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_period_hours)

        try:
            runs = list(
                self.client.list_runs(project_name=project, start_time=start_time, end_time=end_time, limit=1000)
            )

            if not runs:
                return {}

            metrics = {}

            # Customer satisfaction
            satisfaction_data = self._analyze_customer_satisfaction(runs)
            metrics["customer_satisfaction"] = self._create_metric_summary(
                "customer_satisfaction", MetricType.BUSINESS, f"{time_period_hours}h", satisfaction_data
            )

            # Conversion potential
            conversion_data = self._analyze_conversion_potential(runs)
            metrics["conversion_potential"] = self._create_metric_summary(
                "conversion_potential", MetricType.BUSINESS, f"{time_period_hours}h", conversion_data
            )

            # Human escalation rate
            escalation_data = self._analyze_escalation_rates(runs)
            metrics["escalation_rate"] = self._create_metric_summary(
                "escalation_rate", MetricType.BUSINESS, f"{time_period_hours}h", escalation_data
            )

            logger.info(f"Collected business metrics for {len(runs)} runs")
            return metrics

        except Exception as e:
            logger.error(f"Error collecting business metrics: {e}")
            return {}

    async def get_comprehensive_dashboard(self, time_period_hours: int = 24) -> Dict[str, Any]:
        """
        Get comprehensive metrics dashboard data.

        Returns:
            Dashboard data with all metrics categories
        """
        logger.info(f"Generating comprehensive dashboard for last {time_period_hours} hours")

        # Collect all metrics types
        routing_metrics = await self.collect_routing_metrics(time_period_hours)
        quality_metrics = await self.collect_quality_metrics(time_period_hours)
        performance_metrics = await self.collect_performance_metrics(time_period_hours)
        business_metrics = await self.collect_business_metrics(time_period_hours)

        # Combine all metrics
        all_metrics = {**routing_metrics, **quality_metrics, **performance_metrics, **business_metrics}

        # Calculate overall system health score
        health_score = self._calculate_overall_health(all_metrics)

        # Identify top issues and recommendations
        issues = self._identify_top_issues(all_metrics)
        recommendations = self._generate_recommendations(all_metrics)

        dashboard = {
            "dashboard_generated_at": datetime.now().isoformat(),
            "time_period_hours": time_period_hours,
            "overall_health_score": health_score,
            "metrics_by_category": {
                "routing": routing_metrics,
                "quality": quality_metrics,
                "performance": performance_metrics,
                "business": business_metrics,
            },
            "top_issues": issues,
            "recommendations": recommendations,
            "alert_count": len([m for m in all_metrics.values() if m.threshold_status in ["warning", "critical"]]),
        }

        logger.info(f"Dashboard generated with {len(all_metrics)} metrics")
        return dashboard

    # ============================================================================
    # ANALYSIS HELPER METHODS
    # ============================================================================

    def _analyze_routing_accuracy(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze intent routing accuracy from runs."""
        values = []
        for run in runs:
            if hasattr(run, "feedback_stats") and run.feedback_stats:
                # Look for routing accuracy feedback
                feedback = run.feedback_stats.get("routing_accuracy")
                if feedback and feedback.get("score") is not None:
                    values.append(
                        MetricValue(
                            timestamp=run.end_time or run.start_time,
                            value=float(feedback["score"]),
                            metadata={"run_id": run.id, "feedback": feedback},
                        )
                    )
            else:
                # Infer from run outputs if no explicit feedback
                outputs = run.outputs or {}
                expected_agent = outputs.get("expected_agent")
                actual_agent = outputs.get("next_agent") or outputs.get("current_agent")

                if expected_agent and actual_agent:
                    accuracy = 1.0 if expected_agent == actual_agent else 0.0
                    values.append(
                        MetricValue(
                            timestamp=run.end_time or run.start_time,
                            value=accuracy,
                            metadata={"run_id": run.id, "inferred": True},
                        )
                    )

        return values

    def _analyze_agent_selection(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze agent selection accuracy."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            agent_used = outputs.get("current_agent")

            if agent_used:
                # Simple heuristic: non-fallback agents indicate good selection
                accuracy = 0.9 if agent_used != "fallback_agent" else 0.3
                values.append(
                    MetricValue(
                        timestamp=run.end_time or run.start_time,
                        value=accuracy,
                        metadata={"run_id": run.id, "agent": agent_used},
                    )
                )

        return values

    def _analyze_routing_confidence(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze routing confidence scores."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            routing_decision = outputs.get("routing_decision", {})
            confidence = routing_decision.get("confidence")

            if confidence is not None:
                values.append(
                    MetricValue(
                        timestamp=run.end_time or run.start_time,
                        value=float(confidence),
                        metadata={"run_id": run.id, "decision": routing_decision},
                    )
                )

        return values

    def _analyze_response_quality(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze response quality scores."""
        values = []
        for run in runs:
            if hasattr(run, "feedback_stats") and run.feedback_stats:
                quality_feedback = run.feedback_stats.get("response_quality")
                if quality_feedback and quality_feedback.get("score") is not None:
                    values.append(
                        MetricValue(
                            timestamp=run.end_time or run.start_time,
                            value=float(quality_feedback["score"]),
                            metadata={"run_id": run.id, "feedback": quality_feedback},
                        )
                    )

        return values

    def _analyze_task_completion(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze task completion rates."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            is_complete = outputs.get("is_complete", False)
            human_handoff = outputs.get("human_handoff_requested", False)

            # Calculate completion score
            if is_complete and not human_handoff:
                score = 1.0
            elif is_complete and human_handoff:
                score = 0.7
            elif human_handoff:
                score = 0.3
            else:
                score = 0.5

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=score,
                    metadata={"run_id": run.id, "is_complete": is_complete, "human_handoff": human_handoff},
                )
            )

        return values

    def _analyze_conversation_success(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze overall conversation success rates."""
        values = []
        for run in runs:
            outputs = run.outputs or {}
            is_complete = outputs.get("is_complete", False)
            has_error = run.error is not None
            agent_used = outputs.get("current_agent", "")

            # Success criteria
            success = is_complete and not has_error and agent_used not in ["fallback_agent"]

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=1.0 if success else 0.0,
                    metadata={
                        "run_id": run.id,
                        "success_factors": {
                            "complete": is_complete,
                            "no_error": not has_error,
                            "good_agent": agent_used not in ["fallback_agent"],
                        },
                    },
                )
            )

        return values

    def _analyze_response_times(self, runs: List[Run]) -> Dict[str, List[MetricValue]]:
        """Analyze response time metrics."""
        response_times = []

        for run in runs:
            if run.end_time and run.start_time:
                duration_seconds = (run.end_time - run.start_time).total_seconds()
                response_times.append(
                    MetricValue(timestamp=run.end_time, value=duration_seconds, metadata={"run_id": run.id})
                )

        if not response_times:
            return {"average": [], "p95": []}

        # Calculate average and P95
        sorted_times = sorted([rt.value for rt in response_times])
        avg_time = sum(sorted_times) / len(sorted_times)
        p95_index = int(len(sorted_times) * 0.95)
        p95_time = sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]

        return {
            "average": [
                MetricValue(timestamp=datetime.now(), value=avg_time, metadata={"sample_size": len(response_times)})
            ],
            "p95": [
                MetricValue(timestamp=datetime.now(), value=p95_time, metadata={"sample_size": len(response_times)})
            ],
        }

    def _analyze_error_rates(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze error rates."""
        total_runs = len(runs)
        error_runs = len([run for run in runs if run.error is not None])
        error_rate = error_runs / total_runs if total_runs > 0 else 0.0

        return [
            MetricValue(
                timestamp=datetime.now(),
                value=error_rate,
                metadata={"total_runs": total_runs, "error_runs": error_runs},
            )
        ]

    def _analyze_customer_satisfaction(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze inferred customer satisfaction."""
        values = []
        for run in runs:
            # Infer satisfaction from various indicators
            outputs = run.outputs or {}
            processing_time = (
                (run.end_time - run.start_time).total_seconds() if run.end_time and run.start_time else 5.0
            )
            is_complete = outputs.get("is_complete", False)
            agent_transitions = len(outputs.get("agent_history", []))

            # Calculate satisfaction score
            time_score = 1.0 if processing_time < 3.0 else (0.5 if processing_time < 6.0 else 0.2)
            completion_score = 1.0 if is_complete else 0.3
            routing_score = 1.0 if agent_transitions <= 1 else (0.7 if agent_transitions <= 2 else 0.4)

            satisfaction = (time_score + completion_score + routing_score) / 3

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=satisfaction,
                    metadata={
                        "run_id": run.id,
                        "factors": {
                            "response_time": processing_time,
                            "completed": is_complete,
                            "transitions": agent_transitions,
                        },
                    },
                )
            )

        return values

    def _analyze_conversion_potential(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze conversion potential scores."""
        values = []
        for run in runs:
            inputs = run.inputs or {}
            outputs = run.outputs or {}

            user_message = inputs.get("message", "").lower()
            agent_used = outputs.get("current_agent", "")

            # Look for buying signals
            buying_keywords = ["comprar", "precio", "costo", "cuanto", "oferta", "descuento"]
            buying_signals = sum(1 for keyword in buying_keywords if keyword in user_message)

            # Calculate conversion potential
            if agent_used in ["product_agent", "smart_product_agent"] and buying_signals > 0:
                potential = min(1.0, 0.4 + (buying_signals * 0.2))
            elif agent_used == "promotions_agent":
                potential = 0.6
            else:
                potential = 0.1

            values.append(
                MetricValue(
                    timestamp=run.end_time or run.start_time,
                    value=potential,
                    metadata={"run_id": run.id, "agent_used": agent_used, "buying_signals": buying_signals},
                )
            )

        return values

    def _analyze_escalation_rates(self, runs: List[Run]) -> List[MetricValue]:
        """Analyze human escalation rates."""
        total_conversations = len(runs)
        escalated_conversations = len(
            [run for run in runs if (run.outputs or {}).get("human_handoff_requested", False)]
        )

        escalation_rate = escalated_conversations / total_conversations if total_conversations > 0 else 0.0

        return [
            MetricValue(
                timestamp=datetime.now(),
                value=escalation_rate,
                metadata={
                    "total_conversations": total_conversations,
                    "escalated_conversations": escalated_conversations,
                },
            )
        ]

    def _create_metric_summary(
        self, metric_name: str, metric_type: MetricType, time_period: str, values: List[MetricValue]
    ) -> MetricsSummary:
        """Create a metric summary from collected values."""
        if not values:
            return MetricsSummary(
                metric_name=metric_name,
                metric_type=metric_type,
                time_period=time_period,
                current_value=0.0,
                average_value=0.0,
                min_value=0.0,
                max_value=0.0,
                sample_count=0,
                trend=MetricTrend.UNKNOWN,
                trend_confidence=0.0,
                threshold_status="unknown",
            )

        # Calculate statistics
        metric_values = [v.value for v in values]
        current_value = values[-1].value
        average_value = sum(metric_values) / len(metric_values)
        min_value = min(metric_values)
        max_value = max(metric_values)

        # Calculate trend
        trend, trend_confidence = self._calculate_trend(values)

        # Determine threshold status
        threshold_status = self._get_threshold_status(metric_name, current_value)

        # Generate recommendations
        recommendations = self._generate_metric_recommendations(metric_name, current_value, threshold_status, trend)

        return MetricsSummary(
            metric_name=metric_name,
            metric_type=metric_type,
            time_period=time_period,
            current_value=current_value,
            average_value=average_value,
            min_value=min_value,
            max_value=max_value,
            sample_count=len(values),
            trend=trend,
            trend_confidence=trend_confidence,
            threshold_status=threshold_status,
            recommendations=recommendations,
        )

    def _calculate_trend(self, values: List[MetricValue]) -> Tuple[MetricTrend, float]:
        """Calculate trend direction and confidence."""
        if len(values) < 2:
            return MetricTrend.UNKNOWN, 0.0

        # Simple linear trend calculation
        n = len(values)
        recent_half = values[n // 2 :]
        early_half = values[: n // 2] if n > 2 else values[:1]

        if not recent_half or not early_half:
            return MetricTrend.UNKNOWN, 0.0

        recent_avg = sum(v.value for v in recent_half) / len(recent_half)
        early_avg = sum(v.value for v in early_half) / len(early_half)

        change = recent_avg - early_avg
        change_percentage = abs(change) / (early_avg if early_avg != 0 else 1.0)

        # Determine trend
        if abs(change) < 0.02:  # Less than 2% change
            trend = MetricTrend.STABLE
        elif change > 0:
            trend = MetricTrend.IMPROVING
        else:
            trend = MetricTrend.DECLINING

        # Confidence based on change magnitude and sample size
        confidence = min(1.0, change_percentage * 2 + (n / 20))

        return trend, confidence

    def _get_threshold_status(self, metric_name: str, value: float) -> str:
        """Determine threshold status for a metric value."""
        thresholds = self.thresholds.get(metric_name)
        if not thresholds:
            return "ok"

        if value < thresholds["critical"]:
            return "critical"
        elif value < thresholds["warning"]:
            return "warning"
        else:
            return "ok"

    def _generate_metric_recommendations(
        self, metric_name: str, value: float, status: str, trend: MetricTrend
    ) -> List[str]:
        """Generate specific recommendations for a metric."""
        recommendations = []

        if status == "critical":
            recommendations.append(f"🚨 CRITICAL: {metric_name} is below acceptable threshold")
        elif status == "warning":
            recommendations.append(f"⚠️ WARNING: {metric_name} needs attention")

        if trend == MetricTrend.DECLINING:
            recommendations.append(f"📉 {metric_name} is trending downward - investigate causes")

        # Metric-specific recommendations
        if metric_name == "intent_routing_accuracy" and value < 0.85:
            recommendations.extend(
                [
                    "Review intent classification training data",
                    "Analyze misrouted conversations for patterns",
                    "Consider updating routing thresholds",
                ]
            )
        elif metric_name == "response_quality_score" and value < 0.75:
            recommendations.extend(
                [
                    "Review and update agent prompts",
                    "Analyze low-quality responses for improvement",
                    "Consider additional training examples",
                ]
            )
        elif metric_name == "average_response_time" and value > 3.0:
            recommendations.extend(
                [
                    "Optimize database queries and API calls",
                    "Consider caching frequently accessed data",
                    "Review agent processing efficiency",
                ]
            )

        return recommendations

    def _calculate_overall_health(self, metrics: Dict[str, MetricsSummary]) -> float:
        """Calculate overall system health score."""
        if not metrics:
            return 0.0

        # Weight different metric types
        weights = {
            MetricType.ROUTING: 0.3,
            MetricType.QUALITY: 0.3,
            MetricType.PERFORMANCE: 0.2,
            MetricType.BUSINESS: 0.2,
        }

        weighted_scores = []
        for metric in metrics.values():
            weight = weights.get(metric.metric_type, 0.1)

            # Penalize metrics with issues
            score = metric.current_value
            if metric.threshold_status == "warning":
                score *= 0.8
            elif metric.threshold_status == "critical":
                score *= 0.5

            weighted_scores.append(score * weight)

        return sum(weighted_scores) / sum(weights.values()) if weighted_scores else 0.0

    def _identify_top_issues(self, metrics: Dict[str, MetricsSummary]) -> List[Dict[str, Any]]:
        """Identify the most critical issues from metrics."""
        issues = []

        for metric in metrics.values():
            if metric.threshold_status in ["warning", "critical"]:
                severity = "high" if metric.threshold_status == "critical" else "medium"

                issues.append(
                    {
                        "metric": metric.metric_name,
                        "severity": severity,
                        "current_value": metric.current_value,
                        "trend": metric.trend.value,
                        "description": f"{metric.metric_name} is {metric.threshold_status}",
                        "impact": self._assess_issue_impact(metric),
                    }
                )

        # Sort by severity and impact
        issues.sort(key=lambda x: (x["severity"] == "high", x["impact"]), reverse=True)
        return issues[:5]  # Top 5 issues

    def _assess_issue_impact(self, metric: MetricsSummary) -> str:
        """Assess the business impact of a metric issue."""
        impact_map = {
            "intent_routing_accuracy": "Customer experience degradation",
            "response_quality_score": "Poor customer satisfaction",
            "average_response_time": "User experience impact",
            "error_rate": "System reliability concerns",
            "conversion_potential": "Revenue impact",
            "escalation_rate": "Support team workload increase",
        }
        return impact_map.get(metric.metric_name, "System performance impact")

    def _generate_recommendations(self, metrics: Dict[str, MetricsSummary]) -> List[str]:
        """Generate high-level system recommendations."""
        recommendations = []

        # Collect all metric recommendations
        all_recs = []
        for metric in metrics.values():
            all_recs.extend(metric.recommendations)

        # Deduplicate and prioritize
        unique_recs = list(set(all_recs))

        # Add system-level recommendations
        if any(m.threshold_status == "critical" for m in metrics.values()):
            recommendations.append("🚨 System requires immediate attention - multiple critical metrics")

        if any(m.trend == MetricTrend.DECLINING for m in metrics.values()):
            recommendations.append("📉 Monitor system trends - performance declining")

        recommendations.extend(unique_recs[:8])  # Top recommendations
        return recommendations


# Global singleton instance
_metrics_instance: Optional[AynuxMetrics] = None


def get_metrics_collector() -> AynuxMetrics:
    """Get a singleton instance of AynuxMetrics."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = AynuxMetrics()
    return _metrics_instance
