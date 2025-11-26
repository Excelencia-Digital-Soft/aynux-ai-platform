"""
Factory for initializing and managing agents
"""

import logging
from typing import Any, Dict, List

# Import agents directly to avoid circular imports
from app.core.graph.agents.orchestrator_agent import OrchestratorAgent
from app.core.graph.agents.supervisor_agent import SupervisorAgent
from app.domains.shared.agents import (
    DataInsightsAgent,
    FallbackAgent,
    FarewellAgent,
    GreetingAgent,
    SupportAgent,
)
from app.domains.ecommerce.agents import ProductAgent
from app.domains.ecommerce.agents.nodes import (
    InvoiceNode as InvoiceAgent,
    PromotionsNode as PromotionsAgent,
    TrackingNode as TrackingAgent,
)
from app.domains.excelencia.agents import ExcelenciaAgent

logger = logging.getLogger(__name__)


class AgentFactory:
    """Factory class for creating and managing agent instances"""

    def __init__(self, ollama, postgres, config: Dict[str, Any]):
        self.ollama = ollama
        self.postgres = postgres
        self.config = config
        self.agents = {}

    def initialize_all_agents(self) -> Dict[str, Any]:
        """
        Initialize only enabled agents based on configuration.

        Orchestrator and Supervisor are always created as they are required for routing.
        Specialized agents are created only if enabled in configuration.
        """
        try:
            # Get enabled agents list from config (defaults to all agents)
            enabled_agents = self.config.get("enabled_agents", [])
            agent_configs = self.config.get("agents", {})

            # Always create orchestrator and supervisor (required for system)
            self.agents["orchestrator"] = OrchestratorAgent(ollama=self.ollama, config={})

            supervisor_config = self._get_supervisor_config()
            self.agents["supervisor"] = SupervisorAgent(ollama=self.ollama, config=supervisor_config)

            logger.info("Core agents (orchestrator, supervisor) initialized")

            # Agent builder registry - maps agent names to their initialization functions
            # This allows lazy initialization of only enabled agents
            agent_builders = {
                "greeting_agent": lambda: GreetingAgent(ollama=self.ollama, postgres=self.postgres, config={}),
                "product_agent": lambda: ProductAgent(
                    ollama=self.ollama, postgres=self.postgres, config=self._extract_config(agent_configs, "product")
                ),
                "data_insights_agent": lambda: DataInsightsAgent(
                    ollama=self.ollama,
                    postgres=self.postgres,
                    config=self._extract_config(agent_configs, "data_insights"),
                ),
                "promotions_agent": lambda: PromotionsAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "promotions")
                ),
                "tracking_agent": lambda: TrackingAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "tracking")
                ),
                "support_agent": lambda: SupportAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "support")
                ),
                "invoice_agent": lambda: InvoiceAgent(
                    ollama=self.ollama, config=self._extract_config(agent_configs, "invoice")
                ),
                "excelencia_agent": lambda: ExcelenciaAgent(
                    ollama=self.ollama,
                    postgres=self.postgres,
                    config=self._extract_config(agent_configs, "excelencia"),
                ),
                "fallback_agent": lambda: FallbackAgent(ollama=self.ollama, postgres=self.postgres, config={}),
                "farewell_agent": lambda: FarewellAgent(ollama=self.ollama, postgres=self.postgres, config={}),
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

    def _get_supervisor_config(self) -> Dict[str, Any]:
        """Extract supervisor configuration"""
        supervisor_config = self.config.get("supervisor", {})
        if hasattr(supervisor_config, "model_dump"):
            return supervisor_config.model_dump()
        return supervisor_config

    def _extract_config(self, agent_configs: Dict, agent_name: str) -> Dict[str, Any]:
        """Extract configuration for a specific agent"""
        config = agent_configs.get(agent_name, {})
        if hasattr(config, "model_dump"):
            return config.model_dump()
        return {}

    def get_agent(self, agent_name: str) -> Any:
        """Get a specific agent instance"""
        return self.agents.get(agent_name)

    def get_all_agents(self) -> Dict[str, Any]:
        """Get all agent instances"""
        return self.agents

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled and initialized"""
        return agent_name in self.agents

    def get_enabled_agent_names(self) -> List[str]:
        """Get list of all enabled agent names (excluding orchestrator and supervisor)"""
        return [name for name in self.agents.keys() if name not in ["orchestrator", "supervisor"]]

    def get_disabled_agent_names(self) -> List[str]:
        """Get list of all disabled agent names"""
        all_possible_agents = [
            "greeting_agent",
            "product_agent",
            "data_insights_agent",
            "promotions_agent",
            "tracking_agent",
            "support_agent",
            "invoice_agent",
            "excelencia_agent",
            "fallback_agent",
            "farewell_agent",
        ]
        return [name for name in all_possible_agents if name not in self.agents]
