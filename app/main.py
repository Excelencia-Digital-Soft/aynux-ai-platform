"""
Application entry point.

This module follows SRP by only serving as the application entry point.
All configuration, middleware, and lifecycle management is delegated
to specialized modules.
"""

import logging

import sentry_sdk

from app.config.settings import get_settings
from app.core.app_factory import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Sentry for error tracking
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    send_default_pii=True,
    environment=settings.ENVIRONMENT,
)

# Create application using factory
app = create_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting application in {settings.ENVIRONMENT} mode")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
    )
