"""
FastAPI routes for LangSmith monitoring and evaluation endpoints.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.monitoring.langsmith_dashboard import (
    LangSmithMonitoringDashboard,
    PerformanceMetrics,
    AgentMetrics,
    QualityMetrics,
    Alert
)
from app.evaluation.langsmith_evaluators import (
    LangSmithEvaluationRunner,
    ConversationQualityEvaluator
)
from app.config.langsmith_config import get_tracer

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/langsmith", tags=["LangSmith Monitoring"])

# Initialize dashboard (will be singleton)
_dashboard: Optional[LangSmithMonitoringDashboard] = None


def get_dashboard() -> LangSmithMonitoringDashboard:
    """Get or create dashboard instance."""
    global _dashboard
    if _dashboard is None:
        _dashboard = LangSmithMonitoringDashboard()
    return _dashboard


# Response models
class DashboardResponse(BaseModel):
    """Dashboard data response model."""
    timestamp: str = Field(description="When the data was generated")
    period_hours: int = Field(description="Time period for the metrics")
    performance: Dict[str, Any] = Field(description="Performance metrics")
    agents: List[Dict[str, Any]] = Field(description="Agent-specific metrics")
    quality: Dict[str, Any] = Field(description="Quality metrics")
    alerts: Dict[str, Any] = Field(description="Alert information")
    health_status: str = Field(description="Overall system health")
    recommendations: List[str] = Field(description="Actionable recommendations")


class EvaluationRequest(BaseModel):
    """Request model for running evaluations."""
    message: str = Field(description="Message to evaluate")
    expected_response: Optional[str] = Field(None, description="Expected response")
    agent_used: Optional[str] = Field(None, description="Agent that processed the message")
    conversation_id: Optional[str] = Field(None, description="Conversation ID")


class EvaluationResponse(BaseModel):
    """Response model for evaluation results."""
    accuracy: float = Field(description="Response accuracy score")
    relevance: float = Field(description="Response relevance score")
    helpfulness: float = Field(description="Response helpfulness score")
    coherence: float = Field(description="Response coherence score")
    agent_routing_accuracy: float = Field(description="Agent routing accuracy score")
    business_value: float = Field(description="Business value score")
    overall_score: float = Field(description="Overall quality score")


class TracingStatusResponse(BaseModel):
    """Response model for tracing status."""
    enabled: bool = Field(description="Whether tracing is enabled")
    project_name: str = Field(description="LangSmith project name")
    api_configured: bool = Field(description="Whether API is configured")
    sample_rate: float = Field(description="Trace sampling rate")


# Routes
@router.get("/status", response_model=TracingStatusResponse)
async def get_tracing_status():
    """Get current LangSmith tracing status."""
    try:
        tracer = get_tracer()
        
        return TracingStatusResponse(
            enabled=tracer.config.tracing_enabled,
            project_name=tracer.config.project_name,
            api_configured=bool(tracer.config.api_key),
            sample_rate=tracer.config.trace_sample_rate
        )
        
    except Exception as e:
        logger.error(f"Error getting tracing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_data(
    hours_back: int = Query(24, description="Hours to look back for metrics", ge=1, le=168)
):
    """Get comprehensive dashboard data."""
    try:
        dashboard = get_dashboard()
        data = await dashboard.generate_dashboard_data(hours_back=hours_back)
        
        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])
        
        return DashboardResponse(**data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/performance")
async def get_performance_metrics(
    hours_back: int = Query(24, description="Hours to look back", ge=1, le=168)
) -> Dict[str, Any]:
    """Get performance metrics only."""
    try:
        dashboard = get_dashboard()
        metrics = await dashboard.get_performance_metrics(hours_back=hours_back)
        
        return metrics.to_dict()
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/agents")
async def get_agent_metrics(
    hours_back: int = Query(24, description="Hours to look back", ge=1, le=168)
) -> List[Dict[str, Any]]:
    """Get agent-specific metrics."""
    try:
        dashboard = get_dashboard()
        metrics = await dashboard.get_agent_metrics(hours_back=hours_back)
        
        return [metric.to_dict() for metric in metrics]
        
    except Exception as e:
        logger.error(f"Error getting agent metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/quality")
async def get_quality_metrics(
    hours_back: int = Query(24, description="Hours to look back", ge=1, le=168),
    sample_size: int = Query(100, description="Sample size for evaluation", ge=10, le=500)
) -> Dict[str, Any]:
    """Get quality metrics."""
    try:
        dashboard = get_dashboard()
        metrics = await dashboard.get_quality_metrics(
            hours_back=hours_back, 
            sample_size=sample_size
        )
        
        return metrics.to_dict()
        
    except Exception as e:
        logger.error(f"Error getting quality metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, description="Maximum number of alerts to return", ge=1, le=200)
) -> List[Dict[str, Any]]:
    """Get system alerts."""
    try:
        dashboard = get_dashboard()
        alerts = dashboard.alerts
        
        # Filter alerts
        if resolved is not None:
            alerts = [alert for alert in alerts if alert.resolved == resolved]
        
        # Limit results
        alerts = alerts[-limit:] if limit else alerts
        
        return [alert.dict() for alert in alerts]
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve a specific alert."""
    try:
        dashboard = get_dashboard()
        success = dashboard.resolve_alert(alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"message": "Alert resolved successfully", "alert_id": alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_response(request: EvaluationRequest):
    """Evaluate a single response for quality metrics."""
    try:
        evaluator = ConversationQualityEvaluator()
        
        # Prepare context
        context = {}
        if request.agent_used:
            context["agent_used"] = request.agent_used
        if request.conversation_id:
            context["conversation_id"] = request.conversation_id
        
        # Run evaluation
        metrics = evaluator.evaluate_response_quality(
            input_message=request.message,
            actual_response="",  # Would be provided in real scenario
            expected_response=request.expected_response,
            context=context
        )
        
        return EvaluationResponse(
            accuracy=metrics.accuracy,
            relevance=metrics.relevance,
            helpfulness=metrics.helpfulness,
            coherence=metrics.coherence,
            agent_routing_accuracy=metrics.agent_routing_accuracy,
            business_value=metrics.business_value,
            overall_score=metrics.overall_score()
        )
        
    except Exception as e:
        logger.error(f"Error evaluating response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_health_status():
    """Get overall system health status."""
    try:
        dashboard = get_dashboard()
        
        # Get quick metrics for health calculation
        performance_metrics = await dashboard.get_performance_metrics(hours_back=1)
        quality_metrics = await dashboard.get_quality_metrics(hours_back=1, sample_size=10)
        
        # Calculate health status
        health_status = dashboard._calculate_health_status(performance_metrics, quality_metrics)
        
        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "performance": {
                "success_rate": performance_metrics.success_rate,
                "error_rate": performance_metrics.error_rate,
                "avg_response_time": performance_metrics.avg_response_time
            },
            "quality": {
                "overall_score": quality_metrics.overall_quality_score
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/csv")
async def export_metrics_csv(
    hours_back: int = Query(24, description="Hours to look back", ge=1, le=168),
    filepath: Optional[str] = Query(None, description="Custom file path")
):
    """Export metrics to CSV file."""
    try:
        dashboard = get_dashboard()
        
        # Use default filename if not provided
        if not filepath:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filepath = f"/tmp/conversashop_metrics_{timestamp}.csv"
        
        success = await dashboard.export_metrics_to_csv(filepath, hours_back=hours_back)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to export metrics")
        
        return {
            "message": "Metrics exported successfully",
            "filepath": filepath,
            "hours_back": hours_back
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/traces/recent")
async def get_recent_traces(
    limit: int = Query(10, description="Number of recent traces", ge=1, le=100),
    run_type: Optional[str] = Query(None, description="Filter by run type")
):
    """Get recent traces from LangSmith."""
    try:
        tracer = get_tracer()
        
        if not tracer.client:
            raise HTTPException(status_code=503, detail="LangSmith client not available")
        
        # Get recent runs
        runs = list(tracer.client.list_runs(
            project_name=tracer.config.project_name,
            run_type=run_type,
            limit=limit
        ))
        
        # Format response
        traces = []
        for run in runs:
            trace_data = {
                "id": str(run.id),
                "name": run.name,
                "run_type": run.run_type,
                "start_time": run.start_time.isoformat() if run.start_time else None,
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "latency": run.latency,
                "error": run.error,
                "inputs": run.inputs,
                "outputs": run.outputs,
            }
            traces.append(trace_data)
        
        return {
            "traces": traces,
            "total": len(traces),
            "project": tracer.config.project_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Add router to main application
# This would be done in main.py or wherever you configure your FastAPI app
def include_langsmith_routes(app):
    """Include LangSmith routes in the main FastAPI app."""
    app.include_router(router)