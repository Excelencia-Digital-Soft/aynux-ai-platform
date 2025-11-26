"""
Sentry Integration

Provides Sentry error tracking and monitoring.
"""

import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


def configure_sentry() -> bool:
    """
    Configure Sentry error tracking.

    Returns:
        True if configuration was successful
    """
    settings = get_settings()

    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1 if settings.is_development else 0.01,
            profiles_sample_rate=0.1 if settings.is_development else 0.01,
            integrations=[
                StarletteIntegration(),
                FastApiIntegration(),
            ],
        )

        logger.info(f"Sentry configured for environment: {settings.ENVIRONMENT}")
        return True
    except ImportError:
        logger.warning("sentry-sdk package not installed")
        return False


def capture_exception(exception: Exception, context: dict[str, Any] | None = None) -> None:
    """
    Capture an exception to Sentry.

    Args:
        exception: The exception to capture
        context: Additional context data
    """
    try:
        import sentry_sdk

        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(exception)
        else:
            sentry_sdk.capture_exception(exception)
    except ImportError:
        logger.error(f"Exception not sent to Sentry (not installed): {exception}")


def capture_message(message: str, level: str = "info") -> None:
    """
    Capture a message to Sentry.

    Args:
        message: The message to capture
        level: Log level (debug, info, warning, error, fatal)
    """
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level=level)
    except ImportError:
        logger.log(logging.getLevelName(level.upper()), message)


__all__ = [
    "configure_sentry",
    "capture_exception",
    "capture_message",
]
