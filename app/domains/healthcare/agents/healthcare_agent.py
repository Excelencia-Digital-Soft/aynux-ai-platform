"""
Healthcare Agent

IAgent wrapper for the Healthcare domain graph.
Implements the standard agent interface for integration with SuperOrchestrator.
Uses RAG (Knowledge Base Search) for context-aware responses.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config.settings import get_settings
from app.core.interfaces.agent import AgentType, IAgent
from app.domains.excelencia.application.services.support_response import (
    KnowledgeBaseSearch,
    RagQueryLogger,
    SearchMetrics,
)

from .graph import HealthcareGraph

logger = logging.getLogger(__name__)
settings = get_settings()


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

        # RAG integration for knowledge-based responses
        self._knowledge_search = KnowledgeBaseSearch(
            agent_key="healthcare_agent",
            max_results=3,
        )
        self._rag_logger = RagQueryLogger(agent_key="healthcare_agent")
        self._last_search_metrics: SearchMetrics | None = None
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)

        logger.info("HealthcareAgent initialized (RAG enabled: %s)", self.use_rag)

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

            # Extract message from state for the graph
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                message = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            else:
                message = ""

            # Get RAG context for knowledge-based response
            rag_context = await self._get_rag_context(message)

            # Invoke the healthcare graph with the message string
            # Pass RAG context in state for graph nodes to use
            if rag_context:
                state["rag_context"] = rag_context

            result = await self._graph.invoke(message)

            # Log RAG query with response (fire-and-forget)
            if self._last_search_metrics and self._last_search_metrics.result_count > 0:
                # Extract response from graph result
                response_text = result.get("agent_response", "")
                if not response_text and "messages" in result:
                    messages = result.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        response_text = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)

                if response_text:
                    self._rag_logger.log_async(
                        query=message,
                        metrics=self._last_search_metrics,
                        response=response_text,
                    )

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

    async def _get_rag_context(self, message: str) -> str:
        """
        Get RAG context from knowledge base.

        Args:
            message: User message

        Returns:
            Formatted context string or empty string
        """
        self._last_search_metrics = None

        if not self.use_rag:
            return ""

        try:
            search_result = await self._knowledge_search.search(message, "healthcare")
            self._last_search_metrics = search_result.metrics
            if search_result.context:
                logger.info(f"RAG context found for healthcare query: {len(search_result.context)} chars")
            return search_result.context
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return ""

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
