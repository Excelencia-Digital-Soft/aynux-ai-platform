"""
Application lifecycle management using modern FastAPI lifespan pattern.

This module follows SRP by handling only application startup/shutdown logic.
Uses the modern `lifespan` context manager instead of deprecated on_event decorators.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.langsmith_init import get_langsmith_status, initialize_langsmith
from app.config.settings import get_settings
from app.core.background_services import BackgroundServiceManager

logger = logging.getLogger(__name__)
settings = get_settings()


class LifecycleManager:
    """
    Manages application lifecycle events.

    Handles startup initialization and graceful shutdown.
    Separates concerns from the main application factory.
    """

    def __init__(self) -> None:
        """Initialize lifecycle manager."""
        self._background_service_manager = BackgroundServiceManager()
        self._initialized = False

    async def startup(self) -> None:
        """
        Execute startup tasks.

        Called when the application starts.
        """
        if self._initialized:
            logger.warning("Lifecycle already initialized, skipping startup")
            return

        logger.info("Starting application lifecycle...")

        # Initialize LangSmith tracing
        await self._initialize_langsmith()

        # Verify critical configurations
        self._verify_configurations()

        # Start background services (DUX sync, etc.)
        await self._background_service_manager.start()

        # Verify external service connectivity
        await self._verify_external_services()

        self._initialized = True
        logger.info("Application lifecycle startup completed")

    async def shutdown(self) -> None:
        """
        Execute shutdown tasks.

        Called when the application stops.
        """
        if not self._initialized:
            logger.warning("Lifecycle not initialized, skipping shutdown")
            return

        logger.info("Stopping application lifecycle...")

        # Stop background services
        await self._background_service_manager.stop()

        self._initialized = False
        logger.info("Application lifecycle shutdown completed")

    async def _initialize_langsmith(self) -> None:
        """Initialize LangSmith tracing if configured."""
        try:
            langsmith_initialized = initialize_langsmith(force=True)
            if langsmith_initialized:
                logger.info("LangSmith tracing initialized successfully")
                status = get_langsmith_status()
                logger.info(f"  Project: {status.get('project')}")
                logger.info(f"  Tracing enabled: {status.get('tracing_enabled')}")
            else:
                logger.warning("LangSmith tracing not initialized (may be disabled or misconfigured)")
        except Exception as e:
            logger.error(f"Error initializing LangSmith: {e}")

    def _verify_configurations(self) -> None:
        """Verify critical application configurations."""
        if not settings.DUX_API_KEY:
            logger.warning("DUX_API_KEY not configured - DUX sync will be disabled")

        if not settings.DUX_SYNC_ENABLED:
            logger.info("DUX sync is disabled via DUX_SYNC_ENABLED=False")

    async def _verify_external_services(self) -> None:
        """Verify connectivity with external services."""
        try:
            # Verify DUX API connectivity
            if settings.DUX_API_KEY:
                await self._verify_dux_connectivity()

            # Verify Ollama connectivity (embeddings)
            await self._verify_embedding_connectivity()

        except Exception as e:
            logger.error(f"Error verifying external services: {e}")

    async def _verify_dux_connectivity(self) -> None:
        """Verify DUX API is accessible."""
        try:
            from app.clients.dux_api_client import DuxApiClientFactory

            async with DuxApiClientFactory.create_client() as client:
                if await client.test_connection():
                    logger.info("DUX API connectivity verified")
                else:
                    logger.warning("DUX API connectivity failed")
        except Exception as e:
            logger.warning(f"DUX API connectivity check failed: {e}")

    async def _verify_embedding_connectivity(self) -> None:
        """Verify embedding service (Ollama/pgvector) is accessible."""
        try:
            from langchain_ollama import OllamaEmbeddings

            embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")
            # Simple test embedding
            test_result = embeddings.embed_query("test")
            if test_result and len(test_result) > 0:
                logger.info(f"Ollama embeddings connectivity verified - Dimension: {len(test_result)}")
            else:
                logger.warning("Ollama embeddings test returned empty result")
        except Exception as e:
            logger.warning(f"Ollama embeddings connectivity failed: {e}")


# Global lifecycle manager instance
_lifecycle_manager: LifecycleManager | None = None


def get_lifecycle_manager() -> LifecycleManager:
    """Get or create the global lifecycle manager instance."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = LifecycleManager()
    return _lifecycle_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Modern FastAPI lifespan context manager.

    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").

    Usage:
        app = FastAPI(lifespan=lifespan)

    This pattern is recommended by FastAPI for Python 3.9+.
    See: https://fastapi.tiangolo.com/advanced/events/
    """
    lifecycle = get_lifecycle_manager()

    # Startup
    await lifecycle.startup()

    yield  # Application runs here

    # Shutdown
    await lifecycle.shutdown()
