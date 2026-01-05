"""Tenant configuration management for graph execution."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.graph.factories.agent_factory import AgentFactory
    from app.core.schemas.tenant_agent_config import TenantAgentRegistry

logger = logging.getLogger(__name__)


class TenantConfigManager:
    """
    Manager for tenant configuration in multi-tenant mode.

    Handles:
    - Setting tenant registry for per-request configuration
    - Resetting to global defaults after request
    - Mode information reporting
    """

    def __init__(self, agent_factory: "AgentFactory") -> None:
        """
        Initialize tenant config manager.

        Args:
            agent_factory: Factory that holds and applies tenant config to agents
        """
        self._agent_factory = agent_factory

    def set_tenant_registry(self, registry: "TenantAgentRegistry | None") -> None:
        """
        Set tenant registry and apply configuration to all agents.

        Called per-request in multi-tenant mode to configure agents
        with tenant-specific settings from database.

        Args:
            registry: TenantAgentRegistry loaded from database

        Example:
            >>> # In webhook before processing
            >>> registry = await service.get_agent_registry(org_id)
            >>> tenant_manager.set_tenant_registry(registry)
            >>> result = await graph.invoke(message, ...)
        """
        if registry is None:
            logger.debug("No tenant registry provided, using global defaults")
            return

        # Update factory's registry
        self._agent_factory.set_tenant_registry(registry)

        # Apply tenant config to all agents
        self._agent_factory.apply_tenant_config_to_agents(registry)

        logger.info(f"Graph configured for tenant: {registry.organization_id}")

    def reset_tenant_config(self) -> None:
        """
        Reset all agents to global default configuration.

        Called after request processing to clean up tenant-specific
        configuration and prepare for next request.
        """
        self._agent_factory.reset_agents_to_defaults()
        logger.debug("Graph reset to global defaults")

    def get_mode_info(
        self, app_initialized: bool, enabled_agents: list[str]
    ) -> dict[str, Any]:
        """
        Get information about current graph operation mode.

        Args:
            app_initialized: Whether the graph app is compiled
            enabled_agents: List of enabled agent names from config

        Returns:
            Dict with mode info (global vs multi-tenant) and configuration state
        """
        factory_info = self._agent_factory.get_mode_info()

        return {
            **factory_info,
            "graph_initialized": app_initialized,
            "enabled_agents_config": enabled_agents,
        }
