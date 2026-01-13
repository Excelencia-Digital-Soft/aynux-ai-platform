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

        Uses generic domain state management to extract and merge
        pharmacy-specific state from the orchestration state.

        Args:
            message: User message to process
            state_dict: Current state dictionary

        Returns:
            Updated state from subgraph execution
        """
        from app.orchestration.state import (
            extract_domain_fields_from_result,
            get_domain_state,
            update_domain_state,
        )

        try:
            # Ensure graph is initialized with checkpointer
            graph = await self._ensure_graph_initialized()

            # Extract pharmacy state from generic domain_states container
            pharmacy_state = get_domain_state(state_dict, "pharmacy")

            # Extract user phone from multiple possible sources
            user_phone = (
                state_dict.get("customer_id")
                or state_dict.get("user_id")
                or state_dict.get("user_phone")
                or state_dict.get("sender")
            )

            # Build subgraph kwargs from common fields + domain state
            # IMPORTANT: Only pass non-None values to avoid overriding checkpointer state.
            # If we pass customer_name=None, it would override a saved value from checkpoint.
            subgraph_kwargs: dict[str, Any] = {}

            # Add required fields (always passed)
            subgraph_kwargs["conversation_id"] = state_dict.get("conversation_id")

            # Add optional fields only if they have values
            if user_phone:
                subgraph_kwargs["customer_id"] = user_phone
                subgraph_kwargs["whatsapp_phone"] = user_phone

            if state_dict.get("customer_name"):
                subgraph_kwargs["customer_name"] = state_dict["customer_name"]

            if state_dict.get("organization_id"):
                subgraph_kwargs["organization_id"] = state_dict["organization_id"]

            if state_dict.get("is_bypass_route"):
                subgraph_kwargs["is_bypass_route"] = state_dict["is_bypass_route"]

            # CRITICAL: Pass pharmacy config fields from root state (set by bypass routing)
            # These are in root state, NOT in domain_states
            if state_dict.get("pharmacy_id"):
                subgraph_kwargs["pharmacy_id"] = state_dict["pharmacy_id"]

            if state_dict.get("pharmacy_name"):
                subgraph_kwargs["pharmacy_name"] = state_dict["pharmacy_name"]

            if state_dict.get("pharmacy_phone"):
                subgraph_kwargs["pharmacy_phone"] = state_dict["pharmacy_phone"]

            # Spread pharmacy-specific state from domain_states (already filtered by get_domain_state)
            # These values come from parent graph's checkpointer
            subgraph_kwargs.update(pharmacy_state)

            # Log for debugging state persistence
            logger.info(
                f"[PHARMACY_AGENT] Invoking subgraph with "
                f"conversation_id={subgraph_kwargs.get('conversation_id')}, "
                f"pharmacy_id={subgraph_kwargs.get('pharmacy_id')}"
            )

            # Invoke subgraph
            result = await graph.invoke(
                message=message,
                **subgraph_kwargs,
            )

            # Extract pharmacy-specific fields from result
            pharmacy_result_fields = extract_domain_fields_from_result(result, "pharmacy")

            # Build agent tracking updates
            agent_history = state_dict.get("agent_history", [])
            if self.agent_name not in agent_history:
                agent_history = agent_history + [self.agent_name]

            # Merge result: messages go to root, pharmacy fields to domain_states
            domain_state_update = update_domain_state(
                state_dict, "pharmacy", pharmacy_result_fields
            )

            return {
                "messages": result.get("messages", []),
                "current_agent": self.agent_name,
                "agent_history": agent_history,
                **domain_state_update,
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
