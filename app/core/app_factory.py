"""
Application factory for FastAPI.

This module follows SRP by handling only FastAPI application creation and configuration.
Uses modern FastAPI patterns and separates concerns into dedicated modules.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware.auth import AuthenticationMiddleware
from app.api.middleware.logging_middleware import RequestLoggingMiddleware
from app.core.tenancy import TenantContextMiddleware
from app.api.router import api_router
from app.api.routes import frontend
from app.config.settings import Settings, get_settings
from app.core.lifecycle import lifespan

logger = logging.getLogger(__name__)


class AppFactory:
    """
    Factory for creating and configuring FastAPI applications.

    Separates application creation from configuration details.
    Each configuration step is handled by a dedicated method.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize app factory.

        Args:
            settings: Application settings (uses default if not provided)
        """
        self._settings = settings or get_settings()

    def create_app(self) -> FastAPI:
        """
        Create and configure the FastAPI application.

        Returns:
            Configured FastAPI application instance.
        """
        app = self._create_base_app()

        self._configure_middleware(app)
        self._configure_exception_handlers(app)
        self._configure_routes(app)
        self._configure_static_files(app)
        self._configure_health_endpoint(app)

        logger.info(f"Application created: {self._settings.PROJECT_NAME}")
        return app

    def _create_base_app(self) -> FastAPI:
        """Create the base FastAPI application with lifespan."""
        return FastAPI(
            title=self._settings.PROJECT_NAME,
            description=self._settings.PROJECT_DESCRIPTION,
            version=self._settings.VERSION,
            docs_url=f"{self._settings.API_V1_STR}/docs" if self._settings.DEBUG else None,
            redoc_url=f"{self._settings.API_V1_STR}/redoc" if self._settings.DEBUG else None,
            lifespan=lifespan,  # Modern lifespan pattern
            redirect_slashes=False,  # Prevent 307 redirects for trailing slashes
        )

    def _configure_middleware(self, app: FastAPI) -> None:
        """
        Configure application middleware.

        Middleware order matters:
        1. CORS (outermost)
        2. Request logging
        3. Authentication (innermost before handlers)
        """
        # CORS middleware (must be first/outermost)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self._get_cors_origins(),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Request logging middleware
        app.add_middleware(RequestLoggingMiddleware)

        # Authentication middleware
        app.add_middleware(AuthenticationMiddleware)

        # Multi-tenant context middleware (resolves tenant from JWT, header, or WhatsApp)
        app.add_middleware(
            TenantContextMiddleware,
            tenant_header=self._settings.TENANT_HEADER,
            require_tenant=False,  # Allow fallback to system context
        )

        logger.info("Middleware configured")

    def _configure_exception_handlers(self, app: FastAPI) -> None:
        """Register exception handlers."""
        register_exception_handlers(app)

    def _configure_routes(self, app: FastAPI) -> None:
        """Configure API routes."""
        # Frontend routes (no prefix - serve at root)
        app.include_router(frontend.router, tags=["frontend"])

        # API routes (with /api/v1 prefix)
        app.include_router(api_router, prefix=self._settings.API_V1_STR)

        logger.info("Routes configured")

    def _configure_static_files(self, app: FastAPI) -> None:
        """Mount static files directory."""
        static_dir = Path(__file__).parent.parent / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logger.info(f"Static files mounted from: {static_dir}")
        else:
            logger.warning(f"Static directory not found: {static_dir}")

    def _configure_health_endpoint(self, app: FastAPI) -> None:
        """Add health check endpoint."""

        @app.get("/health", tags=["health"])
        async def helth_check() -> dict[str, str]:
            """
            Verify application health status.

            Returns basic status and environment information.
            """
            return {
                "status": "ok",
                "environment": self._settings.ENVIRONMENT,
            }

    def _get_cors_origins(self) -> list[str]:
        """
        Get allowed CORS origins based on environment.

        In production, reads from CORS_ORIGINS environment variable.
        In development (DEBUG=true), allows all origins.
        """
        if self._settings.DEBUG:
            return ["*"]

        import os

        cors_origins = os.getenv("CORS_ORIGINS", "")
        if cors_origins:
            return [origin.strip() for origin in cors_origins.split(",")]

        # Fallback defaults for production
        return [
            "http://localhost",
            "http://localhost:8000",
        ]


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create FastAPI application using the factory.

    This is the main entry point for application creation.

    Args:
        settings: Optional settings override

    Returns:
        Configured FastAPI application
    """
    factory = AppFactory(settings)
    return factory.create_app()
