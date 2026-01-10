"""
Message Extractor

Extracts content from messages in different formats.
Single responsibility: message content extraction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_core.messages import HumanMessage


class MessageExtractor:
    """
    Extracts content from messages.

    Responsibility: Extract text content from various message formats.
    """

    @staticmethod
    def extract_last_human_message(state: Mapping[str, Any]) -> str | None:
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
