"""Response processing utilities for graph execution."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ResponseProcessor:
    """
    Processor for graph execution responses.

    Handles extraction and transformation of responses:
    - Safe state preview creation for streaming events
    - Bot response extraction from result messages
    """

    def create_state_preview(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Create a safe preview of the current state for streaming events.

        Args:
            state: Current graph state dictionary

        Returns:
            Dictionary with safe preview fields for streaming
        """
        try:
            return {
                "current_agent": state.get("current_agent"),
                "message_count": len(state.get("messages", [])),
                "conversation_id": state.get("conversation_id"),
                "has_error": "error" in state,
                "is_complete": state.get("is_complete", False),
            }
        except Exception as e:
            logger.warning(f"Error creating state preview: {e}")
            return {"error": "Could not create state preview"}

    def extract_bot_response(self, result: dict[str, Any]) -> str | None:
        """
        Extract the last bot response from graph result.

        Args:
            result: Graph execution result dictionary

        Returns:
            Bot response content or None if not found
        """
        try:
            messages = result.get("messages", [])
            if not messages:
                return None

            # Find last AI/assistant message
            for msg in reversed(messages):
                if hasattr(msg, "content"):
                    # Check if it's an AI message (not human)
                    msg_type = getattr(msg, "type", None)
                    if msg_type in ("ai", "assistant") or not msg_type:
                        return msg.content

            # Fallback: return last message content
            last_msg = messages[-1]
            if hasattr(last_msg, "content"):
                return last_msg.content

            return None
        except Exception as e:
            logger.warning(f"Error extracting bot response: {e}")
            return None
