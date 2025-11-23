"""
Servicio de sincronización programada para productos DUX
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import func, select

from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.domains.ecommerce.infrastructure.services import DuxSyncService
from app.models.db import Product
from app.services.dux_rag_sync_service import create_dux_rag_sync_service

logger = logging.getLogger(__name__)


class SyncState(Enum):
    """Estados de sincronización."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledSyncService:
    """Servicio mejorado para programar y ejecutar sincronización completa DUX con RAG."""

    def __init__(self, use_rag_sync: bool = True):
        """
        Inicializa el servicio de sincronización programada

        Args:
            use_rag_sync: Si True, usa DuxRagSyncService (DB + embeddings),
                         si False usa solo DuxSyncService (solo DB)
        """
        self.settings = get_settings()
        self.use_rag_sync = use_rag_sync

        if self.use_rag_sync:
            self.rag_sync_service = create_dux_rag_sync_service(batch_size=self.settings.DUX_SYNC_BATCH_SIZE)
            self.sync_service = None
        else:
            self.sync_service = DuxSyncService(batch_size=self.settings.DUX_SYNC_BATCH_SIZE)
            self.rag_sync_service = None

        self.is_running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._last_sync_results: Dict[str, Dict] = {}

        # Estado de sincronización
        self._sync_state = SyncState.IDLE
        self._current_sync_task: Optional[asyncio.Task] = None
        self._sync_progress = {
            "total_items": 0,
            "processed_items": 0,
            "current_batch": 0,
            "total_batches": 0,
            "start_time": None,
            "estimated_completion": None,
            "error_message": None,
        }

    async def start(self):
        """Inicia el servicio de sincronización programada."""
        if self.is_running:
            logger.warning("Scheduled sync service is already running")
            return

        self.is_running = True
        self._sync_task = asyncio.create_task(self._run_scheduled_sync())
        logger.info("Scheduled sync service started")

    async def stop(self):
        """Detiene el servicio de sincronización programada."""
        self.is_running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduled sync service stopped")

    async def _run_scheduled_sync(self):
        """Ejecuta el ciclo de sincronización programada."""
        while self.is_running:
            try:
                current_hour = datetime.now().hour

                # Verificar si es hora de sincronizar
                if current_hour in self.settings.DUX_SYNC_HOURS:
                    # Verificar si ya sincronizamos en esta hora
                    last_sync_time = await self._get_last_sync_time()
                    if not last_sync_time or (datetime.now() - last_sync_time).total_seconds() > 3600:
                        logger.info(f"Starting scheduled sync at hour {current_hour}")
                        await self._execute_sync_with_state_management()

                # Esperar hasta el próximo chequeo (cada 30 minutos)
                await asyncio.sleep(1800)

            except Exception as e:
                logger.error(f"Error in scheduled sync loop: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto en caso de error

    async def force_sync_if_needed(self) -> bool:
        """
        Verifica si es necesario forzar una sincronización basada en la antigüedad de los datos.

        Returns:
            bool: True si se ejecutó la sincronización, False si no fue necesario
        """
        # Verificar si ya hay una sincronización en progreso
        if self._sync_state == SyncState.RUNNING:
            logger.warning("Sync already in progress, skipping force sync check")
            return False

        try:
            last_update = await self._get_most_recent_product_update()

            if not last_update:
                # No hay productos, sincronizar
                logger.info("No products in database, forcing sync")
                await self._execute_sync_with_state_management()
                return True

            hours_since_update = (datetime.now() - last_update).total_seconds() / 3600

            if hours_since_update > self.settings.DUX_FORCE_SYNC_THRESHOLD_HOURS:
                logger.info(f"Products are {hours_since_update:.1f} hours old, forcing sync")
                await self._execute_sync_with_state_management()
                return True

            logger.debug(f"Products are {hours_since_update:.1f} hours old, no sync needed")
            return False

        except Exception as e:
            logger.error(f"Error checking sync need: {e}")
            return False

    async def _execute_sync_with_state_management(self):
        """Wrapper que ejecuta sincronización con manejo de estado."""
        # Verificar si ya hay una sincronización en progreso
        if self._sync_state == SyncState.RUNNING:
            logger.warning("Sync already in progress, skipping")
            return

        try:
            # Inicializar estado
            self._sync_state = SyncState.RUNNING
            self._sync_progress["start_time"] = datetime.now()
            self._sync_progress["error_message"] = None

            # Crear y ejecutar task de sincronización
            self._current_sync_task = asyncio.create_task(self._execute_sync())
            await self._current_sync_task

            # Marcar como completado
            self._sync_state = SyncState.COMPLETED
            logger.info("✅ Sync completed successfully")

        except asyncio.CancelledError:
            self._sync_state = SyncState.CANCELLED
            logger.info("🚫 Sync was cancelled")
            raise
        except Exception as e:
            self._sync_state = SyncState.FAILED
            self._sync_progress["error_message"] = str(e)
            logger.error(f"❌ Sync failed: {e}")
            raise
        finally:
            self._current_sync_task = None

    async def _execute_sync(self):
        """Ejecuta la sincronización completa con DUX (productos + facturas)."""
        sync_start_time = datetime.now()

        try:
            logger.info("Starting comprehensive DUX synchronization...")

            # Sincronizar productos (con o sin RAG según configuración)
            if self.use_rag_sync:
                logger.info("Executing integrated DUX-RAG product sync...")
                products_result = await self.rag_sync_service.sync_all_products_with_rag()

                logger.info(
                    f"Products sync completed - DB: {products_result.total_processed} processed, "
                    f"{products_result.total_created} created, {products_result.total_updated} updated, "
                    f"{products_result.total_errors} errors | RAG: {products_result.total_embeddings_created} "
                    f"embeddings created, {products_result.total_embeddings_updated} updated"
                )
            else:
                logger.info("Executing traditional DUX product sync...")
                products_result = await self.sync_service.sync_all_products()

                logger.info(
                    f"Products sync completed - Processed: {products_result.total_processed}, "
                    f"Created: {products_result.total_created}, Updated: {products_result.total_updated}, "
                    f"Errors: {products_result.total_errors}"
                )

            # Guardar resultado de productos
            self._last_sync_results["products"] = {
                "timestamp": sync_start_time.isoformat(),
                "success": products_result.success,
                "processed": products_result.total_processed,
                "created": products_result.total_created,
                "updated": products_result.total_updated,
                "errors": products_result.total_errors,
                "duration_seconds": products_result.duration_seconds,
            }

            # Sincronizar facturas si está habilitada la sincronización RAG
            if self.use_rag_sync:
                try:
                    logger.info("Executing facturas sync...")
                    facturas_result = await self.rag_sync_service.sync_facturas_with_rag(limit=200)

                    logger.info(
                        f"Facturas sync completed - Processed: {facturas_result.total_processed}, "
                        f"Errors: {facturas_result.total_errors}"
                    )

                    # Guardar resultado de facturas
                    self._last_sync_results["facturas"] = {
                        "timestamp": sync_start_time.isoformat(),
                        "success": facturas_result.success,
                        "processed": facturas_result.total_processed,
                        "errors": facturas_result.total_errors,
                        "duration_seconds": facturas_result.duration_seconds,
                    }

                except Exception as e:
                    logger.error(f"Error during facturas sync: {e}")
                    self._last_sync_results["facturas"] = {
                        "timestamp": sync_start_time.isoformat(),
                        "success": False,
                        "error": str(e),
                    }

            # Guardar timestamp de última sincronización
            await self._save_sync_timestamp()

            total_duration = (datetime.now() - sync_start_time).total_seconds()
            logger.info(f"Comprehensive DUX sync completed in {total_duration:.2f}s")

        except Exception as e:
            logger.error(f"Error during sync execution: {e}")
            self._last_sync_results["products"] = {
                "timestamp": sync_start_time.isoformat(),
                "success": False,
                "error": str(e),
            }

    async def _get_last_sync_time(self) -> Optional[datetime]:
        """Obtiene el timestamp de la última sincronización."""
        # TODO: Implementar almacenamiento persistente del timestamp
        # Por ahora, usar la fecha de actualización más reciente de productos
        return await self._get_most_recent_product_update()

    async def _get_most_recent_product_update(self) -> Optional[datetime]:
        """Obtiene la fecha de actualización más reciente de productos."""
        try:
            async with get_async_db_context() as db:
                result = await db.execute(select(func.max(Product.updated_at)))
                return result.scalar()
        except Exception as e:
            logger.error(f"Error getting most recent product update: {e}")
            return None

    async def _save_sync_timestamp(self):
        """Guarda el timestamp de la sincronización actual."""
        # TODO: Implementar almacenamiento persistente
        # Por ahora, los productos se actualizan con updated_at automáticamente
        pass

    async def get_sync_status(self) -> dict:
        """Obtiene el estado completo de la sincronización."""
        last_sync = await self._get_last_sync_time()
        last_update = await self._get_most_recent_product_update()

        base_status = {
            "is_running": self.is_running,
            "sync_mode": "rag_integrated" if self.use_rag_sync else "database_only",
            "sync_hours": self.settings.DUX_SYNC_HOURS,
            "force_sync_threshold_hours": self.settings.DUX_FORCE_SYNC_THRESHOLD_HOURS,
            "last_sync_time": last_sync.isoformat() if last_sync else None,
            "last_product_update": last_update.isoformat() if last_update else None,
            "hours_since_update": ((datetime.now() - last_update).total_seconds() / 3600 if last_update else None),
            "next_scheduled_sync": self._get_next_scheduled_sync_time(),
            "last_sync_results": self._last_sync_results,
            "current_sync": self.get_current_sync_state(),
        }

        # Agregar estado detallado si usa RAG sync
        if self.use_rag_sync and self.rag_sync_service:
            try:
                rag_status = await self.rag_sync_service.get_sync_status()
                base_status["rag_details"] = rag_status
            except Exception as e:
                logger.error(f"Error getting RAG sync status: {e}")
                base_status["rag_details"] = {"error": str(e)}

        return base_status

    def _get_next_scheduled_sync_time(self) -> str:
        """Calcula la próxima hora de sincronización programada."""
        current_time = datetime.now()
        current_hour = current_time.hour

        # Encontrar la próxima hora de sincronización
        for sync_hour in sorted(self.settings.DUX_SYNC_HOURS):
            if sync_hour > current_hour:
                next_sync = current_time.replace(hour=sync_hour, minute=0, second=0, microsecond=0)
                return next_sync.isoformat()

        # Si no hay más horas hoy, usar la primera hora de mañana
        if self.settings.DUX_SYNC_HOURS:
            next_sync = (current_time + timedelta(days=1)).replace(
                hour=min(self.settings.DUX_SYNC_HOURS), minute=0, second=0, microsecond=0
            )
            return next_sync.isoformat()

        return "No scheduled syncs configured"

    async def force_products_sync(self, max_products: Optional[int] = None) -> Dict[str, Any]:
        """
        Fuerza sincronización inmediata de productos

        Args:
            max_products: Límite opcional de productos

        Returns:
            Dict con resultado de la operación
        """
        logger.info(f"Forcing immediate products sync (max: {max_products})")

        try:
            if self.use_rag_sync:
                result = await self.rag_sync_service.sync_all_products_with_rag(max_products=max_products)

                return {
                    "success": result.success,
                    "sync_type": "rag_integrated",
                    "processed": result.total_processed,
                    "created": result.total_created,
                    "updated": result.total_updated,
                    "errors": result.total_errors,
                    "embeddings_created": result.total_embeddings_created,
                    "embeddings_updated": result.total_embeddings_updated,
                    "duration_seconds": result.duration_seconds,
                }
            else:
                result = await self.sync_service.sync_all_products(max_products=max_products)

                return {
                    "success": result.success,
                    "sync_type": "database_only",
                    "processed": result.total_processed,
                    "created": result.total_created,
                    "updated": result.total_updated,
                    "errors": result.total_errors,
                    "duration_seconds": result.duration_seconds,
                }

        except Exception as e:
            logger.error(f"Error during forced sync: {e}")
            return {"success": False, "error": str(e)}

    async def force_embeddings_update(self) -> Dict[str, Any]:
        """
        Fuerza actualización inmediata de embeddings

        Returns:
            Dict con resultado de la operación
        """
        if not self.use_rag_sync:
            return {"success": False, "error": "RAG sync is disabled - cannot update embeddings"}

        logger.info("Forcing immediate embeddings update")

        try:
            result = await self.rag_sync_service.force_embedding_update_for_recent_products(hours=24)
            return result

        except Exception as e:
            logger.error(f"Error during forced embedding update: {e}")
            return {"success": False, "error": str(e)}

    def get_current_sync_state(self) -> dict:
        """Obtiene el estado actual de sincronización con progreso detallado."""
        return {
            "state": self._sync_state.value,
            "is_running": self._sync_state == SyncState.RUNNING,
            "progress": self._sync_progress.copy(),
            "has_current_task": self._current_sync_task is not None,
        }

    async def cancel_current_sync(self) -> bool:
        """Cancela la sincronización en progreso si existe."""
        if self._current_sync_task and not self._current_sync_task.done():
            try:
                self._current_sync_task.cancel()
                await asyncio.sleep(0.1)  # Give time for cancellation
                logger.info("🚫 Current sync task cancelled")
                return True
            except Exception as e:
                logger.error(f"Error cancelling sync task: {e}")
                return False
        return False

    def reset_sync_state(self):
        """Resetea el estado de sincronización a IDLE."""
        if self._sync_state != SyncState.RUNNING:
            self._sync_state = SyncState.IDLE
            self._sync_progress = {
                "total_items": 0,
                "processed_items": 0,
                "current_batch": 0,
                "total_batches": 0,
                "start_time": None,
                "estimated_completion": None,
                "error_message": None,
            }
            logger.info("Sync state reset to IDLE")


# Instancia global del servicio
_scheduled_sync_service: Optional[ScheduledSyncService] = None


def get_scheduled_sync_service(use_rag_sync: bool = True) -> ScheduledSyncService:
    """
    Obtiene la instancia global del servicio de sincronización programada.

    Args:
        use_rag_sync: Si True, usa sincronización integrada con RAG
    """
    global _scheduled_sync_service
    if _scheduled_sync_service is None:
        _scheduled_sync_service = ScheduledSyncService(use_rag_sync=use_rag_sync)
    return _scheduled_sync_service

