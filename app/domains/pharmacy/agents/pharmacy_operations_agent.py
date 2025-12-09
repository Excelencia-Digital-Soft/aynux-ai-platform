"""
Pharmacy Operations Agent

Main agent for the Pharmacy domain that wraps the PharmacyGraph subgraph.
Extends BaseAgent for consistent agent behavior.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage

from app.core.agents import BaseAgent
from app.domains.pharmacy.agents.graph import PharmacyGraph

logger = logging.getLogger(__name__)


class PharmacyOperationsAgent(BaseAgent):
    """
    Pharmacy Operations Agent - Entry point for pharmacy domain.

    Wraps the PharmacyGraph subgraph for handling transactional
    pharmacy workflows:
    - Consulta Deuda (Check Debt)
    - Confirmar (Confirm)
    - Generar Factura (Generate Invoice)

    This agent is designed to be routed to via bypass routing
    for dedicated pharmacy WhatsApp numbers.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize pharmacy operations agent.

        Args:
            config: Agent configuration options
        """
        super().__init__("pharmacy_operations_agent", config or {})

        # Initialize pharmacy subgraph
        self._graph = PharmacyGraph(config)
        self._graph.initialize()

        logger.info("PharmacyOperationsAgent initialized with subgraph")

    @property
    def agent_name(self) -> str:
        """Agent name."""
        return "pharmacy_operations_agent"

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process message through the pharmacy subgraph.

        Args:
            message: User message to process
            state_dict: Current state dictionary

        Returns:
            Updated state from subgraph execution
        """
        try:
            # Pass relevant state to subgraph
            subgraph_kwargs = {
                "customer_id": state_dict.get("customer_id") or state_dict.get("user_id"),
                "customer_name": state_dict.get("customer_name"),
                "conversation_id": state_dict.get("conversation_id"),
                "is_bypass_route": state_dict.get("is_bypass_route", False),
                # Carry over workflow state
                "debt_id": state_dict.get("debt_id"),
                "debt_data": state_dict.get("debt_data"),
                "debt_status": state_dict.get("debt_status"),
                "total_debt": state_dict.get("total_debt"),
                "has_debt": state_dict.get("has_debt", False),
                "awaiting_confirmation": state_dict.get("awaiting_confirmation", False),
                "confirmation_received": state_dict.get("confirmation_received", False),
                "invoice_number": state_dict.get("invoice_number"),
                "pdf_url": state_dict.get("pdf_url"),
            }

            # Invoke subgraph
            result = await self._graph.invoke(
                message=message,
                **subgraph_kwargs,
            )

            # Merge subgraph result with agent tracking
            agent_history = state_dict.get("agent_history", [])
            if self.agent_name not in agent_history:
                agent_history = agent_history + [self.agent_name]

            return {
                **result,
                "current_agent": self.agent_name,
                "agent_history": agent_history,
            }

        except Exception as e:
            logger.error(
                f"Error in PharmacyOperationsAgent: {e}",
                exc_info=True,
            )
            return self._error_response(str(e), state_dict)

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute pharmacy agent logic.

        This method is called by the main graph when routing to this agent.

        Args:
            state: Current conversation state

        Returns:
            Updated state from agent execution
        """
        try:
            # Extract message
            messages = state.get("messages", [])
            if not messages:
                return self._error_response("No message provided", state)

            last_message = messages[-1]
            message_content = (
                last_message.content
                if hasattr(last_message, "content")
                else str(last_message.get("content", ""))
            )

            # Process through internal handler
            return await self._process_internal(str(message_content), state)

        except Exception as e:
            logger.error(
                f"Error in PharmacyOperationsAgent.execute: {e}",
                exc_info=True,
            )
            return self._error_response(str(e), state)

    async def validate_input(self, state: dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if valid, False otherwise
        """
        messages = state.get("messages", [])
        return bool(messages)

    def _error_response(
        self,
        error: str,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate error response.

        Args:
            error: Error message
            state: Current state

        Returns:
            Error state update
        """
        logger.error(f"Pharmacy agent error: {error}")
        return {
            "messages": [
                AIMessage(
                    content="Disculpa, tuve un problema. Podrias intentar de nuevo?"
                )
            ],
            "current_agent": self.agent_name,
            "error_count": state.get("error_count", 0) + 1,
            "error": error,
        }

    async def health_check(self) -> dict[str, Any]:
        """
        Check health of the pharmacy agent and its subgraph.

        Returns:
            Health status dictionary
        """
        subgraph_health = await self._graph.health_check()

        return {
            "agent": self.agent_name,
            "status": "healthy" if subgraph_health.get("graph_compiled") else "unhealthy",
            "subgraph": subgraph_health,
        }
