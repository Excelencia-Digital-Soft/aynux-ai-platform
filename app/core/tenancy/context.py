# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Contexto de tenant usando contextvars de Python.
#              Propaga información del tenant a través de llamadas async.
# Tenant-Aware: Yes - ESTE ES el mecanismo central de tenant-awareness.
# ============================================================================
"""
TenantContext - Request-scoped tenant context using Python's contextvars.

Provides thread-safe, async-safe tenant context that propagates automatically
across async function calls within a request.

Usage:
    # Set context (usually in middleware)
    ctx = TenantContext(organization_id=uuid, organization=org, user_id=uuid)
    set_tenant_context(ctx)

    # Get context anywhere in the request
    ctx = get_tenant_context()
    org_id = ctx.organization_id

    # Convenience function
    tenant = get_current_tenant()  # Returns organization_id or None
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.db.tenancy import Organization, TenantConfig


# Context variable for tenant context - thread-safe and async-safe
_tenant_context: ContextVar[TenantContext | None] = ContextVar("tenant_context", default=None)


@dataclass
class TenantContext:
    """
    Request-scoped tenant context.

    Contains all tenant-related information needed during request processing.
    This context is automatically propagated across async function calls.

    Attributes:
        organization_id: The organization UUID (required)
        organization: Full Organization model (lazy-loaded)
        user_id: The user UUID within the organization (optional)
        config: TenantConfig for this organization (lazy-loaded)
        mode: Operating mode ('generic' or 'multi_tenant')
        is_system: Whether this is the system organization (for generic mode)

    Example:
        >>> ctx = TenantContext(
        ...     organization_id=org_uuid,
        ...     organization=org,
        ...     user_id=user_uuid
        ... )
        >>> set_tenant_context(ctx)
        >>> # Later in request handling...
        >>> ctx = get_tenant_context()
        >>> print(ctx.organization_id)
    """

    organization_id: uuid.UUID
    organization: Organization | None = None
    user_id: uuid.UUID | None = None
    config: TenantConfig | None = None
    mode: str = "multi_tenant"
    is_system: bool = False

    # Cached values for performance
    _enabled_domains: list[str] = field(default_factory=list, repr=False)
    _enabled_agents: list[str] = field(default_factory=list, repr=False)

    @property
    def is_generic_mode(self) -> bool:
        """Check if operating in generic (single-tenant) mode."""
        return self.mode == "generic" or self.is_system

    @property
    def is_multi_tenant_mode(self) -> bool:
        """Check if operating in multi-tenant mode."""
        return self.mode == "multi_tenant" and not self.is_system

    @property
    def enabled_domains(self) -> list[str]:
        """Get list of enabled domains for this tenant."""
        if self._enabled_domains:
            return self._enabled_domains
        if self.config:
            return self.config.enabled_domains or []
        return []

    @property
    def enabled_agents(self) -> list[str]:
        """Get list of enabled agent types for this tenant."""
        if self._enabled_agents:
            return self._enabled_agents
        if self.config:
            return self.config.enabled_agent_types or []
        return []

    @property
    def rag_enabled(self) -> bool:
        """Check if RAG is enabled for this tenant."""
        if self.config:
            return self.config.rag_enabled
        return False

    @property
    def rag_similarity_threshold(self) -> float:
        """Get RAG similarity threshold for this tenant."""
        if self.config:
            return self.config.rag_similarity_threshold
        return 0.7  # Default threshold

    @property
    def rag_max_results(self) -> int:
        """Get max RAG results for this tenant."""
        if self.config:
            return self.config.rag_max_results
        return 5  # Default max results

    @property
    def llm_model(self) -> str:
        """Get LLM model for this tenant."""
        if self.organization:
            return self.organization.llm_model
        return "deepseek-r1:7b"  # Default model

    @property
    def llm_temperature(self) -> float:
        """Get LLM temperature for this tenant."""
        if self.organization:
            return self.organization.llm_temperature
        return 0.7  # Default temperature

    @property
    def llm_max_tokens(self) -> int:
        """Get max tokens for this tenant."""
        if self.organization:
            return self.organization.llm_max_tokens
        return 2048  # Default max tokens

    def with_config(self, config: TenantConfig) -> TenantContext:
        """Return a new context with the config set."""
        return TenantContext(
            organization_id=self.organization_id,
            organization=self.organization,
            user_id=self.user_id,
            config=config,
            mode=self.mode,
            is_system=self.is_system,
            _enabled_domains=list(config.enabled_domains) if config.enabled_domains else [],
            _enabled_agents=list(config.enabled_agent_types) if config.enabled_agent_types else [],
        )

    @classmethod
    def create_system_context(cls) -> TenantContext:
        """
        Create a context for the system organization (generic mode).

        Used when operating without multi-tenancy, falls back to
        environment-based configuration.
        """
        # Use a fixed UUID for system organization
        system_org_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        return cls(
            organization_id=system_org_id,
            mode="generic",
            is_system=True,
        )


def get_tenant_context() -> TenantContext | None:
    """
    Get the current tenant context.

    Returns:
        TenantContext if set, None otherwise.

    Example:
        >>> ctx = get_tenant_context()
        >>> if ctx:
        ...     print(f"Current org: {ctx.organization_id}")
    """
    return _tenant_context.get()


def get_current_tenant() -> uuid.UUID | None:
    """
    Convenience function to get the current organization ID.

    Returns:
        Organization UUID if context is set, None otherwise.

    Example:
        >>> org_id = get_current_tenant()
        >>> if org_id:
        ...     products = await repo.get_by_org(org_id)
    """
    ctx = _tenant_context.get()
    return ctx.organization_id if ctx else None


def set_tenant_context(context: TenantContext | None) -> None:
    """
    Set the tenant context for the current request.

    Should typically be called from middleware at the start of request processing.

    Args:
        context: TenantContext to set, or None to clear.

    Example:
        >>> ctx = TenantContext(organization_id=org_uuid)
        >>> set_tenant_context(ctx)
    """
    _tenant_context.set(context)


def require_tenant_context() -> TenantContext:
    """
    Get the tenant context, raising an error if not set.

    Use this when tenant context is required for an operation.

    Returns:
        TenantContext (never None)

    Raises:
        RuntimeError: If tenant context is not set.

    Example:
        >>> ctx = require_tenant_context()
        >>> # ctx is guaranteed to be TenantContext, not None
    """
    ctx = _tenant_context.get()
    if ctx is None:
        raise RuntimeError(
            "Tenant context is required but not set. "
            "Ensure TenantContextMiddleware is configured."
        )
    return ctx
