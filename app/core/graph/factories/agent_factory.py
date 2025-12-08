"""
Factory for initializing and managing agents.

Supports DUAL-MODE operation:

1. GLOBAL MODE (no token):
   - Uses Python defaults from builtin_agents.py and environment config
   - No database lookups for agent configuration
   - Suitable for non-authenticated requests

2. MULTI-TENANT MODE (with token):
   - Uses TenantAgentRegistry loaded from database
   - Agent configurations (model, temperature, keywords, priority) from DB
   - Supports custom agent classes loaded dynamically
   - Applied per-request via apply_tenant_config_to_agents()

Usage:
    # Global mode initialization (no tenant)
    factory = AgentFactory(ollama, postgres, config)
    agents = factory.initialize_all_agents()

    # Multi-tenant mode initialization (with registry)
    factory = AgentFactory(ollama, postgres, config, tenant_registry=registry)
    agents = factory.initialize_all_agents()

    # Apply tenant config per-request (runtime)
    factory.apply_tenant_config_to_agents(registry)
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

# Import agents directly to avoid circular imports
from app.core.graph.agents.orchestrator_agent import OrchestratorAgent
from app.core.graph.agents.supervisor import SupervisorAgent

# E-commerce domain - new consolidated agent with subgraph
from app.domains.ecommerce.agents.ecommerce_agent import EcommerceAgent

# Legacy e-commerce nodes (kept for backward compatibility)
from app.domains.ecommerce.agents.nodes import (
    InvoiceNode as InvoiceAgent,
)
from app.domains.ecommerce.agents.nodes import (
    PromotionsNode as PromotionsAgent,
)
from app.domains.ecommerce.agents.nodes import (
    TrackingNode as TrackingAgent,
)
from app.domains.excelencia.agents import (
    ExcelenciaAgent,
    ExcelenciaInvoiceAgent,
    ExcelenciaPromotionsAgent,
    ExcelenciaSupportAgent,
)
from app.domains.shared.agents import (
    DataInsightsAgent,
    FallbackAgent,
    FarewellAgent,
    GreetingAgent,
    SupportAgent,
)

if TYPE_CHECKING:
    from app.core.agents.base_agent import BaseAgent
    from app.core.schemas.tenant_agent_config import AgentConfig, TenantAgentRegistry

logger = logging.getLogger(__name__)


# Registry of builtin agent classes (used for dynamic loading)
BUILTIN_AGENT_CLASSES: dict[str, type] = {
    # Always available agents (domain_key=None)
    "greeting_agent": GreetingAgent,
    "farewell_agent": FarewellAgent,
    "fallback_agent": FallbackAgent,
    "support_agent": SupportAgent,
    # Excelencia domain agents (domain_key="excelencia")
    "excelencia_agent": ExcelenciaAgent,
    "excelencia_invoice_agent": ExcelenciaInvoiceAgent,  # Client invoices
    "excelencia_promotions_agent": ExcelenciaPromotionsAgent,  # Software promotions
    "excelencia_support_agent": ExcelenciaSupportAgent,  # Software support/incidents
    "data_insights_agent": DataInsightsAgent,  # Moved to Excelencia domain
    # E-commerce domain agents (domain_key="ecommerce")
    "ecommerce_agent": EcommerceAgent,
    # Legacy e-commerce agents (deprecated)
    "promotions_agent": PromotionsAgent,
    "tracking_agent": TrackingAgent,
    "invoice_agent": InvoiceAgent,
}


class AgentFactory:
    """
    Factory class for creating and managing agent instances.

    Supports two modes of operation:
    1. Global mode (default): Uses enabled_agents from config
    2. Tenant mode: Uses TenantAgentRegistry for database-driven configuration

    Attributes:
        ollama: Ollama LLM integration
        postgres: PostgreSQL connection
        config: Global configuration dictionary
        agents: Dictionary of initialized agent instances
        enabled_agents: List of enabled agent names
        tenant_registry: Optional TenantAgentRegistry for tenant-specific config
    """

    def __init__(
        self,
        ollama,
        postgres,
        config: dict[str, Any],
        tenant_registry: TenantAgentRegistry | None = None,
    ):
        self.ollama = ollama
        self.postgres = postgres
        self.config = config
        self.agents: dict[str, Any] = {}
        self._tenant_registry = tenant_registry

        # Determine enabled agents and domains from registry or config
        if tenant_registry is not None:
            # Use tenant registry for enabled agents
            self.enabled_agents = [
                agent.agent_key for agent in tenant_registry.get_enabled_agents()
            ]
            logger.info(
                f"AgentFactory using TenantAgentRegistry for org {tenant_registry.organization_id}"
            )
        else:
            # Use global config
            self.enabled_agents = config.get("enabled_agents", [])

        # Get enabled domains from config (for filtering e-commerce services in greetings)
        self.enabled_domains: list[str] = config.get("enabled_domains", [])

    @property
    def tenant_registry(self) -> TenantAgentRegistry | None:
        """Get the tenant agent registry if available."""
        return self._tenant_registry

    def set_tenant_registry(self, registry: TenantAgentRegistry) -> None:
        """
        Set tenant registry and update enabled agents.

        Args:
            registry: TenantAgentRegistry to use for agent configuration.
        """
        self._tenant_registry = registry
        self.enabled_agents = [
            agent.agent_key for agent in registry.get_enabled_agents()
        ]
        logger.info(f"Updated tenant registry for org {registry.organization_id}")

    def get_agent_config_from_registry(self, agent_key: str) -> dict[str, Any]:
        """
        Get agent configuration from tenant registry if available.

        Args:
            agent_key: Agent key (e.g., "greeting_agent")

        Returns:
            Agent configuration dict merged with registry config.
        """
        base_config: dict[str, Any] = {}

        if self._tenant_registry is not None:
            agent = self._tenant_registry.get_agent(agent_key)
            if agent:
                # Merge registry config with any custom config
                base_config = {
                    "keywords": agent.keywords,
                    "priority": agent.priority,
                    "intent_patterns": [p.model_dump() for p in agent.intent_patterns],
                    **agent.config,
                }

        return base_config

    def initialize_all_agents(self) -> dict[str, Any]:
        """
        Initialize only enabled agents based on configuration.

        Orchestrator and Supervisor are always created as they are required for routing.
        Specialized agents are created only if enabled in configuration.

        When tenant_registry is set, uses registry config for agent initialization.
        """
        try:
            # Use self.enabled_agents which respects tenant_registry if set
            enabled_agents = self.enabled_agents
            agent_configs = self.config.get("agents", {})

            # Always create orchestrator and supervisor (required for system)
            self.agents["orchestrator"] = OrchestratorAgent(ollama=self.ollama, config={})

            supervisor_config = self._get_supervisor_config()
            self.agents["supervisor"] = SupervisorAgent(ollama=self.ollama, config=supervisor_config)

            logger.info("Core agents (orchestrator, supervisor) initialized")

            # Agent builder registry - maps agent names to their initialization functions
            # This allows lazy initialization of only enabled agents
            agent_builders = {
                "greeting_agent": lambda: GreetingAgent(
                    ollama=self.ollama,
                    postgres=self.postgres,
                    config={
                        "enabled_agents": self.enabled_agents,
                        "enabled_domains": self.enabled_domains,
                    },
                ),
                # E-commerce domain - consolidated agent with subgraph
                # Replaces individual product_agent, promotions_agent, tracking_agent, invoice_agent
                "ecommerce_agent": lambda: EcommerceAgent(
                    config={
                        **self._extract_config(agent_configs, "ecommerce"),
                        "integrations": {"postgres": {}},
                    }
                ),
                # Legacy e-commerce agents (deprecated - kept for backward compatibility)
                # ProductAgent requires: product_repository, vector_store, llm
                # It should be created via DependencyContainer.create_product_agent()
                "product_agent": lambda: None,  # Placeholder - use DependencyContainer or ecommerce_agent
                "promotions_agent": lambda: PromotionsAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "promotions")
                ),
                "tracking_agent": lambda: TrackingAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "tracking")
                ),
                "invoice_agent": lambda: InvoiceAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "invoice")
                ),
                # Other domain agents
                "data_insights_agent": lambda: DataInsightsAgent(
                    ollama=self.ollama,
                    postgres=self.postgres,
                    config=self._extract_config(agent_configs, "data_insights"),
                ),
                "support_agent": lambda: SupportAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "support")
                ),
                "excelencia_agent": lambda: ExcelenciaAgent(
                    config=self._extract_config(agent_configs, "excelencia"),
                ),
                # NEW: Excelencia domain agents (independent agents)
                "excelencia_invoice_agent": lambda: ExcelenciaInvoiceAgent(
                    ollama=self.ollama,
                    config=self._extract_config(agent_configs, "excelencia_invoice"),
                ),
                "excelencia_promotions_agent": lambda: ExcelenciaPromotionsAgent(
                    ollama=self.ollama,
                    config=self._extract_config(agent_configs, "excelencia_promotions"),
                ),
                "excelencia_support_agent": lambda: ExcelenciaSupportAgent(
                    ollama=self.ollama,
                    config=self._extract_config(agent_configs, "excelencia_support"),
                ),
                "fallback_agent": lambda: FallbackAgent(
                    ollama=self.ollama,
                    postgres=self.postgres,
                    config={"enabled_agents": self.enabled_agents},
                ),
                "farewell_agent": lambda: FarewellAgent(
                    ollama=self.ollama, postgres=self.postgres, config={}
                ),
            }

            # Initialize only enabled agents
            enabled_count = 0
            disabled_count = 0

            for agent_name in agent_builders.keys():
                if agent_name in enabled_agents:
                    # Agent is enabled - create instance
                    self.agents[agent_name] = agent_builders[agent_name]()
                    logger.info(f"✓ Enabled agent: {agent_name}")
                    enabled_count += 1
                else:
                    # Agent is disabled - skip initialization
                    logger.info(f"✗ Disabled agent: {agent_name}")
                    disabled_count += 1

            # Log any unknown agents in config
            for agent_name in enabled_agents:
                if agent_name not in agent_builders:
                    logger.warning(f"⚠ Unknown agent in enabled_agents config: {agent_name}")

            total_agents = len(self.agents)
            logger.info(
                f"Agent initialization complete: {total_agents} total "
                f"({enabled_count} enabled, {disabled_count} disabled). "
                f"Active agents: {list(self.agents.keys())}"
            )

            return self.agents

        except Exception as e:
            logger.error(f"Error initializing agents: {e}")
            raise

    def _get_supervisor_config(self) -> dict[str, Any]:
        """Extract supervisor configuration."""
        supervisor_config = self.config.get("supervisor", {})
        if hasattr(supervisor_config, "model_dump"):
            return supervisor_config.model_dump()
        return supervisor_config

    def _extract_config(self, agent_configs: dict, agent_name: str) -> dict[str, Any]:
        """
        Extract configuration for a specific agent.

        Merges global config with tenant registry config if available.
        """
        # Start with global config
        config = agent_configs.get(agent_name, {})
        if hasattr(config, "model_dump"):
            base_config = config.model_dump()
        else:
            base_config = dict(config) if config else {}

        # Merge with tenant registry config if available
        registry_config = self.get_agent_config_from_registry(agent_name)
        if registry_config:
            base_config = {**base_config, **registry_config}

        return base_config

    def get_agent(self, agent_name: str) -> Any:
        """Get a specific agent instance."""
        return self.agents.get(agent_name)

    def get_all_agents(self) -> dict[str, Any]:
        """Get all agent instances."""
        return self.agents

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled and initialized."""
        return agent_name in self.agents

    def get_enabled_agent_names(self) -> list[str]:
        """Get list of all enabled agent names (excluding orchestrator and supervisor)."""
        return [name for name in self.agents.keys() if name not in ["orchestrator", "supervisor"]]

    def get_disabled_agent_names(self) -> list[str]:
        """Get list of all disabled agent names."""
        all_possible_agents = [
            # Always available agents (domain_key=None)
            "greeting_agent",
            "farewell_agent",
            "fallback_agent",
            "support_agent",
            # Excelencia domain agents (domain_key="excelencia")
            "excelencia_agent",
            "excelencia_invoice_agent",  # NEW: Client invoices
            "excelencia_promotions_agent",  # NEW: Software promotions
            "data_insights_agent",
            # E-commerce domain agents (domain_key="ecommerce")
            "ecommerce_agent",
            # Legacy agents (deprecated)
            "product_agent",
            "promotions_agent",
            "tracking_agent",
            "invoice_agent",
        ]
        return [name for name in all_possible_agents if name not in self.agents]

    # =========================================================================
    # Dual-Mode Methods (Global vs Multi-Tenant)
    # =========================================================================

    def apply_tenant_config_to_agents(self, registry: TenantAgentRegistry) -> None:
        """
        Apply tenant-specific configuration to all initialized agents.

        Called per-request in multi-tenant mode to update agent configurations
        from database values. This allows runtime configuration without
        reinitializing agents.

        Args:
            registry: TenantAgentRegistry with agent configurations for tenant

        Example:
            >>> # In webhook handler after resolving tenant
            >>> registry = await tenant_service.get_agent_registry(org_id)
            >>> factory.apply_tenant_config_to_agents(registry)
        """
        if registry is None:
            logger.debug("No tenant registry provided, agents using defaults")
            return

        applied_count = 0
        for agent_key, agent in self.agents.items():
            # Skip orchestrator and supervisor (system agents)
            if agent_key in ("orchestrator", "supervisor"):
                continue

            # Get tenant config for this agent
            agent_config = registry.get_agent(agent_key)
            if agent_config and hasattr(agent, "apply_tenant_config"):
                agent.apply_tenant_config(agent_config)
                applied_count += 1

        logger.info(
            f"Applied tenant config to {applied_count} agents "
            f"for org {registry.organization_id}"
        )

    def reset_agents_to_defaults(self) -> None:
        """
        Reset all agents to their global default configuration.

        Called after request processing in multi-tenant mode to ensure
        agents don't retain tenant-specific configuration for next request.
        """
        reset_count = 0
        for agent_key, agent in self.agents.items():
            if agent_key in ("orchestrator", "supervisor"):
                continue

            if hasattr(agent, "reset_to_defaults"):
                agent.reset_to_defaults()
                reset_count += 1

        logger.debug(f"Reset {reset_count} agents to default configuration")

    def _load_custom_agent_class(self, agent_config: AgentConfig) -> type | None:
        """
        Dynamically load a custom agent class from module path.

        Args:
            agent_config: AgentConfig with agent_class path

        Returns:
            Agent class or None if loading fails

        Example:
            >>> config = AgentConfig(agent_class="app.agents.custom.MyAgent", ...)
            >>> agent_class = factory._load_custom_agent_class(config)
            >>> agent = agent_class(ollama=self.ollama, config=config.config)
        """
        if not agent_config.agent_class:
            return None

        try:
            # Split module path and class name
            module_path, class_name = agent_config.agent_class.rsplit(".", 1)

            # Import module and get class
            module = importlib.import_module(module_path)
            agent_class = getattr(module, class_name)

            logger.info(f"Loaded custom agent class: {agent_config.agent_class}")
            return agent_class

        except (ImportError, AttributeError, ValueError) as e:
            logger.error(
                f"Failed to load custom agent class '{agent_config.agent_class}': {e}"
            )
            return None

    def create_agent_from_config(
        self, agent_config: AgentConfig
    ) -> BaseAgent | None:
        """
        Create an agent instance from AgentConfig.

        Supports both builtin and custom agent types.

        Args:
            agent_config: Configuration from database or builtin defaults

        Returns:
            Initialized agent instance or None if creation fails
        """
        agent_key = agent_config.agent_key

        # Try to get builtin agent class
        if agent_config.agent_type == "builtin":
            agent_class = BUILTIN_AGENT_CLASSES.get(agent_key)
        else:
            # Try to load custom agent class
            agent_class = self._load_custom_agent_class(agent_config)

        if not agent_class:
            logger.warning(f"No agent class found for {agent_key}")
            return None

        try:
            # Create agent with merged config
            agent_instance = agent_class(
                ollama=self.ollama,
                postgres=self.postgres,
                config={
                    **agent_config.config,
                    "enabled_agents": self.enabled_agents,
                    "enabled_domains": self.enabled_domains,
                },
            )

            # Apply tenant config immediately
            if hasattr(agent_instance, "apply_tenant_config"):
                agent_instance.apply_tenant_config(agent_config)

            logger.info(f"Created agent from config: {agent_key}")
            return agent_instance

        except Exception as e:
            logger.error(f"Failed to create agent {agent_key}: {e}", exc_info=True)
            return None

    def get_mode_info(self) -> dict[str, Any]:
        """
        Get information about current factory mode.

        Returns:
            Dict with mode information and configuration state
        """
        has_registry = self._tenant_registry is not None
        org_id = str(self._tenant_registry.organization_id) if has_registry else None

        return {
            "mode": "multi_tenant" if has_registry else "global",
            "organization_id": org_id,
            "enabled_agents": self.enabled_agents,
            "initialized_agents": list(self.agents.keys()),
            "tenant_registry_loaded": has_registry,
        }
