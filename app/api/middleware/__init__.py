"""
Middleware package for FastAPI application.

Contains authentication, logging, and other request processing middleware.
"""

from app.api.middleware.auth import AuthenticationMiddleware
from app.api.middleware.logging_middleware import RequestLoggingMiddleware

__all__ = [
    "AuthenticationMiddleware",
    "RequestLoggingMiddleware",
]
