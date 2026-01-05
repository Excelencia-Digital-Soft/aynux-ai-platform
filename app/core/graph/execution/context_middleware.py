"""Conversation context middleware for graph execution."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.core.graph.execution.response_processor import ResponseProcessor
    from app.domains.shared.agents.history_agent import HistoryAgent
    from app.models.conversation_context import ConversationContextModel

logger = logging.getLogger(__name__)


class ConversationContextMiddleware:
    """
    Middleware for conversation context management.

    Handles the complete lifecycle of conversation context:
    - Database session injection for persistence
    - Context loading from storage
    - Initial state building for graph execution
    - Context updates after execution
    """

    def __init__(self, history_agent: "HistoryAgent") -> None:
        """
        Initialize middleware with history agent dependency.

        Args:
            history_agent: Agent responsible for context persistence
        """
        self._history_agent = history_agent

    def prepare_db_session(self, db_session: AsyncSession | None) -> None:
        """
        Inject database session into history agent for message persistence.

        Args:
            db_session: SQLAlchemy async session or None
        """
        if db_session:
            self._history_agent.set_db_session(db_session)

    async def load_context(
        self, conv_id: str, **kwargs: Any
    ) -> "ConversationContextModel | None":
        """
        Load conversation context from storage with error handling.

        Args:
            conv_id: Conversation identifier
            **kwargs: Additional parameters (organization_id, pharmacy_id, user_phone)

        Returns:
            Loaded conversation context or None if not found/error
        """
        try:
            context = await self._history_agent.load_context(
                conversation_id=conv_id,
                organization_id=kwargs.get("organization_id"),
                pharmacy_id=kwargs.get("pharmacy_id"),
                user_phone=kwargs.get("user_phone"),
            )
            logger.debug(
                f"Loaded context for {conv_id}: turns={context.total_turns if context else 0}"
            )
            return context
        except Exception as e:
            logger.warning(f"Error loading conversation context: {e}")
            return None

    def build_initial_state(
        self,
        message: str,
        conv_id: str,
        user_id: str | None,
        context: "ConversationContextModel | None",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Build initial state dictionary for graph execution.

        Args:
            message: User message content
            conv_id: Conversation identifier
            user_id: User identifier or None
            context: Loaded conversation context or None
            **kwargs: Additional state parameters

        Returns:
            Initial state dictionary for graph execution
        """
        return {
            "messages": [HumanMessage(content=message)],
            "conversation_id": conv_id,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            # Identification fields for flow continuity (pending tickets, etc.)
            "user_phone": kwargs.get("user_phone"),
            "sender": kwargs.get("user_phone"),  # Alias for WhatsApp compatibility
            # MIDDLEWARE: Inject conversation context
            "conversation_context": context.model_dump() if context else {},
            "conversation_summary": context.to_prompt_context() if context else "",
            "history_loaded": context is not None,
            # FLOW CONTINUITY: Inject last_agent as current_agent for follow-up detection
            "current_agent": context.last_agent if context else None,
            # CHECKPOINTER: Reset control flags for new message (prevents early exit)
            "is_complete": False,
            "human_handoff_requested": False,
            "next_agent": None,
            **kwargs,
        }

    def extract_specialized_agent(self, agent_history: list[str]) -> str | None:
        """
        Extract the last specialized agent from history (not orchestrator/supervisor).

        Args:
            agent_history: List of agent names in execution order

        Returns:
            Last specialized agent name or None if not found
        """
        for agent in reversed(agent_history):
            if agent not in ("orchestrator", "supervisor"):
                return agent
        return None

    async def update_context(
        self,
        result: dict[str, Any],
        message: str,
        context: "ConversationContextModel | None",
        conv_id: str,
        response_processor: "ResponseProcessor",
    ) -> None:
        """
        Update conversation context after graph execution.

        Args:
            result: Graph execution result
            message: Original user message
            context: Previous conversation context
            conv_id: Conversation identifier
            response_processor: Processor to extract bot response
        """
        bot_response = response_processor.extract_bot_response(result)
        if not bot_response:
            return

        try:
            specialized_agent = self.extract_specialized_agent(
                result.get("agent_history", [])
            )
            await self._history_agent.update_context(
                conversation_id=conv_id,
                user_message=message,
                bot_response=bot_response,
                current_context=context,
                agent_name=specialized_agent or result.get("current_agent"),
            )
        except Exception as e:
            logger.warning(f"Error updating conversation context: {e}")

    def build_checkpointer_config(self, conv_id: str) -> dict[str, Any]:
        """
        Build configuration for checkpointing.

        Args:
            conv_id: Conversation identifier

        Returns:
            Configuration dictionary for checkpointer
        """
        config: dict[str, Any] = {}
        if conv_id:
            config["configurable"] = {"thread_id": conv_id}
        return config
