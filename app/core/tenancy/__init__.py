"""
Tenancy module for multi-tenant support.

This module provides the core infrastructure for multi-tenant operations:
- TenantContext: Request-scoped tenant context using contextvars
- TenantResolver: Resolves tenant from JWT token or other sources
- TenantMiddleware: FastAPI middleware for automatic tenant resolution
- TenantVectorStore: Multi-tenant aware vector store for RAG
- TenantPromptManager: Multi-tenant prompt resolution with scope hierarchy
"""

from .context import (
    TenantContext,
    get_current_tenant,
    get_tenant_context,
    require_tenant_context,
    set_tenant_context,
)
from .middleware import (
    TenantContextMiddleware,
    get_optional_tenant_dependency,
    get_tenant_dependency,
)
from .prompt_manager import PromptNotFoundError, PromptScope, TenantPromptManager
from .resolver import TenantResolutionError, TenantResolver
from .vector_store import TenantVectorStore

__all__ = [
    # Context
    "TenantContext",
    "get_current_tenant",
    "get_tenant_context",
    "require_tenant_context",
    "set_tenant_context",
    # Middleware
    "TenantContextMiddleware",
    "get_tenant_dependency",
    "get_optional_tenant_dependency",
    # Resolver
    "TenantResolutionError",
    "TenantResolver",
    # Vector Store
    "TenantVectorStore",
    # Prompt Manager
    "TenantPromptManager",
    "PromptScope",
    "PromptNotFoundError",
]
