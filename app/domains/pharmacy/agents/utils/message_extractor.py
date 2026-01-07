"""
Message Extractor

Extracts content from messages in different formats.
Single responsibility: message content extraction.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage


class MessageExtractor:
    """
    Extracts content from messages.

    Responsibility: Extract text content from various message formats.
    """

    @staticmethod
    def extract_last_human_message(state: dict[str, Any]) -> str | None:
        """
        Extract content from last HumanMessage in state.

        Args:
            state: State dict containing messages list

        Returns:
            Content of the last human message or None if not found
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                content = msg.content if hasattr(msg, "content") else str(msg)
                return str(content).strip()

        return None

    @staticmethod
    def extract_last_message_content(state: dict[str, Any]) -> str | None:
        """
        Extract content from the last message regardless of type.

        Args:
            state: State dict containing messages list

        Returns:
            Content of the last message or None if not found
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        last_message = messages[-1]

        if hasattr(last_message, "content"):
            return str(last_message.content).strip()

        if isinstance(last_message, dict):
            return str(last_message.get("content", "")).strip()

        return str(last_message).strip()

    @staticmethod
    def extract_message_content(message: Any) -> str:
        """
        Extract content from a single message.

        Args:
            message: Message object or dict

        Returns:
            String content of the message
        """
        if hasattr(message, "content"):
            return str(message.content)

        if isinstance(message, dict):
            return str(message.get("content", ""))

        return str(message)

    @staticmethod
    def has_messages(state: dict[str, Any]) -> bool:
        """
        Check if state has any messages.

        Args:
            state: State dict

        Returns:
            True if messages exist and list is not empty
        """
        messages = state.get("messages", [])
        return bool(messages)
