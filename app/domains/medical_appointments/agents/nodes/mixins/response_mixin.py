# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Response generation mixin for LangGraph nodes.
# ============================================================================
"""Response Mixin.

Provides response generation helpers for LangGraph nodes.
Single Responsibility: Generate formatted responses.
"""

from typing import Any

from langchain_core.messages import AIMessage


class ResponseMixin:
    """Mixin providing response generation helpers.

    Usage:
        class MyNode(BaseNode, ResponseMixin):
            async def process(self, state):
                return self._text_response("Hello!")
    """

    def _text_response(
        self,
        text: str,
        **state_updates: Any,
    ) -> dict[str, Any]:
        """Create a text response.

        Args:
            text: Response text.
            **state_updates: Additional state updates.

        Returns:
            State update dictionary with message and response_text.
        """
        return {
            "messages": [AIMessage(content=text)],
            "response_text": text,
            **state_updates,
        }

    def _error_response(self, error_message: str) -> dict[str, Any]:
        """Create an error response.

        Args:
            error_message: Error description (logged, not shown to user).

        Returns:
            State update dictionary with generic error message.
        """
        return {
            "messages": [
                AIMessage(
                    content="Lo siento, ocurrió un error. " "Por favor, intentá nuevamente o contactá a la institución."
                )
            ],
            "last_error": error_message,
            "error_count": 1,
        }

    def _list_response(
        self,
        title: str,
        items: list[dict[str, Any]],
        item_key: str = "nombre",
        prompt: str = "Seleccioná una opción:",
        **state_updates: Any,
    ) -> dict[str, Any]:
        """Create a numbered list response.

        Args:
            title: List title.
            items: List of items to display (max 10).
            item_key: Key to extract item name from dict.
            prompt: Prompt text after the list.
            **state_updates: Additional state updates.

        Returns:
            State update dictionary with formatted list.
        """
        text = f"{title}\n\n"
        for i, item in enumerate(items[:10], 1):
            name = item.get(item_key) or item.get("descripcion") or f"Opción {i}"
            text += f"{i}. {name}\n"
        text += f"\n{prompt}"

        return self._text_response(text, **state_updates)
