"""
API endpoints para administración de sincronización DUX-RAG
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.settings import get_settings
from app.services.scheduled_sync_service import get_scheduled_sync_service

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class SyncRequest(BaseModel):
    """Modelo para solicitudes de sincronización forzada"""

    max_products: Optional[int] = None
    sync_type: str = "full"  # "full", "products_only", "embeddings_only"
    dry_run: bool = False


class SyncResponse(BaseModel):
    """Modelo para respuestas de sincronización"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@router.get("/sync/status", response_model=Dict[str, Any])
async def get_sync_status():
    """
    Obtiene el estado completo del sistema de sincronización DUX-RAG

    Returns:
        Dict con información detallada del estado de sincronización
    """
    try:
        sync_service = get_scheduled_sync_service()
        status = await sync_service.get_sync_status()

        return {"success": True, "data": status, "timestamp": status.get("last_check", "unknown")}

    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sync/force", response_model=SyncResponse)
async def force_sync(request: SyncRequest):
    """
    Fuerza una sincronización inmediata

    Args:
        request: Parámetros de sincronización

    Returns:
        SyncResponse con resultado de la operación
    """
    if not settings.DUX_SYNC_ENABLED:
        raise HTTPException(status_code=400, detail="DUX sync is disabled via configuration")

    try:
        sync_service = get_scheduled_sync_service()

        if request.sync_type == "products_only" or request.sync_type == "full":
            logger.info(f"Forcing products sync - max: {request.max_products}, dry_run: {request.dry_run}")

            if request.dry_run:
                # Para dry run, usar el servicio directo para no tocar embeddings
                if sync_service.use_rag_sync:
                    result = await sync_service.rag_sync_service.sync_all_products_with_rag(
                        max_products=request.max_products, dry_run=True
                    )
                else:
                    result = await sync_service.sync_service.sync_all_products(
                        max_products=request.max_products, dry_run=True
                    )

                return SyncResponse(
                    success=result.success,
                    message=f"Dry run completed - {result.total_processed} products would be processed",
                    data={
                        "would_process": result.total_processed,
                        "duration_seconds": result.duration_seconds,
                        "errors": result.errors,
                    },
                )
            else:
                result = await sync_service.force_products_sync(max_products=request.max_products)

                return SyncResponse(
                    success=result.get("success", False),
                    message=f"Products sync completed - {result.get('processed', 0)} processed",
                    data=result,
                )

        elif request.sync_type == "embeddings_only":
            if not sync_service.use_rag_sync:
                raise HTTPException(status_code=400, detail="RAG sync is disabled - cannot update embeddings only")

            logger.info("Forcing embeddings update")
            result = await sync_service.force_embeddings_update()

            return SyncResponse(
                success=result.get("success", False),
                message="Embeddings update completed" if result.get("success") else "Embeddings update failed",
                data=result,
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sync_type: {request.sync_type}. Must be 'full', 'products_only', or 'embeddings_only'",
            )

    except Exception as e:
        logger.error(f"Error during forced sync: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sync/health", response_model=Dict[str, Any])
async def sync_health_check():
    """
    Verifica la salud del sistema de sincronización

    Returns:
        Dict con estado de salud de los componentes
    """
    try:
        health_status = {"overall_status": "healthy", "components": {}, "issues": []}

        # Verificar servicio de sincronización
        sync_service = get_scheduled_sync_service()
        sync_status = await sync_service.get_sync_status()

        health_status["components"]["scheduled_sync"] = {
            "status": "healthy" if sync_status["is_running"] else "stopped",
            "mode": sync_status["sync_mode"],
            "last_sync": sync_status.get("last_sync_time"),
            "hours_since_update": sync_status.get("hours_since_update"),
        }

        # Verificar conectividad API DUX
        if settings.DUX_API_KEY:
            try:
                from app.clients.dux_api_client import DuxApiClientFactory

                async with DuxApiClientFactory.create_client() as client:
                    api_healthy = await client.test_connection()

                health_status["components"]["dux_api"] = {"status": "healthy" if api_healthy else "unhealthy"}

                if not api_healthy:
                    health_status["issues"].append("DUX API connectivity failed")

            except Exception as e:
                health_status["components"]["dux_api"] = {"status": "error", "error": str(e)}
                health_status["issues"].append(f"DUX API error: {e}")
        else:
            health_status["components"]["dux_api"] = {"status": "disabled", "reason": "DUX_API_KEY not configured"}
            health_status["issues"].append("DUX API key not configured")

        # Verificar RAG/embeddings si está habilitado
        if sync_service.use_rag_sync:
            try:
                from app.services.embedding_update_service import EmbeddingUpdateService

                embedding_service = EmbeddingUpdateService()

                stats = embedding_service.get_collection_stats()
                total_embeddings = sum(stats.values())

                health_status["components"]["rag_system"] = {
                    "status": "healthy" if total_embeddings > 0 else "empty",
                    "collections": stats,
                    "total_embeddings": total_embeddings,
                }

                if total_embeddings == 0:
                    health_status["issues"].append("No embeddings found in vector store")

            except Exception as e:
                health_status["components"]["rag_system"] = {"status": "error", "error": str(e)}
                health_status["issues"].append(f"RAG system error: {e}")
        else:
            health_status["components"]["rag_system"] = {"status": "disabled", "reason": "RAG sync is disabled"}

        # Determinar estado general
        if health_status["issues"]:
            if any("error" in issue.lower() for issue in health_status["issues"]):
                health_status["overall_status"] = "unhealthy"
            else:
                health_status["overall_status"] = "degraded"

        return health_status

    except Exception as e:
        logger.error(f"Error during health check: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/sync/metrics", response_model=Dict[str, Any])
async def get_sync_metrics():
    """
    Obtiene métricas detalladas del sistema de sincronización

    Returns:
        Dict con métricas de rendimiento y uso
    """
    try:
        sync_service = get_scheduled_sync_service()
        status = await sync_service.get_sync_status()

        metrics = {
            "sync_performance": {
                "mode": status["sync_mode"],
                "is_running": status["is_running"],
                "last_sync_results": status.get("last_sync_results", {}),
                "hours_since_update": status.get("hours_since_update"),
                "next_scheduled_sync": status.get("next_scheduled_sync"),
            },
            "configuration": {
                "sync_enabled": settings.DUX_SYNC_ENABLED,
                "sync_hours": settings.DUX_SYNC_HOURS,
                "batch_size": settings.DUX_SYNC_BATCH_SIZE,
                "force_sync_threshold_hours": settings.DUX_FORCE_SYNC_THRESHOLD_HOURS,
            },
            "rag_details": status.get("rag_details", {}),
        }

        # Agregar métricas de database si están disponibles
        try:
            from sqlalchemy import func, select

            from app.database.async_db import get_async_db_context
            from app.models.db import Product

            async with get_async_db_context() as db:
                # Contar productos totales
                total_result = await db.execute(select(func.count(Product.id)))
                total_products = total_result.scalar()

                # Productos activos
                active_result = await db.execute(select(func.count(Product.id)).where(Product.is_active))
                active_products = active_result.scalar()

                metrics["database_stats"] = {
                    "total_products": total_products or 0,
                    "active_products": active_products or 0,
                    "inactive_products": (total_products or 0) - (active_products or 0),
                }

        except Exception as e:
            logger.warning(f"Could not get database stats: {e}")
            metrics["database_stats"] = {"error": str(e)}

        return metrics

    except Exception as e:
        logger.error(f"Error getting sync metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

