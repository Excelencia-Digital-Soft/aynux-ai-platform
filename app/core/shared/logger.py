"""
Shared Logger

Centralized logging configuration for the application.
"""

import json
import logging
import sys
from datetime import datetime, UTC
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        extra_data = getattr(record, "extra_data", None)
        if extra_data is not None:
            log_data["extra"] = extra_data

        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    """Colored console log formatter."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format with colors."""
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class ContextLogger:
    """Logger with context support."""

    def __init__(self, name: str, context: dict[str, Any] | None = None):
        """
        Initialize context logger.

        Args:
            name: Logger name
            context: Default context to include in all logs
        """
        self._logger = logging.getLogger(name)
        self._context = context or {}

    def with_context(self, **kwargs) -> "ContextLogger":
        """Create new logger with additional context."""
        new_context = {**self._context, **kwargs}
        return ContextLogger(self._logger.name, new_context)

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Log with context."""
        extra = {**self._context, **kwargs}
        self._logger.log(level, message, extra={"extra_data": extra})

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        self._logger.exception(message, extra={"extra_data": {**self._context, **kwargs}})


def configure_logging(
    level: str = "INFO",
    format_type: str = "colored",
    log_file: str | None = None,
) -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 'colored', 'json', or 'plain'
        log_file: Optional file path for file logging
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if format_type == "json":
        console_handler.setFormatter(JSONFormatter())
    elif format_type == "colored":
        console_handler.setFormatter(
            ColoredFormatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)


def get_logger(name: str, context: dict[str, Any] | None = None) -> ContextLogger:
    """
    Get a context-aware logger.

    Args:
        name: Logger name (typically __name__)
        context: Default context

    Returns:
        ContextLogger instance
    """
    return ContextLogger(name, context)


# Pre-configured loggers for common modules
def get_agent_logger(agent_name: str) -> ContextLogger:
    """Get logger for agent modules."""
    return get_logger(f"agent.{agent_name}", {"component": "agent", "agent": agent_name})


def get_api_logger(route_name: str) -> ContextLogger:
    """Get logger for API routes."""
    return get_logger(f"api.{route_name}", {"component": "api", "route": route_name})


def get_service_logger(service_name: str) -> ContextLogger:
    """Get logger for service modules."""
    return get_logger(f"service.{service_name}", {"component": "service", "service": service_name})


def get_repository_logger(repo_name: str) -> ContextLogger:
    """Get logger for repository modules."""
    return get_logger(f"repository.{repo_name}", {"component": "repository", "repository": repo_name})
