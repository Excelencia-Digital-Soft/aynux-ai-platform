"""
Background services management for the application.

This module follows SRP by handling only background task orchestration.
"""

import asyncio
import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BackgroundServiceManager:
    """
    Manages background services lifecycle.

    Handles starting, stopping, and monitoring of background tasks
    like DUX synchronization.
    """

    def __init__(self) -> None:
        """Initialize background service manager."""
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._sync_service: Any = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if background services are running."""
        return self._running

    async def start(self) -> None:
        """Start all background services."""
        if self._running:
            logger.warning("Background services already running")
            return

        logger.info("Starting background services...")

        # Start DUX sync service if enabled
        if settings.DUX_SYNC_ENABLED and settings.DUX_API_KEY:
            await self._start_dux_sync()
        else:
            logger.info("DUX sync disabled or not configured")

        self._running = True
        logger.info("Background services started")

    async def stop(self) -> None:
        """Stop all background services gracefully."""
        if not self._running:
            logger.warning("Background services not running")
            return

        logger.info("Stopping background services...")

        # Cancel all background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._background_tasks.clear()

        # Stop DUX sync service
        if self._sync_service:
            await self._stop_dux_sync()

        self._running = False
        logger.info("Background services stopped")

    async def _start_dux_sync(self) -> None:
        """Start DUX synchronization service."""
        try:
            from app.domains.ecommerce.infrastructure.services.scheduled_sync_service import (
                get_scheduled_sync_service,
            )

            # Use integrated RAG sync by default
            self._sync_service = get_scheduled_sync_service(use_rag_sync=True)
            await self._sync_service.start()

            # Get initial status
            initial_status = await self._sync_service.get_sync_status()
            logger.info(
                f"DUX scheduled sync service started - "
                f"Mode: {initial_status['sync_mode']}, "
                f"Next sync: {initial_status['next_scheduled_sync']}"
            )

            # Schedule initial sync check in background
            sync_task = asyncio.create_task(
                self._run_initial_sync(),
                name="initial_dux_sync",
            )
            self._background_tasks.add(sync_task)
            sync_task.add_done_callback(self._background_tasks.discard)

            logger.info("Background initial sync task scheduled")

        except Exception as e:
            logger.error(f"Failed to start DUX sync service: {e}", exc_info=True)

    async def _stop_dux_sync(self) -> None:
        """Stop DUX synchronization service."""
        try:
            if self._sync_service:
                await self._sync_service.stop()
                logger.info("DUX scheduled sync service stopped")
                self._sync_service = None
        except Exception as e:
            logger.error(f"Error stopping DUX sync service: {e}", exc_info=True)

    async def _run_initial_sync(self) -> None:
        """
        Run initial sync check in background.

        Does not block application startup.
        """
        try:
            logger.info("Starting background initial sync check...")

            if self._sync_service:
                sync_executed = await self._sync_service.force_sync_if_needed()
                if sync_executed:
                    logger.info("Background initial sync completed successfully")
                else:
                    logger.info("Background initial sync not needed (data is recent)")

        except asyncio.CancelledError:
            logger.info("Initial sync cancelled")
            raise
        except Exception as e:
            logger.error(f"Background initial sync failed: {e}", exc_info=True)
        finally:
            logger.info("Background initial sync task finished")

    def get_status(self) -> dict[str, Any]:
        """
        Get status of background services.

        Returns:
            Dictionary with service status information.
        """
        return {
            "running": self._running,
            "active_tasks": len(self._background_tasks),
            "dux_sync_enabled": self._sync_service is not None,
        }


# Global instance for singleton pattern
_background_service_manager: BackgroundServiceManager | None = None


def get_background_service_manager() -> BackgroundServiceManager:
    """Get or create the global background service manager."""
    global _background_service_manager
    if _background_service_manager is None:
        _background_service_manager = BackgroundServiceManager()
    return _background_service_manager
