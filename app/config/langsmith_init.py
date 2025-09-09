"""
LangSmith initialization module.
Ensures LangSmith is properly configured at application startup.
"""

import logging
import os

logger = logging.getLogger(__name__)


def initialize_langsmith(force: bool = False) -> bool:
    """
    Initialize LangSmith environment variables and configuration.

    Args:
        force: Force initialization even if already configured

    Returns:
        True if initialization successful, False otherwise
    """
    try:
        from app.config.settings import get_settings

        settings = get_settings()

        # Check if already initialized (unless forcing)
        if not force and os.getenv("LANGSMITH_TRACING_V2"):
            logger.debug("LangSmith already initialized")
            return True

        # Set environment variables from settings
        env_vars = {
            "LANGSMITH_TRACING": str(settings.LANGSMITH_TRACING).lower(),
            "LANGSMITH_TRACING_V2": str(settings.LANGSMITH_TRACING).lower(),
            "LANGSMITH_ENDPOINT": settings.LANGSMITH_ENDPOINT,
            "LANGSMITH_PROJECT": settings.LANGSMITH_PROJECT,
            "LANGSMITH_VERBOSE": str(settings.LANGSMITH_VERBOSE).lower(),
        }

        # Only set API key if available
        if settings.LANGSMITH_API_KEY:
            env_vars["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        else:
            logger.warning("LANGSMITH_API_KEY not configured - tracing will be disabled")
            env_vars["LANGSMITH_TRACING"] = "false"
            env_vars["LANGSMITH_TRACING_V2"] = "false"

        # Set all environment variables
        for key, value in env_vars.items():
            os.environ[key] = value
            logger.debug(f"Set {key} = {'***' if 'KEY' in key else value}")

        # Verify LangSmith client can be created
        if settings.LANGSMITH_API_KEY and settings.LANGSMITH_TRACING:
            try:
                from langsmith import Client

                Client(api_key=settings.LANGSMITH_API_KEY, api_url=settings.LANGSMITH_ENDPOINT)

                # Test connection by trying to access project
                # This is a lightweight check that doesn't make unnecessary API calls
                logger.info(f"LangSmith initialized successfully for project: {settings.LANGSMITH_PROJECT}")
                logger.info(f"Tracing enabled: {settings.LANGSMITH_TRACING}")
                logger.info(f"Verbose mode: {settings.LANGSMITH_VERBOSE}")

                return True

            except Exception as e:
                logger.error(f"Failed to initialize LangSmith client: {e}")
                # Disable tracing if client fails
                os.environ["LANGSMITH_TRACING"] = "false"
                os.environ["LANGSMITH_TRACING_V2"] = "false"
                return False
        else:
            logger.info("LangSmith tracing disabled (no API key or tracing disabled)")
            return False

    except Exception as e:
        logger.error(f"Error initializing LangSmith: {e}")
        return False


def get_langsmith_status() -> dict:
    """
    Get current LangSmith configuration status.

    Returns:
        Dictionary with LangSmith configuration and status
    """
    status = {
        "initialized": False,
        "tracing_enabled": False,
        "api_key_set": False,
        "project": None,
        "endpoint": None,
        "verbose": False,
        "environment_vars": {},
    }

    try:
        # Check environment variables
        env_vars = [
            "LANGSMITH_TRACING",
            "LANGSMITH_TRACING_V2",
            "LANGSMITH_API_KEY",
            "LANGSMITH_PROJECT",
            "LANGSMITH_ENDPOINT",
            "LANGSMITH_VERBOSE",
        ]

        for var in env_vars:
            value = os.getenv(var)
            if value:
                # Mask API key
                if "KEY" in var:
                    status["environment_vars"][var] = "***" if value else "not set"
                    status["api_key_set"] = bool(value)
                else:
                    status["environment_vars"][var] = value

        # Check tracing status
        status["tracing_enabled"] = os.getenv("LANGSMITH_TRACING", "").lower() == "true"
        status["project"] = os.getenv("LANGSMITH_PROJECT")
        status["endpoint"] = os.getenv("LANGSMITH_ENDPOINT")
        status["verbose"] = os.getenv("LANGSMITH_VERBOSE", "").lower() == "true"

        # Check if properly initialized
        status["initialized"] = (
            status["api_key_set"] and status["project"] is not None and status["endpoint"] is not None
        )

        # Test client if initialized
        if status["initialized"] and status["tracing_enabled"]:
            try:
                from langsmith import Client

                api_key = os.getenv("LANGSMITH_API_KEY")
                if api_key:
                    Client(api_key=api_key)
                    status["client_available"] = True
            except Exception:
                status["client_available"] = False

    except Exception as e:
        logger.error(f"Error getting LangSmith status: {e}")
        status["error"] = str(e)

    return status


# Auto-initialize when module is imported
_initialized = initialize_langsmith()

if _initialized:
    logger.info("LangSmith auto-initialized on module import")
else:
    logger.warning("LangSmith auto-initialization failed or disabled")

