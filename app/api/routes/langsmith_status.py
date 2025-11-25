"""
LangSmith status and debugging endpoints.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.config.langsmith_config import get_tracer
from app.config.langsmith_init import get_langsmith_status, initialize_langsmith

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/langsmith", tags=["monitoring"])


@router.get("/status")
async def get_tracing_status() -> Dict[str, Any]:
    """
    Get current LangSmith tracing status and configuration.

    Returns:
        Dictionary with LangSmith configuration and status
    """
    try:
        status = get_langsmith_status()

        # Add tracer status
        tracer = get_tracer()
        status["tracer"] = {
            "initialized": tracer is not None,
            "tracing_enabled": tracer.config.tracing_enabled if tracer else False,
            "project_name": tracer.config.project_name if tracer else None,
            "api_key_configured": bool(tracer.config.api_key) if tracer else False,
            "client_available": tracer.client is not None if tracer else False,
        }

        # Add recent runs info if client available
        if tracer and tracer.client:
            try:
                runs = list(tracer.client.list_runs(project_name=tracer.config.project_name, limit=5))

                status["recent_runs"] = {
                    "count": len(runs),
                    "latest": (
                        {
                            "id": str(runs[0].id) if runs else None,
                            "name": runs[0].name if runs else None,
                            "status": runs[0].status if runs else None,
                        }
                        if runs
                        else None
                    ),
                }
            except Exception as e:
                status["recent_runs"] = {"error": str(e)}

        return status

    except Exception as e:
        logger.error(f"Error getting LangSmith status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/initialize")
async def initialize_tracing(force: bool = False) -> Dict[str, Any]:
    """
    Initialize or reinitialize LangSmith tracing.

    Args:
        force: Force reinitialization even if already configured

    Returns:
        Status after initialization attempt
    """
    try:
        success = initialize_langsmith(force=force)

        if success:
            logger.info("LangSmith tracing initialized via API")
        else:
            logger.warning("LangSmith tracing initialization failed or disabled")

        # Return current status
        return {"success": success, "status": get_langsmith_status()}

    except Exception as e:
        logger.error(f"Error initializing LangSmith: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/test-trace")
async def test_trace() -> Dict[str, Any]:
    """
    Create a test trace to verify LangSmith is working.

    Returns:
        Test trace result
    """
    try:
        import time

        from langsmith import traceable

        tracer = get_tracer()

        if not tracer or not tracer.config.tracing_enabled:
            return {"success": False, "message": "LangSmith tracing is not enabled", "status": get_langsmith_status()}

        @traceable(name="test_api_trace", run_type="chain", project_name=tracer.config.project_name)
        async def test_function(message: str) -> str:
            """Test function for tracing."""
            await asyncio.sleep(0.1)
            return f"Processed: {message}"

        # Run test function
        import asyncio

        test_message = f"Test trace at {time.time()}"
        result = await test_function(test_message)

        return {
            "success": True,
            "message": "Test trace created successfully",
            "test_result": result,
            "project": tracer.config.project_name,
            "dashboard_url": "https://smith.langchain.com",
            "note": "Check your LangSmith dashboard for the trace",
        }

    except Exception as e:
        logger.error(f"Error creating test trace: {e}")
        return {"success": False, "error": str(e), "status": get_langsmith_status()}


@router.get("/metrics")
async def get_tracing_metrics() -> Dict[str, Any]:
    """
    Get LangSmith metrics for the project.

    Returns:
        Project metrics from LangSmith
    """
    try:
        tracer = get_tracer()

        if not tracer or not tracer.client:
            return {"error": "LangSmith client not available", "status": get_langsmith_status()}

        metrics = tracer.get_metrics()

        return {
            "project": tracer.config.project_name,
            "metrics": metrics,
            "dashboard_url": f"https://smith.langchain.com/o/{tracer.config.project_name}",
        }

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
