"""
Node Executor

Wraps node execution with error handling and message formatting.
Single responsibility: node execution with consistent error handling.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from langchain_core.messages import AIMessage

from app.domains.pharmacy.agents.utils.message_formatter import MessageFormatter

if TYPE_CHECKING:
    from app.domains.pharmacy.agents.state import PharmacyState

logger = logging.getLogger(__name__)


class NodeExecutor:
    """
    Wraps node execution with error handling and message formatting.

    Responsibility: Execute nodes with consistent error handling and message conversion.
    """

    DEFAULT_ERROR_MESSAGE = "Disculpa, tuve un problema. ¿Podrías intentar de nuevo?"

    def __init__(
        self,
        message_formatter: MessageFormatter | None = None,
        error_message: str | None = None,
    ):
        """
        Initialize the executor.

        Args:
            message_formatter: Optional message formatter (created if not provided)
            error_message: Custom error message to use
        """
        self.formatter = message_formatter or MessageFormatter()
        self.error_message = error_message or self.DEFAULT_ERROR_MESSAGE

    def create_executor(
        self,
        node_instance: Any,
        node_name: str | None = None,
    ) -> Callable[[PharmacyState], Any]:
        """
        Create an async executor wrapper for a node.

        Args:
            node_instance: The node instance to wrap
            node_name: Optional name for logging

        Returns:
            Async function that executes the node with error handling
        """
        name = node_name or node_instance.__class__.__name__

        async def executor(state: PharmacyState) -> dict[str, Any]:
            try:
                # Extract message content
                messages = state.get("messages", [])
                if not messages:
                    logger.warning(f"Node {name}: No messages in state")
                    return self._create_error_increment(state)

                last_message = messages[-1]
                content = self._extract_message_content(last_message)

                # Execute node
                result = await node_instance.process(str(content), dict(state))

                # Format result messages
                if "messages" in result:
                    result["messages"] = self.formatter.format_result_messages(
                        result["messages"]
                    )

                return result

            except Exception as e:
                logger.error(f"Error in pharmacy node {name}: {e}", exc_info=True)
                return self._create_error_response(state)

        return executor

    def _extract_message_content(self, message: Any) -> str:
        """
        Extract content from a message object.

        Args:
            message: Message object or dict

        Returns:
            String content
        """
        if hasattr(message, "content"):
            return str(message.content)
        return str(message)

    def _create_error_increment(self, state: PharmacyState) -> dict[str, Any]:
        """
        Create a state update that increments the error count.

        Args:
            state: Current state

        Returns:
            State update with incremented error count
        """
        return {"error_count": state.get("error_count", 0) + 1}

    def _create_error_response(self, state: PharmacyState) -> dict[str, Any]:
        """
        Create a standard error response.

        Args:
            state: Current state

        Returns:
            State update with error response
        """
        return {
            "error_count": state.get("error_count", 0) + 1,
            "messages": [AIMessage(content=self.error_message)],
        }

    def wrap_async_handler(
        self,
        handler_func: Callable[..., Any],
        handler_name: str | None = None,
    ) -> Callable[[PharmacyState], Any]:
        """
        Wrap an async handler function with error handling.

        Args:
            handler_func: The handler function to wrap
            handler_name: Optional name for logging

        Returns:
            Wrapped async function
        """
        name = handler_name or handler_func.__name__

        async def wrapped(state: PharmacyState) -> dict[str, Any]:
            try:
                return await handler_func(state)
            except Exception as e:
                logger.error(f"Error in handler {name}: {e}", exc_info=True)
                return self._create_error_response(state)

        return wrapped
