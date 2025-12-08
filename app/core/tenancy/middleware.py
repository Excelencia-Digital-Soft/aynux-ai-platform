# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Middleware que resuelve el tenant automáticamente en cada request.
#              Punto de entrada para la propagación del contexto de tenant.
# Tenant-Aware: Yes - es el INICIADOR del tenant-awareness en cada request.
# ============================================================================
"""
TenantContextMiddleware - FastAPI middleware for automatic tenant resolution.

Automatically resolves tenant context from incoming requests and makes it
available throughout the request lifecycle via contextvars.

Resolution strategies (in order):
1. JWT Authorization header with org_id claim
2. X-Tenant-ID header (for internal services)
3. WhatsApp webhook wa_id parameter
4. Default to system context (generic mode)

Usage:
    from app.core.tenancy import TenantContextMiddleware

    app = FastAPI()
    app.add_middleware(TenantContextMiddleware)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config.settings import get_settings
from app.database.async_db import get_async_db

from .context import TenantContext, set_tenant_context
from .resolver import TenantResolutionError, TenantResolver

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic tenant context resolution.

    Resolves tenant from various sources and sets the context for the
    duration of the request. The context is automatically cleared after
    the request completes.

    Configuration:
        - MULTI_TENANT_MODE: Enable/disable multi-tenant resolution
        - TENANT_HEADER: Custom header name for tenant ID (default: X-Tenant-ID)

    Example:
        >>> app = FastAPI()
        >>> app.add_middleware(TenantContextMiddleware)

        >>> @app.get("/products")
        >>> async def get_products():
        >>>     ctx = get_tenant_context()
        >>>     return await repo.get_by_org(ctx.organization_id)
    """

    # Paths that should skip tenant resolution
    SKIP_PATHS = {
        "/health",
        "/healthz",
        "/ready",
        "/readyz",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    # Paths that use WhatsApp webhook resolution
    WHATSAPP_PATHS = {
        "/api/v1/webhook",
        "/api/v1/whatsapp/webhook",
        "/webhook",
    }

    def __init__(
        self,
        app: Callable,
        *,
        tenant_header: str = "X-Tenant-ID",
        require_tenant: bool = False,
    ):
        """
        Initialize middleware.

        Args:
            app: ASGI application.
            tenant_header: Header name for tenant ID.
            require_tenant: If True, reject requests without tenant context.
        """
        super().__init__(app)
        self.tenant_header = tenant_header
        self.require_tenant = require_tenant
        self.settings = get_settings()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        """
        Process request and resolve tenant context.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware/handler in chain.

        Returns:
            HTTP response.
        """
        # Skip tenant resolution for certain paths
        if self._should_skip(request.url.path):
            return await call_next(request)

        try:
            # Resolve tenant context
            context = await self._resolve_tenant(request)

            # Set context for request duration
            set_tenant_context(context)

            # Log tenant info for debugging
            if context:
                logger.debug(
                    f"Tenant context set: org_id={context.organization_id}, "
                    f"mode={context.mode}, is_system={context.is_system}"
                )

            # Process request
            response = await call_next(request)

            return response

        except TenantResolutionError as e:
            logger.warning(f"Tenant resolution failed: {e}")
            if self.require_tenant:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Tenant resolution failed",
                        "error": str(e),
                    },
                )
            # Fall back to system context
            set_tenant_context(TenantContext.create_system_context())
            return await call_next(request)

        except Exception as e:
            logger.exception(f"Unexpected error in tenant middleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        finally:
            # Clear context after request
            set_tenant_context(None)

    def _should_skip(self, path: str) -> bool:
        """Check if path should skip tenant resolution."""
        # Exact matches
        if path in self.SKIP_PATHS:
            return True

        # Prefix matches for static files
        if path.startswith("/static/"):
            return True

        return False

    async def _resolve_tenant(self, request: Request) -> TenantContext | None:
        """
        Resolve tenant context from request.

        Tries multiple resolution strategies in order:
        1. JWT Authorization header
        2. X-Tenant-ID header
        3. WhatsApp webhook parameters
        4. System context (fallback)

        Args:
            request: HTTP request.

        Returns:
            TenantContext or None.
        """
        # Check if multi-tenant mode is enabled
        multi_tenant_enabled = getattr(self.settings, "MULTI_TENANT_MODE", False)
        if not multi_tenant_enabled:
            return TenantContext.create_system_context()

        # Get database session
        async for db in get_async_db():
            resolver = TenantResolver(db)

            # Strategy 1: JWT Authorization header
            context = await self._try_jwt_resolution(request, resolver)
            if context:
                return context

            # Strategy 2: X-Tenant-ID header
            context = await self._try_header_resolution(request, resolver)
            if context:
                return context

            # Strategy 3: WhatsApp webhook
            if request.url.path in self.WHATSAPP_PATHS:
                context = await self._try_whatsapp_resolution(request, resolver)
                if context:
                    return context

            break

        # Fallback to system context
        return TenantContext.create_system_context()

    async def _try_jwt_resolution(
        self,
        request: Request,
        resolver: TenantResolver,
    ) -> TenantContext | None:
        """Try to resolve tenant from JWT token."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        try:
            from app.api.middleware.auth import decode_token

            token = auth_header.split(" ")[1]
            payload = decode_token(token)

            if payload and ("org_id" in payload or "organization_id" in payload):
                return await resolver.resolve_from_jwt(payload, require_org=False)

        except Exception as e:
            logger.debug(f"JWT resolution failed: {e}")

        return None

    async def _try_header_resolution(
        self,
        request: Request,
        resolver: TenantResolver,
    ) -> TenantContext | None:
        """Try to resolve tenant from X-Tenant-ID header."""
        import uuid

        tenant_id = request.headers.get(self.tenant_header)
        if not tenant_id:
            return None

        try:
            org_id = uuid.UUID(tenant_id)
            return await resolver.resolve_from_organization_id(org_id)
        except (ValueError, TenantResolutionError) as e:
            logger.debug(f"Header resolution failed: {e}")

        return None

    async def _try_whatsapp_resolution(
        self,
        request: Request,
        resolver: TenantResolver,
    ) -> TenantContext | None:
        """Try to resolve tenant from WhatsApp webhook data."""
        try:
            # For GET requests (verification), skip
            if request.method == "GET":
                return None

            # For POST requests, try to extract wa_id from body
            body = await request.body()
            if not body:
                return None

            import json

            data = json.loads(body)

            # Extract wa_id from WhatsApp webhook format
            wa_id = self._extract_wa_id(data)
            if wa_id:
                return await resolver.resolve_from_whatsapp(wa_id, require_org=False)

        except Exception as e:
            logger.debug(f"WhatsApp resolution failed: {e}")

        return None

    def _extract_wa_id(self, data: dict) -> str | None:
        """
        Extract WhatsApp ID from webhook payload.

        WhatsApp Cloud API webhook format:
        {
            "entry": [{
                "changes": [{
                    "value": {
                        "contacts": [{"wa_id": "..."}],
                        "messages": [{"from": "..."}]
                    }
                }]
            }]
        }
        """
        try:
            entry = data.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})

            # Try contacts first
            contacts = value.get("contacts", [])
            if contacts:
                return contacts[0].get("wa_id")

            # Try messages
            messages = value.get("messages", [])
            if messages:
                return messages[0].get("from")

        except (IndexError, KeyError):
            pass

        return None


def get_tenant_dependency() -> TenantContext:
    """
    FastAPI dependency to get current tenant context.

    Use this in route handlers to access tenant context:

        @app.get("/items")
        async def get_items(tenant: TenantContext = Depends(get_tenant_dependency)):
            return await repo.get_by_org(tenant.organization_id)

    Raises:
        HTTPException: If tenant context is not available.
    """
    from fastapi import HTTPException

    from .context import get_tenant_context

    ctx = get_tenant_context()
    if ctx is None:
        raise HTTPException(
            status_code=401,
            detail="Tenant context not available. Authentication required.",
        )
    return ctx


def get_optional_tenant_dependency() -> TenantContext | None:
    """
    FastAPI dependency to get optional tenant context.

    Returns None if no tenant context is set (useful for public endpoints).

        @app.get("/public")
        async def public_endpoint(tenant: TenantContext | None = Depends(get_optional_tenant_dependency)):
            if tenant:
                # Tenant-specific logic
                pass
            else:
                # Public logic
                pass
    """
    from .context import get_tenant_context

    return get_tenant_context()
