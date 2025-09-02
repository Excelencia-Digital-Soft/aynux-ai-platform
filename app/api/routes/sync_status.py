"""
Endpoints para verificar el estado de sincronización de productos DUX
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.config.settings import get_settings
from app.services.scheduled_sync_service import get_scheduled_sync_service

router = APIRouter()


@router.get("/sync/status", response_model=Dict[str, Any])
async def get_sync_status():
    """
    Obtiene el estado actual de la sincronización de productos DUX.

    Returns:
        Dict con información del estado de sincronización
    """
    try:
        settings = get_settings()
        sync_service = get_scheduled_sync_service()

        status = await sync_service.get_sync_status()
        status["dux_sync_enabled"] = settings.DUX_SYNC_ENABLED

        return status

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting sync status: {str(e)}") from e


@router.post("/sync/force", response_model=Dict[str, Any])
async def force_sync():
    """
    Fuerza una sincronización inmediata de productos DUX.

    Returns:
        Dict con el resultado de la sincronización
    """
    try:
        settings = get_settings()

        if not settings.DUX_SYNC_ENABLED:
            raise HTTPException(
                status_code=400, detail="DUX sync is disabled. Set DUX_SYNC_ENABLED=true to enable synchronization"
            )

        sync_service = get_scheduled_sync_service()
        synced = await sync_service.force_sync_if_needed()

        return {
            "success": True,
            "sync_executed": synced,
            "message": "Sync completed successfully" if synced else "Sync not needed, data is recent",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error forcing sync: {str(e)}") from e

