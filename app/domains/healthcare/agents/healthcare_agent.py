"""
Healthcare Agent

IAgent wrapper for the Healthcare domain graph.
Implements the standard agent interface for integration with SuperOrchestrator.
"""

import logging
from typing import Any

from app.core.interfaces.agent import AgentType, IAgent

from .graph import HealthcareGraph

logger = logging.getLogger(__name__)


class HealthcareAgent(IAgent):
    """
    Healthcare domain agent implementing IAgent interface.

    Wraps HealthcareGraph to provide consistent agent interface
    for the SuperOrchestrator and DependencyContainer.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize Healthcare agent.

        Args:
            config: Configuration dictionary for the healthcare graph
        """
        self._config = config or {}
        self._graph = HealthcareGraph(config=self._config)

        # Initialize the compiled graph
        self._graph.initialize()

        logger.info("HealthcareAgent initialized")

    @property
    def agent_type(self) -> AgentType:
        """Return agent type."""
        return AgentType.HEALTHCARE

    @property
    def agent_name(self) -> str:
        """Return agent name."""
        return "healthcare_agent"

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute healthcare agent with the given state.

        Args:
            state: Current conversation state

        Returns:
            Updated state after processing
        """
        try:
            logger.debug(f"HealthcareAgent executing with state keys: {list(state.keys())}")

            # Invoke the healthcare graph
            result = await self._graph.invoke(state)

            logger.debug("HealthcareAgent execution completed")
            return result

        except Exception as e:
            logger.error(f"Error in HealthcareAgent execution: {e}", exc_info=True)
            # Return error state
            return {
                **state,
                "error": str(e),
                "agent_response": f"Lo siento, hubo un error procesando tu consulta de salud: {e}",
            }

    async def validate_input(self, state: dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if state is valid
        """
        # Check required fields
        if "messages" not in state:
            logger.warning("HealthcareAgent: 'messages' field missing from state")
            return False

        messages = state.get("messages", [])
        if not messages:
            logger.warning("HealthcareAgent: 'messages' list is empty")
            return False

        return True

    async def health_check(self) -> dict[str, Any]:
        """
        Check agent health.

        Returns:
            Health status dictionary
        """
        try:
            graph_health = await self._graph.health_check()
            return {
                "status": "healthy",
                "agent": self.agent_name,
                "graph": graph_health,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "agent": self.agent_name,
                "error": str(e),
            }


__all__ = ["HealthcareAgent"]
