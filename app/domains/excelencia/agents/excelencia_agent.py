"""
Excelencia Agent

IAgent wrapper for the Excelencia ERP domain graph.
Implements the standard agent interface for integration with SuperOrchestrator.
"""

from __future__ import annotations

from typing import Any

from app.core.interfaces.agent import AgentType, IAgent

from .graph import ExcelenciaGraph


class ExcelenciaAgent(IAgent):
    """
    Excelencia ERP domain agent implementing IAgent interface.

    Wraps ExcelenciaGraph to provide consistent agent interface
    for the SuperOrchestrator and DependencyContainer.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize Excelencia agent.

        Args:
            config: Configuration dictionary for the excelencia graph
        """
        self._config = config or {}
        self._graph = ExcelenciaGraph(config=self._config)

        # Initialize the compiled graph
        self._graph.initialize()

    @property
    def agent_type(self) -> AgentType:
        """Return agent type."""
        return AgentType.EXCELENCIA

    @property
    def agent_name(self) -> str:
        """Return agent name."""
        return "excelencia_agent"

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute Excelencia agent with the given state.

        Args:
            state: Current conversation state

        Returns:
            Updated state after processing
        """
        try:
            # Invoke the excelencia graph
            return await self._graph.invoke(state)

        except Exception as exc:
            # Return error state
            return {
                **state,
                "error": str(exc),
                "agent_response": f"Lo siento, hubo un error procesando tu consulta sobre Excelencia ERP: {exc}",
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
            return False

        messages = state.get("messages", [])
        if not messages:
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
        except Exception as exc:
            return {
                "status": "unhealthy",
                "agent": self.agent_name,
                "error": str(exc),
            }


__all__ = ["ExcelenciaAgent"]
