"""
Servicio de sincronización programada para productos DUX
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config.settings import get_settings
from app.database.async_db import get_async_db_context
from app.services.dux_sync_service import DuxSyncService
from sqlalchemy import select, func
from app.models.db import Product

logger = logging.getLogger(__name__)


class ScheduledSyncService:
    """Servicio para programar y ejecutar sincronización de productos DUX."""
    
    def __init__(self):
        self.settings = get_settings()
        self.sync_service = DuxSyncService(batch_size=self.settings.DUX_SYNC_BATCH_SIZE)
        self.is_running = False
        self._sync_task: Optional[asyncio.Task] = None
        
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
                        await self._execute_sync()
                
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
        try:
            last_update = await self._get_most_recent_product_update()
            
            if not last_update:
                # No hay productos, sincronizar
                logger.info("No products in database, forcing sync")
                await self._execute_sync()
                return True
                
            hours_since_update = (datetime.now() - last_update).total_seconds() / 3600
            
            if hours_since_update > self.settings.DUX_FORCE_SYNC_THRESHOLD_HOURS:
                logger.info(f"Products are {hours_since_update:.1f} hours old, forcing sync")
                await self._execute_sync()
                return True
                
            logger.debug(f"Products are {hours_since_update:.1f} hours old, no sync needed")
            return False
            
        except Exception as e:
            logger.error(f"Error checking sync need: {e}")
            return False
            
    async def _execute_sync(self):
        """Ejecuta la sincronización con DUX."""
        try:
            logger.info("Executing DUX product sync")
            result = await self.sync_service.sync_all_products()
            
            logger.info(
                f"Sync completed - Processed: {result.total_processed}, "
                f"Created: {result.total_created}, Updated: {result.total_updated}, "
                f"Errors: {result.total_errors}"
            )
            
            # Guardar timestamp de última sincronización
            await self._save_sync_timestamp()
            
        except Exception as e:
            logger.error(f"Error during sync execution: {e}")
            
    async def _get_last_sync_time(self) -> Optional[datetime]:
        """Obtiene el timestamp de la última sincronización."""
        # TODO: Implementar almacenamiento persistente del timestamp
        # Por ahora, usar la fecha de actualización más reciente de productos
        return await self._get_most_recent_product_update()
        
    async def _get_most_recent_product_update(self) -> Optional[datetime]:
        """Obtiene la fecha de actualización más reciente de productos."""
        try:
            async with get_async_db_context() as db:
                result = await db.execute(
                    select(func.max(Product.updated_at))
                )
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
        """Obtiene el estado actual de la sincronización."""
        last_sync = await self._get_last_sync_time()
        last_update = await self._get_most_recent_product_update()
        
        return {
            "is_running": self.is_running,
            "sync_hours": self.settings.DUX_SYNC_HOURS,
            "force_sync_threshold_hours": self.settings.DUX_FORCE_SYNC_THRESHOLD_HOURS,
            "last_sync_time": last_sync.isoformat() if last_sync else None,
            "last_product_update": last_update.isoformat() if last_update else None,
            "hours_since_update": (
                (datetime.now() - last_update).total_seconds() / 3600 
                if last_update else None
            ),
            "next_scheduled_sync": self._get_next_scheduled_sync_time()
        }
        
    def _get_next_scheduled_sync_time(self) -> str:
        """Calcula la próxima hora de sincronización programada."""
        current_time = datetime.now()
        current_hour = current_time.hour
        
        # Encontrar la próxima hora de sincronización
        for sync_hour in sorted(self.settings.DUX_SYNC_HOURS):
            if sync_hour > current_hour:
                next_sync = current_time.replace(
                    hour=sync_hour, minute=0, second=0, microsecond=0
                )
                return next_sync.isoformat()
                
        # Si no hay más horas hoy, usar la primera hora de mañana
        if self.settings.DUX_SYNC_HOURS:
            next_sync = (current_time + timedelta(days=1)).replace(
                hour=min(self.settings.DUX_SYNC_HOURS),
                minute=0, second=0, microsecond=0
            )
            return next_sync.isoformat()
            
        return "No scheduled syncs configured"


# Instancia global del servicio
_scheduled_sync_service: Optional[ScheduledSyncService] = None


def get_scheduled_sync_service() -> ScheduledSyncService:
    """Obtiene la instancia global del servicio de sincronización programada."""
    global _scheduled_sync_service
    if _scheduled_sync_service is None:
        _scheduled_sync_service = ScheduledSyncService()
    return _scheduled_sync_service