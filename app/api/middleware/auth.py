"""
Authentication middleware for FastAPI application.

This module follows SRP by handling only authentication concerns.
Uses modern Starlette middleware patterns.
"""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config.settings import get_settings
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

# Use settings instead of os.getenv for consistency
_settings = get_settings()
API_V1_STR = _settings.API_V1_STR


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    HTTP middleware for request authentication.

    Handles JWT token validation for protected routes.
    Public paths bypass authentication.
    """

    # Routes that don't require authentication
    PUBLIC_PATHS: tuple[str, ...] = (
        f"{API_V1_STR}/auth/token",
        f"{API_V1_STR}/auth/refresh",
        f"{API_V1_STR}/webhook",
        "/health",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/static",
        "/chat",
    )

    def __init__(self, app: ASGIApp, token_service: TokenService | None = None) -> None:
        """
        Initialize authentication middleware.

        Args:
            app: ASGI application
            token_service: Optional token service instance (for testing)
        """
        super().__init__(app)
        self._token_service = token_service or TokenService()

    def _is_public_path(self, path: str) -> bool:
        """Check if the request path is public and doesn't require auth."""
        return any(path.startswith(public_path) for public_path in self.PUBLIC_PATHS)

    def _extract_token(self, request: Request) -> str | None:
        """
        Extract Bearer token from Authorization header.

        Returns:
            Token string if valid Bearer scheme, None otherwise.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> JSONResponse:
        """
        Process the request through authentication.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            Response from next handler or 401 error
        """
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract token
        token = self._extract_token(request)
        if not token:
            logger.warning(f"Missing auth token for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": True,
                    "message": "Authentication required",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify token
        if not self._token_service.verify_token(token):
            logger.warning(f"Invalid token for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": True,
                    "message": "Invalid or expired token",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Decode and attach user info to request state
        try:
            payload = self._token_service.decode_token(token)
            request.state.user = payload
        except Exception as e:
            logger.error(f"Token decode error: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": True,
                    "message": "Token decode error",
                    "status_code": status.HTTP_401_UNAUTHORIZED,
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
