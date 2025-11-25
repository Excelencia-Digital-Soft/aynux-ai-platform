"""
Request logging middleware for FastAPI application.

This module follows SRP by handling only request/response logging.
"""

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for request/response logging.

    Logs request details, timing, and response status.
    Adds correlation ID to requests for tracing.
    """

    # Paths to exclude from detailed logging (high-frequency, low-value)
    EXCLUDE_PATHS: tuple[str, ...] = (
        "/health",
        "/static",
        "/favicon.ico",
    )

    def __init__(self, app: ASGIApp, log_request_body: bool = False) -> None:
        """
        Initialize logging middleware.

        Args:
            app: ASGI application
            log_request_body: Whether to log request bodies (careful with sensitive data)
        """
        super().__init__(app)
        self._log_request_body = log_request_body

    def _should_log(self, path: str) -> bool:
        """Check if request should be logged based on path."""
        return not any(path.startswith(exclude) for exclude in self.EXCLUDE_PATHS)

    def _generate_correlation_id(self) -> str:
        """Generate a unique correlation ID for request tracing."""
        return str(uuid.uuid4())[:8]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        """
        Process request with logging.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler
        """
        # Generate and attach correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", self._generate_correlation_id())
        request.state.correlation_id = correlation_id

        # Skip detailed logging for excluded paths
        if not self._should_log(request.url.path):
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response

        # Log request
        start_time = time.perf_counter()
        client_ip = self._get_client_ip(request)

        logger.info(f"[{correlation_id}] --> {request.method} {request.url.path} " f"from {client_ip}")

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception and re-raise
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[{correlation_id}] <-- {request.method} {request.url.path} " f"ERROR in {duration_ms:.2f}ms: {e}"
            )
            raise

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log response
        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(
            log_level,
            f"[{correlation_id}] <-- {request.method} {request.url.path} "
            f"{response.status_code} in {duration_ms:.2f}ms",
        )

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request, considering proxies.

        Checks X-Forwarded-For header for proxied requests.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain (original client)
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
