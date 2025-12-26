"""
Excelencia Agent

Simplified agent for the Excelencia Software domain.
Implements the standard agent interface for integration with SuperOrchestrator.

This agent handles:
- Company information (mission, vision, values)
- ERP module information and queries
- Demo requests and presentations
- Training and support queries

Note: Invoicing and promotions are handled by separate agents:
- ExcelenciaInvoiceAgent: Client invoicing and collections
- ExcelenciaPromotionsAgent: Software promotions and discounts
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.core.interfaces.agent import AgentType
from app.core.utils.tracing import trace_async_method
from app.integrations.llm import OllamaLLM

from .nodes import ExcelenciaNode

logger = logging.getLogger(__name__)


class ExcelenciaAgent(BaseAgent):
    """
    Excelencia Software domain agent implementing BaseAgent interface.

    This is a simplified agent that directly uses ExcelenciaNode
    for processing queries about the ERP system.

    Focuses on:
    - Company information (mission, vision, values)
    - Module information and queries
    - Demo requests
    - General ERP questions

    Note: Invoicing and promotions have been separated into dedicated agents.
    """

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        """
        Initialize Excelencia agent.

        Args:
            ollama: OllamaLLM instance for LLM calls
            config: Configuration dictionary
        """
        super().__init__("excelencia_agent", config or {}, ollama=ollama)

        self.ollama = ollama or OllamaLLM()
        self._config = config or {}

        # Initialize the main processing node
        self._node = ExcelenciaNode(
            ollama=self.ollama,
            config=self._config.get("node_config", {}),
        )

        logger.info("ExcelenciaAgent initialized (simplified architecture)")

    @property
    def agent_type(self) -> AgentType:
        """Return agent type."""
        return AgentType.EXCELENCIA

    @property
    def agent_name(self) -> str:
        """Return agent name."""
        return "excelencia_agent"

    @trace_async_method(
        name="excelencia_agent_process",
        run_type="chain",
        metadata={"agent_type": "excelencia", "domain": "excelencia"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Process Excelencia domain queries.

        Delegates to ExcelenciaNode for actual processing.

        Args:
            message: User message to process
            state_dict: Current conversation state

        Returns:
            Dictionary with response and metadata
        """
        try:
            logger.info(f"ExcelenciaAgent processing: {message[:50]}...")

            # Delegate to the node for processing
            result = await self._node.process(message, state_dict)

            logger.info(f"ExcelenciaAgent result keys: {list(result.keys())}")

            # Ensure proper response format
            response_text = ""
            if result.get("messages"):
                messages = result["messages"]
                if messages and isinstance(messages[0], dict):
                    response_text = messages[0].get("content", "")
                elif messages:
                    response_text = str(messages[0])

            if not response_text:
                response_text = "No pude procesar tu consulta sobre Excelencia. ¿Podrías reformularla?"

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "response": response_text,
                "current_agent": self.name,
                "agent_history": [self.name],
                "confidence": result.get("confidence", 0.9),
                "is_complete": True,
                "retrieved_data": {
                    "agent": self.agent_name,
                    "query_type": result.get("query_type", "general"),
                    "modules_mentioned": result.get("mentioned_modules", []),
                    "requires_demo": result.get("requires_demo", False),
                },
            }

        except Exception as exc:
            logger.error(f"ExcelenciaAgent error: {exc}")
            error_response = "Lo siento, hubo un error procesando tu consulta sobre Excelencia. ¿Podrías intentar de nuevo?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "response": error_response,
                "current_agent": self.name,
                "confidence": 0.0,
                "is_complete": True,
                "error_count": state_dict.get("error_count", 0) + 1,
            }

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute Excelencia agent with the given state.

        This method is provided for IAgent interface compatibility.

        Args:
            state: Current conversation state

        Returns:
            Updated state after processing
        """
        messages = state.get("messages", [])
        if not messages:
            return {
                **state,
                "error": "No messages provided",
                "is_complete": True,
            }

        last_message = messages[-1]
        message_content = (
            last_message.content if hasattr(last_message, "content") else str(last_message)
        )

        result = await self.process(message_content, state)
        return {**state, **result}

    async def validate_input(self, state: dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if state is valid
        """
        if "messages" not in state:
            return False

        messages = state.get("messages", [])
        return bool(messages)

    async def health_check(self) -> dict[str, Any]:
        """
        Check agent health.

        Returns:
            Health status dictionary
        """
        try:
            return {
                "status": "healthy",
                "agent": self.agent_name,
                "node": "excelencia_node",
                "architecture": "simplified",
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "agent": self.agent_name,
                "error": str(exc),
            }


__all__ = ["ExcelenciaAgent"]
