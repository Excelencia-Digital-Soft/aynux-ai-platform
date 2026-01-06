"""
E-commerce Agent

Parent agent that wraps the EcommerceSubgraph for integration with the main AynuxGraph.
Uses the wrapper function pattern for state transformation between LangGraphState and EcommerceState.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.core.graph.state_schema import LangGraphState

from .graph import EcommerceGraph

logger = logging.getLogger(__name__)


class EcommerceAgent:
    """
    Parent agent that wraps the EcommerceSubgraph.

    This agent acts as a single entry point for all e-commerce intents in the main graph.
    It transforms state between LangGraphState (main graph) and EcommerceState (subgraph),
    invokes the subgraph, and transforms the result back.

    Architecture:
        AynuxGraph
        └── ecommerce_agent (this class)
            └── EcommerceSubgraph
                ├── ecommerce_router (LLM-based)
                ├── product_node
                ├── promotions_node
                ├── tracking_node
                └── invoice_node
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the E-commerce agent.

        Args:
            config: Configuration dictionary with:
                - enabled_nodes: List of enabled subgraph nodes
                - router: Router configuration (confidence_threshold, etc.)
                - max_errors: Maximum errors before failing
                - integrations: vLLM and PostgreSQL settings
        """
        self.config = config or {}
        self.name = "ecommerce_agent"

        # Initialize and compile the subgraph
        self.subgraph = EcommerceGraph(config)
        self.subgraph.initialize()
        self.compiled_subgraph = self.subgraph.app

        logger.info(
            f"EcommerceAgent initialized with subgraph nodes: "
            f"{self.subgraph.get_enabled_nodes()}"
        )

    async def process(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Process a message through the e-commerce subgraph.

        This is the main entry point called by the NodeExecutor.

        Args:
            message: User message
            state_dict: Current LangGraphState as dictionary

        Returns:
            Updated state dictionary with e-commerce response
        """
        try:
            # Transform to EcommerceState
            ecommerce_input = self._transform_to_ecommerce_state(message, state_dict)

            # Invoke subgraph
            result = await self.compiled_subgraph.ainvoke(ecommerce_input)

            # Transform back to LangGraphState format
            return self._transform_to_langgraph_state(result, state_dict)

        except Exception as e:
            logger.error(f"Error in EcommerceAgent.process: {e}")
            return self._create_error_response(str(e), state_dict)

    async def invoke(self, state: LangGraphState) -> dict[str, Any]:
        """
        Wrapper function for LangGraph node integration.

        This method is used when adding the agent directly as a node.

        Args:
            state: LangGraphState from main graph

        Returns:
            State updates for main graph
        """
        try:
            # Extract message from state
            messages = state.get("messages", [])
            if not messages:
                return {"is_complete": True}

            last_message = messages[-1]
            message_content = (
                last_message.content
                if hasattr(last_message, "content")
                else str(last_message)
            )

            # Process through subgraph
            return await self.process(message_content, dict(state))

        except Exception as e:
            logger.error(f"Error in EcommerceAgent.invoke: {e}")
            return self._create_error_response(str(e), dict(state))

    def _transform_to_ecommerce_state(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Transform LangGraphState to EcommerceState format.

        Maps common fields and extracts e-commerce specific context.

        Args:
            message: User message
            state_dict: LangGraphState as dictionary

        Returns:
            Dictionary compatible with EcommerceState
        """
        # Start with base message
        ecommerce_state: dict[str, Any] = {
            "messages": [HumanMessage(content=message)],
            "conversation_id": state_dict.get("conversation_id"),
            "timestamp": datetime.now().isoformat(),
            "is_complete": False,
            "error_count": 0,
            "max_errors": self.config.get("max_errors", 3),
        }

        # Transfer customer context if available
        if customer_data := state_dict.get("customer_data"):
            ecommerce_state["customer"] = customer_data

        # Transfer cart context if available
        if cart := state_dict.get("cart"):
            ecommerce_state["cart"] = cart

        # Transfer any existing e-commerce context
        if product_context := state_dict.get("product_context"):
            ecommerce_state["product_context"] = product_context

        if current_order := state_dict.get("current_order"):
            ecommerce_state["current_order"] = current_order

        return ecommerce_state

    def _transform_to_langgraph_state(
        self,
        result: dict[str, Any],
        original_state: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Transform EcommerceState result back to LangGraphState format.

        Extracts response messages and merges e-commerce specific data.

        Args:
            result: Result from EcommerceSubgraph
            original_state: Original LangGraphState

        Returns:
            State updates for main graph
        """
        state_updates: dict[str, Any] = {
            "current_agent": self.name,
        }

        # Extract and transform messages
        if result_messages := result.get("messages"):
            # Get the last AI message from the subgraph
            ai_messages = [
                msg for msg in result_messages
                if isinstance(msg, AIMessage) or (
                    isinstance(msg, dict) and msg.get("role") == "assistant"
                )
            ]
            if ai_messages:
                last_response = ai_messages[-1]
                content = (
                    last_response.content
                    if hasattr(last_response, "content")
                    else last_response.get("content", "")
                )
                state_updates["messages"] = [AIMessage(content=content)]

        # Transfer agent responses
        if agent_responses := result.get("agent_responses"):
            state_updates["agent_responses"] = agent_responses

        # Merge retrieved data
        retrieved_data = original_state.get("retrieved_data", {})
        if new_data := result.get("retrieved_data"):
            retrieved_data = {**retrieved_data, **new_data}
        if search_results := result.get("search_results"):
            retrieved_data["search_results"] = search_results
        if tracking_info := result.get("tracking_info"):
            retrieved_data["tracking_info"] = tracking_info
        if active_promotions := result.get("active_promotions"):
            retrieved_data["active_promotions"] = active_promotions
        if invoice_info := result.get("invoice_info"):
            retrieved_data["invoice_info"] = invoice_info

        if retrieved_data:
            state_updates["retrieved_data"] = retrieved_data

        # Transfer routing decision for supervisor
        if routing_decision := result.get("routing_decision"):
            state_updates["ecommerce_routing"] = routing_decision

        # Transfer error state if any
        if result.get("error_count", 0) > 0:
            state_updates["error_count"] = original_state.get("error_count", 0) + 1

        return state_updates

    def _create_error_response(
        self,
        error_message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """Create error response when processing fails."""
        return {
            "current_agent": self.name,
            "messages": [
                AIMessage(
                    content="Disculpa, tuve un problema procesando tu consulta de e-commerce. "
                    "Por favor, intenta de nuevo."
                )
            ],
            "error_count": state_dict.get("error_count", 0) + 1,
            "agent_responses": [
                {
                    "agent": self.name,
                    "status": "error",
                    "error": error_message,
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

    def get_enabled_nodes(self) -> list[str]:
        """Get list of enabled subgraph node names."""
        return self.subgraph.get_enabled_nodes()

    async def health_check(self) -> dict[str, Any]:
        """Check health of the e-commerce subgraph."""
        try:
            subgraph_health = await self.subgraph.health_check()
            return {
                "agent": self.name,
                "healthy": subgraph_health.get("healthy", False),
                "subgraph_nodes": subgraph_health.get("nodes", {}),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "agent": self.name,
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
