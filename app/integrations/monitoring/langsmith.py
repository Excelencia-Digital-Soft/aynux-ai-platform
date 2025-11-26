"""
LangSmith Integration

Provides LangSmith tracing and monitoring for LLM operations.
"""

import logging
from typing import Any

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> bool:
    """
    Configure LangSmith tracing.

    Returns:
        True if configuration was successful
    """
    settings = get_settings()

    if not settings.LANGSMITH_TRACING:
        logger.info("LangSmith tracing disabled")
        return False

    if not settings.LANGSMITH_API_KEY:
        logger.warning("LangSmith API key not configured")
        return False

    import os

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

    logger.info(f"LangSmith configured for project: {settings.LANGSMITH_PROJECT}")
    return True


def get_langsmith_client() -> Any | None:
    """
    Get LangSmith client instance.

    Returns:
        LangSmith client or None if not configured
    """
    settings = get_settings()

    if not settings.LANGSMITH_API_KEY:
        return None

    try:
        from langsmith import Client

        return Client(
            api_url=settings.LANGSMITH_ENDPOINT,
            api_key=settings.LANGSMITH_API_KEY,
        )
    except ImportError:
        logger.warning("langsmith package not installed")
        return None


__all__ = [
    "configure_langsmith",
    "get_langsmith_client",
]
