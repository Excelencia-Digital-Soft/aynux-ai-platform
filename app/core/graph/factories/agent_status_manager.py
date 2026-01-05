"""Agent status management for graph."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.graph.factories.agent_factory import AgentFactory


class AgentStatusManager:
    """
    Manager for agent status information.

    Provides status queries:
    - Check if specific agent is enabled
    - Get lists of enabled/disabled agents
    - Complete status reporting
    """

    def __init__(
        self,
        enabled_agents: list[str],
        agents: dict[str, Any],
        agent_factory: "AgentFactory",
    ) -> None:
        """
        Initialize status manager with dependencies.

        Args:
            enabled_agents: List of enabled agent names from config
            agents: Dictionary of initialized agent instances
            agent_factory: Factory for agent name queries
        """
        self._enabled_agents = enabled_agents
        self._agents = agents
        self._agent_factory = agent_factory

    def is_agent_enabled(self, agent_name: str) -> bool:
        """
        Check if an agent is enabled in the graph.

        Args:
            agent_name: Name of the agent to check

        Returns:
            True if agent is enabled, False otherwise
        """
        return agent_name in self._enabled_agents and agent_name in self._agents

    def get_enabled_agents(self) -> list[str]:
        """
        Get list of enabled agent names.

        Returns:
            List of enabled agent names (excluding orchestrator and supervisor)
        """
        return self._agent_factory.get_enabled_agent_names()

    def get_disabled_agents(self) -> list[str]:
        """
        Get list of disabled agent names.

        Returns:
            List of disabled agent names
        """
        return self._agent_factory.get_disabled_agent_names()

    def get_agent_status(self) -> dict[str, Any]:
        """
        Get complete agent status information.

        Returns:
            Dictionary with enabled/disabled agents and statistics
        """
        enabled = self.get_enabled_agents()
        disabled = self.get_disabled_agents()

        return {
            "enabled_agents": enabled,
            "disabled_agents": disabled,
            "enabled_count": len(enabled),
            "disabled_count": len(disabled),
            "total_possible_agents": len(enabled) + len(disabled),
        }
