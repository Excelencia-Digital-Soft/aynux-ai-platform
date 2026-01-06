# ============================================================================
# SCOPE: GLOBAL
# Description: Agente de historial de conversación. NO es un nodo del grafo,
#              sino un servicio que se usa en el middleware de graph.py
# Tenant-Aware: Yes via BaseAgent
# ============================================================================
"""
History Agent - Conversation History Management

This agent manages conversation context by:
1. Loading existing context at conversation start
2. Generating LLM-based rolling summaries
3. Updating context after each conversation turn

NOTE: This is NOT a graph node. It's used by the middleware pattern in graph.py
"""

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.integrations.llm import VllmLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.models.conversation_context import ConversationContextModel
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry
from app.services.conversation_context_service import ConversationContextService

logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_SUMMARY_MAX_TOKENS = 300
DEFAULT_SUMMARY_TEMPERATURE = 0.3
DEFAULT_SUMMARY_INTERVAL = 5  # Regenerate summary every N turns


class HistoryAgent(BaseAgent):
    """
    Agent responsible for conversation history management.

    This agent does NOT produce user-facing responses - it only
    manages conversation context for other agents.

    Responsibilities:
    - Load conversation context from Redis/PostgreSQL
    - Generate LLM-based rolling summaries
    - Update context after each exchange
    - Extract key entities and topics

    Usage:
        history_agent = HistoryAgent(llm=llm, postgres=postgres)

        # Load context at start
        context = await history_agent.load_context(conversation_id)

        # Update context after exchange
        await history_agent.update_context(
            conversation_id=conv_id,
            user_message=user_msg,
            bot_response=response,
            current_context=context,
        )
    """

    def __init__(
        self,
        llm: VllmLLM | None = None,
        postgres=None,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(
            "history_agent", config or {}, llm=llm, postgres=postgres
        )
        self.llm = llm or VllmLLM()

        # Configuration
        config = config or {}
        self.summary_interval = config.get(
            "summary_interval", DEFAULT_SUMMARY_INTERVAL
        )
        self.max_summary_tokens = config.get(
            "max_summary_tokens", DEFAULT_SUMMARY_MAX_TOKENS
        )

        # Initialize services
        self.prompt_manager = PromptManager()
        self._context_service: ConversationContextService | None = None

        logger.info(
            f"HistoryAgent initialized with summary_interval={self.summary_interval}"
        )

    @property
    def context_service(self) -> ConversationContextService:
        """Lazy initialization of context service."""
        if self._context_service is None:
            self._context_service = ConversationContextService()
        return self._context_service

    def set_db_session(self, db_session) -> None:
        """Set database session for the context service."""
        self._context_service = ConversationContextService(db=db_session)

    # =========================================================================
    # Main API Methods
    # =========================================================================

    @trace_async_method(
        name="history_agent_load",
        run_type="chain",
        metadata={"agent_type": "history", "operation": "load"},
    )
    async def load_context(
        self, conversation_id: str, **initial_data: Any
    ) -> ConversationContextModel:
        """
        Load conversation context from storage.

        Args:
            conversation_id: Unique conversation identifier
            **initial_data: Initial data for new contexts (organization_id, user_phone)

        Returns:
            ConversationContextModel with loaded or new context
        """
        context = await self.context_service.get_or_create_context(
            conversation_id, **initial_data
        )
        logger.debug(
            f"Loaded context for {conversation_id}: turns={context.total_turns}"
        )
        return context

    @trace_async_method(
        name="history_agent_update",
        run_type="chain",
        metadata={"agent_type": "history", "operation": "update"},
    )
    async def update_context(
        self,
        conversation_id: str,
        user_message: str,
        bot_response: str,
        current_context: ConversationContextModel | None = None,
        agent_name: str | None = None,
    ) -> ConversationContextModel:
        """
        Update conversation context with new exchange.

        Args:
            conversation_id: Unique conversation identifier
            user_message: The user's message
            bot_response: The assistant's response
            current_context: Optional existing context (avoids extra lookup)
            agent_name: Name of the agent that generated the response

        Returns:
            Updated ConversationContextModel
        """
        # Get current context if not provided
        if current_context is None:
            current_context = await self.context_service.get_or_create_context(
                conversation_id
            )

        # Update basic fields
        current_context.update_from_exchange(user_message, bot_response)

        # Save the agent that processed this message for flow continuity
        if agent_name:
            current_context.last_agent = agent_name

        # Check if we should regenerate summary
        should_summarize = (
            current_context.total_turns % self.summary_interval == 0
            and current_context.total_turns > 0
        )

        if should_summarize:
            logger.info(
                f"Regenerating summary for {conversation_id} at turn {current_context.total_turns}"
            )
            try:
                new_summary = await self._generate_summary(
                    previous_summary=current_context.rolling_summary,
                    user_message=user_message,
                    bot_response=bot_response,
                )
                current_context.rolling_summary = new_summary
                logger.debug(f"Summary updated: {new_summary[:100]}...")
            except Exception as e:
                logger.error(f"Error generating summary: {e}")
                # Continue without summary update (graceful degradation)

        # Save context first to ensure parent record exists (FK requirement)
        await self.context_service.save_context(conversation_id, current_context)

        # Save messages to database (after context exists)
        try:
            await self.context_service.save_message(
                conversation_id=conversation_id,
                sender_type="user",
                content=user_message,
            )
            await self.context_service.save_message(
                conversation_id=conversation_id,
                sender_type="assistant",
                content=bot_response,
                agent_name=agent_name,
            )
        except Exception as e:
            logger.warning(f"Error saving messages: {e}")

        return current_context

    @trace_async_method(
        name="history_agent_summarize",
        run_type="llm",
        metadata={"agent_type": "history", "operation": "summarize"},
    )
    async def summarize(
        self,
        previous_summary: str,
        user_message: str,
        bot_response: str,
    ) -> str:
        """
        Generate an updated rolling summary using LLM.

        Public method that can be called directly for force-summarization.

        Args:
            previous_summary: The existing summary (or empty string)
            user_message: The user's latest message
            bot_response: The assistant's latest response

        Returns:
            Updated summary string
        """
        return await self._generate_summary(
            previous_summary=previous_summary,
            user_message=user_message,
            bot_response=bot_response,
        )

    # =========================================================================
    # BaseAgent Interface (required but not used as graph node)
    # =========================================================================

    async def _process_internal(
        self, message: str, state_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """
        BaseAgent interface - not used as this agent is not a graph node.

        This method exists only to satisfy the BaseAgent interface.
        Use load_context() and update_context() instead.
        """
        logger.warning(
            "HistoryAgent._process_internal called - this agent should not be used as a graph node"
        )
        return {
            "messages": [],
            "conversation_context": state_dict.get("conversation_context", {}),
            "conversation_summary": state_dict.get("conversation_summary", ""),
        }

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _generate_summary(
        self,
        previous_summary: str,
        user_message: str,
        bot_response: str,
    ) -> str:
        """Generate rolling summary using LLM."""
        try:
            # Try to load prompt from YAML
            prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_HISTORY_SUMMARIZE,
                variables={
                    "previous_summary": previous_summary or "No hay contexto previo.",
                    "user_message": user_message,
                    "bot_response": bot_response,
                },
            )
        except Exception:
            # Fallback to hardcoded prompt if YAML not available
            prompt = self._get_fallback_prompt(
                previous_summary, user_message, bot_response
            )

        # Use summary model (fast non-reasoning model) for summarization
        # NOTE: Using SUMMARY instead of SIMPLE because deepseek-r1 generates
        # internal "thinking tokens" that cause 3-10 minute delays.
        llm = self.llm.get_llm(
            complexity=ModelComplexity.SUMMARY,
            temperature=DEFAULT_SUMMARY_TEMPERATURE,
        )

        result = await llm.ainvoke(prompt)
        summary = result.content.strip()

        # Truncate if too long
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return summary

    def _get_fallback_prompt(
        self,
        previous_summary: str,
        user_message: str,
        bot_response: str,
    ) -> str:
        """Fallback prompt when YAML is not available."""
        return f"""Eres un asistente que resume conversaciones de forma concisa.

## Resumen anterior:
{previous_summary or "No hay contexto previo."}

## Nuevo intercambio:
Usuario: {user_message}
Asistente: {bot_response}

Genera un resumen actualizado (máximo 200 palabras) que:
1. Capture los temas principales discutidos
2. Retenga información clave del usuario (nombre, preferencias, problemas)
3. Note acciones pendientes o compromisos
4. Mantenga el tono y estado emocional de la conversación

Resumen actualizado:"""
