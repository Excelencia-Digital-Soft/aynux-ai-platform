"""
Excelencia API Routes

FastAPI router for Excelencia Software domain endpoints.

Note: Demo scheduling and module browsing features are planned but not yet implemented.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/excelencia", tags=["Excelencia Software"])


# TODO: Implement these endpoints when use cases are ready
# - GET /modules - List available ERP modules
# - POST /demo - Schedule a demo session
# - GET /demo/slots - Get available demo slots


@router.get("/health")
async def health_check():
    """Health check endpoint for Excelencia domain."""
    return {"status": "ok", "domain": "excelencia"}


__all__ = ["router"]
