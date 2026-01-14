"""
Conversation Context Builder

Builds formatted conversation context for LLM prompts.
Single responsibility: conversation history formatting.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage


class ConversationContextBuilder:
    """
    Builds formatted conversation context for use in prompts.

    Responsibility: Format conversation history for context injection.
    """

    DEFAULT_MAX_TURNS = 5
    DEFAULT_MAX_RESPONSE_LENGTH = 150

    def format_recent_history(
        self,
        state: dict[str, Any],
        max_turns: int = DEFAULT_MAX_TURNS,
        max_response_length: int = DEFAULT_MAX_RESPONSE_LENGTH,
    ) -> str:
        """
        Format recent conversation turns for context.

        Args:
            state: Current state with messages
            max_turns: Maximum conversation turns to include (default: 5)
            max_response_length: Maximum length for assistant responses (default: 150)

        Returns:
            Formatted string with recent conversation history
        """
        messages = state.get("messages", [])
        if len(messages) <= 1:  # Only current message
            return ""

        # Exclude current message, take last N*2 (user+assistant pairs)
        history_messages = messages[:-1][-(max_turns * 2) :]
        if not history_messages:
            return ""

        formatted_lines = []
        for msg in history_messages:
            if isinstance(msg, HumanMessage):
                content = msg.content if hasattr(msg, "content") else str(msg)
                formatted_lines.append(f"Usuario: {content}")
            elif isinstance(msg, AIMessage):
                # Truncate long responses
                content = str(msg.content)
                if len(content) > max_response_length:
                    content = content[:max_response_length] + "..."
                formatted_lines.append(f"Asistente: {content}")

        return "\n".join(formatted_lines) if formatted_lines else ""

    def format_messages_list(
        self,
        messages: list[Any],
        max_length: int = DEFAULT_MAX_RESPONSE_LENGTH,
    ) -> list[dict[str, str]]:
        """
        Format a list of messages into a standardized format.

        Args:
            messages: List of message objects
            max_length: Maximum length for content truncation

        Returns:
            List of dicts with 'role' and 'content' keys
        """
        formatted = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                content = str(msg.content)
                role = "user"
            elif isinstance(msg, AIMessage):
                content = str(msg.content)
                role = "assistant"
            elif isinstance(msg, dict):
                content = str(msg.get("content", ""))
                role = msg.get("role", "user")
            else:
                content = str(msg)
                role = "user"

            if len(content) > max_length:
                content = content[:max_length] + "..."

            formatted.append({"role": role, "content": content})

        return formatted

    def build_context_dict(
        self,
        state: dict[str, Any],
        include_history: bool = True,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> dict[str, Any]:
        """
        Build a context dictionary from state.

        Args:
            state: Current state
            include_history: Whether to include conversation history
            max_turns: Maximum turns for history

        Returns:
            Context dict with customer info and optional history
        """
        context = {
            "customer_identified": state.get("customer_identified", False),
            "customer_name": state.get("customer_name", "Cliente"),
            "has_debt": state.get("has_debt", False),
            "debt_status": state.get("debt_status"),
            "awaiting_confirmation": state.get("awaiting_confirmation", False),
        }

        if include_history:
            context["conversation_history"] = self.format_recent_history(state, max_turns=max_turns)

        return context
