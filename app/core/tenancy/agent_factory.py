# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Factory que filtra agentes habilitados según TenantConfig.
#              Intersección de agentes globales con los permitidos por tenant.
# Tenant-Aware: Yes - consulta enabled_agent_types del tenant.
# ============================================================================
"""
TenantAgentFactory - Tenant-aware agent factory.

Extends agent filtering to respect per-tenant configuration from TenantConfig.
When TenantContext is active, filters enabled agents based on enabled_agent_types.

Features:
- Falls back to global ENABLED_AGENTS when no tenant context
- Respects tenant's enabled_agent_types configuration
- Empty enabled_agent_types = all global agents enabled
- Provides intersection of global and tenant-enabled agents
- NEW: Can load full agent registry from database via TenantAgentService

Usage:
    # During request with tenant context
    factory = TenantAgentFactory.from_context()
    enabled_agents = factory.get_enabled_agents()

    # Explicit tenant
    factory = TenantAgentFactory(enabled_agent_types=["greeting_agent", "product_agent"])
    enabled_agents = factory.get_enabled_agents()

    # With database session (full registry)
    factory = TenantAgentFactory.from_context(db=session)
    registry = await factory.get_agent_registry()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config.settings import get_settings
from app.core.tenancy.context import TenantContext, get_tenant_context

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.schemas.tenant_agent_config import AgentConfig, TenantAgentRegistry
    from app.core.tenancy.cache import TenantConfigCache

logger = logging.getLogger(__name__)


class TenantAgentFactory:
    """
    Tenant-aware agent filtering.

    Determines which agents are enabled based on:
    1. Global settings (ENABLED_AGENTS from settings)
    2. Tenant configuration (enabled_agent_types from TenantConfig)

    Logic:
    - No tenant context → Use global ENABLED_AGENTS
    - Tenant with empty enabled_agent_types → Use global ENABLED_AGENTS
    - Tenant with specific enabled_agent_types → Intersection with global

    Example:
        >>> # In request with tenant context
        >>> factory = TenantAgentFactory.from_context()
        >>> agents = factory.get_enabled_agents()
        ['greeting_agent', 'product_agent', 'fallback_agent']

        >>> # Check specific agent
        >>> factory.is_agent_enabled('support_agent')
        False
    """

    def __init__(
        self,
        enabled_agent_types: list[str] | None = None,
        ctx: TenantContext | None = None,
        db: AsyncSession | None = None,
        cache: TenantConfigCache | None = None,
    ):
        """
        Initialize tenant agent factory.

        Args:
            enabled_agent_types: Explicit list of tenant-enabled agents.
                If None, will try to get from TenantContext.
            ctx: TenantContext to use. If None, will try get_tenant_context().
            db: Optional database session for loading full registry.
            cache: Optional cache for tenant configurations.
        """
        self._explicit_agents = enabled_agent_types
        self._ctx = ctx
        self._db = db
        self._cache = cache
        self._settings = get_settings()
        self._registry: TenantAgentRegistry | None = None

    @classmethod
    def from_context(
        cls,
        db: AsyncSession | None = None,
        cache: TenantConfigCache | None = None,
    ) -> TenantAgentFactory:
        """
        Create factory from current TenantContext.

        Args:
            db: Optional database session for loading full registry.
            cache: Optional cache for tenant configurations.

        Returns:
            TenantAgentFactory with tenant-specific configuration.
        """
        ctx = get_tenant_context()
        return cls(ctx=ctx, db=db, cache=cache)

    @property
    def global_enabled_agents(self) -> list[str]:
        """Get global enabled agents from settings."""
        return list(self._settings.ENABLED_AGENTS)

    @property
    def tenant_enabled_agents(self) -> list[str] | None:
        """
        Get tenant-specific enabled agents.

        Returns:
            List of enabled agent names, or None if using global config.
        """
        # Explicit override takes precedence
        if self._explicit_agents is not None:
            return self._explicit_agents

        # Try to get from context
        ctx = self._ctx or get_tenant_context()
        if ctx and hasattr(ctx, "enabled_agents"):
            agents = ctx.enabled_agents
            # Convert frozenset to list if needed
            if isinstance(agents, (set, frozenset)):
                return list(agents)
            return agents if agents else None

        return None

    def get_enabled_agents(self) -> list[str]:
        """
        Get the effective list of enabled agents.

        Logic:
        1. If no tenant context or empty tenant config → Use global
        2. If tenant has specific agents → Intersection with global

        Returns:
            List of enabled agent names.
        """
        global_agents = set(self.global_enabled_agents)
        tenant_agents = self.tenant_enabled_agents

        # No tenant-specific config → use global
        if tenant_agents is None or len(tenant_agents) == 0:
            logger.debug(
                f"Using global agents (no tenant config): {sorted(global_agents)}"
            )
            return sorted(global_agents)

        # Tenant has specific config → intersection with global
        tenant_set = set(tenant_agents)
        enabled = global_agents.intersection(tenant_set)

        # Warn about agents that tenant wants but aren't globally enabled
        unavailable = tenant_set - global_agents
        if unavailable:
            logger.warning(
                f"Tenant requested agents not globally enabled: {unavailable}"
            )

        logger.debug(f"Tenant-filtered agents: {sorted(enabled)}")
        return sorted(enabled)

    def is_agent_enabled(self, agent_name: str) -> bool:
        """
        Check if a specific agent is enabled for the current tenant.

        Args:
            agent_name: Name of the agent to check.

        Returns:
            True if agent is enabled.
        """
        return agent_name in self.get_enabled_agents()

    def get_disabled_agents(self) -> list[str]:
        """
        Get list of agents that are disabled for this tenant.

        Returns:
            List of disabled agent names.
        """
        # All possible agents from global config
        all_agents = set(self.global_enabled_agents)
        enabled = set(self.get_enabled_agents())
        return sorted(all_agents - enabled)

    def get_agent_status(self) -> dict:
        """
        Get complete status of agents for this tenant.

        Returns:
            Dict with enabled, disabled, global, and tenant lists.
        """
        enabled = self.get_enabled_agents()
        disabled = self.get_disabled_agents()
        tenant_config = self.tenant_enabled_agents

        ctx = self._ctx or get_tenant_context()
        org_id = str(ctx.organization_id) if ctx else None

        return {
            "organization_id": org_id,
            "mode": "tenant" if tenant_config else "global",
            "enabled_agents": enabled,
            "disabled_agents": disabled,
            "enabled_count": len(enabled),
            "disabled_count": len(disabled),
            "global_config": self.global_enabled_agents,
            "tenant_config": tenant_config or [],
        }

    # =========================================================================
    # Async methods for full registry support (require db session)
    # =========================================================================

    async def get_agent_registry(self) -> TenantAgentRegistry:
        """
        Load complete agent registry for the current tenant.

        Requires db session to be provided.
        Uses TenantAgentService to load from database and merge with builtins.

        Returns:
            TenantAgentRegistry with all agents and computed indexes.

        Raises:
            ValueError: If no database session available.
            ValueError: If no tenant context available.
        """
        if self._registry is not None:
            return self._registry

        if self._db is None:
            raise ValueError("Database session required for get_agent_registry()")

        ctx = self._ctx or get_tenant_context()
        if ctx is None:
            raise ValueError("TenantContext required for get_agent_registry()")

        from app.core.tenancy.agent_service import TenantAgentService

        service = TenantAgentService(db=self._db, cache=self._cache)
        self._registry = await service.get_agent_registry(ctx.organization_id)
        return self._registry

    async def get_agent_config(self, agent_key: str) -> AgentConfig | None:
        """
        Get configuration for a specific agent.

        Args:
            agent_key: Agent key (e.g., "greeting_agent")

        Returns:
            AgentConfig or None if not found.
        """
        registry = await self.get_agent_registry()
        return registry.get_agent(agent_key)

    async def get_agent_for_intent(self, intent: str) -> str | None:
        """
        Get the agent key that handles a given intent.

        Args:
            intent: Intent name (e.g., "saludo")

        Returns:
            Agent key or None if no mapping found.
        """
        registry = await self.get_agent_registry()
        return registry.get_agent_for_intent(intent)

    async def get_agents_for_keyword(self, keyword: str) -> list[str]:
        """
        Get agent keys that might handle a given keyword.

        Args:
            keyword: Keyword to match

        Returns:
            List of agent keys that have this keyword.
        """
        registry = await self.get_agent_registry()
        return registry.get_agents_for_keyword(keyword)


def get_tenant_enabled_agents() -> list[str]:
    """
    Convenience function to get enabled agents for current tenant.

    Returns:
        List of enabled agent names.
    """
    factory = TenantAgentFactory.from_context()
    return factory.get_enabled_agents()


def is_agent_enabled_for_tenant(agent_name: str) -> bool:
    """
    Convenience function to check if agent is enabled for current tenant.

    Args:
        agent_name: Name of the agent to check.

    Returns:
        True if agent is enabled.
    """
    factory = TenantAgentFactory.from_context()
    return factory.is_agent_enabled(agent_name)


__all__ = [
    "TenantAgentFactory",
    "get_tenant_enabled_agents",
    "is_agent_enabled_for_tenant",
]
