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
from app.integrations.databases import PostgreSQLIntegration

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

        # Initialize pharmacy subgraph (lazy init for async checkpointer)
        self._graph: PharmacyGraph | None = None
        self._postgres: PostgreSQLIntegration | None = None
        self._graph_initialized = False
        self._agent_config = config

        logger.info("PharmacyOperationsAgent initialized (graph will be initialized lazily)")

    @property
    def agent_name(self) -> str:
        """Agent name."""
        return "pharmacy_operations_agent"

    async def _ensure_graph_initialized(self) -> PharmacyGraph:
        """
        Ensure the pharmacy graph is initialized with PostgreSQL checkpointer.

        This lazy initialization allows us to use async checkpointer setup.

        Returns:
            Initialized PharmacyGraph instance
        """
        if self._graph is None or not self._graph_initialized:
            # Create PostgreSQL integration for checkpointer
            if self._postgres is None:
                self._postgres = PostgreSQLIntegration()

            # Create and initialize graph with checkpointer
            self._graph = PharmacyGraph(self._agent_config)
            await self._graph.initialize(postgres=self._postgres)
            self._graph_initialized = True
            logger.info("PharmacyGraph initialized with PostgreSQL checkpointer")

        return self._graph

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
            # Ensure graph is initialized with checkpointer
            graph = await self._ensure_graph_initialized()

            # Pass relevant state to subgraph
            # Extract user phone from multiple possible sources (context_middleware uses user_phone/sender)
            user_phone = (
                state_dict.get("customer_id")
                or state_dict.get("user_id")
                or state_dict.get("user_phone")
                or state_dict.get("sender")
            )
            subgraph_kwargs = {
                "customer_id": user_phone,
                "customer_name": state_dict.get("customer_name"),
                "conversation_id": state_dict.get("conversation_id"),
                "is_bypass_route": state_dict.get("is_bypass_route", False),
                # Customer identification state (CRITICAL for persistence)
                "customer_identified": state_dict.get("customer_identified", False),
                "plex_customer_id": state_dict.get("plex_customer_id"),
                "plex_customer": state_dict.get("plex_customer"),
                "whatsapp_phone": state_dict.get("whatsapp_phone") or user_phone,
                # Pharmacy configuration (CRITICAL - must propagate for multi-turn)
                "pharmacy_id": state_dict.get("pharmacy_id"),
                "pharmacy_name": state_dict.get("pharmacy_name"),
                "pharmacy_phone": state_dict.get("pharmacy_phone"),
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
            result = await graph.invoke(
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
        graph = await self._ensure_graph_initialized()
        subgraph_health = await graph.health_check()

        return {
            "agent": self.agent_name,
            "status": "healthy" if subgraph_health.get("graph_compiled") else "unhealthy",
            "subgraph": subgraph_health,
        }
