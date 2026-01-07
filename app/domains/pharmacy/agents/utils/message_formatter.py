"""
Message Formatter

Formats messages between different representations (dict, LangChain objects).
Single responsibility: message format conversion.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage


class MessageFormatter:
    """
    Converts messages between different formats.

    Responsibility: Transform messages between dict and LangChain message types.
    """

    @staticmethod
    def format_result_messages(messages: list[dict | Any]) -> list[AIMessage | HumanMessage]:
        """
        Convert dict-based messages to LangChain message objects.

        Args:
            messages: List of messages (dicts or message objects)

        Returns:
            List of LangChain message objects (AIMessage or HumanMessage)
        """
        formatted: list[AIMessage | HumanMessage] = []

        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if msg.get("role") == "assistant":
                    formatted.append(AIMessage(content=content))
                else:
                    formatted.append(HumanMessage(content=content))
            else:
                # Already a message object
                formatted.append(msg)

        return formatted

    @staticmethod
    def create_assistant_message(content: str) -> AIMessage:
        """
        Create an assistant message.

        Args:
            content: Message content

        Returns:
            AIMessage instance
        """
        return AIMessage(content=content)

    @staticmethod
    def create_human_message(content: str) -> HumanMessage:
        """
        Create a human/user message.

        Args:
            content: Message content

        Returns:
            HumanMessage instance
        """
        return HumanMessage(content=content)

    @staticmethod
    def to_dict(message: AIMessage | HumanMessage) -> dict[str, str]:
        """
        Convert a LangChain message to dict format.

        Args:
            message: LangChain message object

        Returns:
            Dict with 'role' and 'content' keys
        """
        role = "assistant" if isinstance(message, AIMessage) else "user"
        content = message.content if hasattr(message, "content") else str(message)
        return {"role": role, "content": str(content)}

    @staticmethod
    def format_error_response(error: Exception | str) -> dict[str, Any]:
        """
        Format an error into a standard response dict.

        Args:
            error: Exception or error message

        Returns:
            Dict with error response structure
        """
        error_message = str(error) if isinstance(error, Exception) else error
        return {
            "messages": [AIMessage(content="Disculpa, tuve un problema. ¿Podrías intentar de nuevo?")],
            "error": error_message,
        }
