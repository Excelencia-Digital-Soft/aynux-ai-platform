"""Protocol definition for intent analyzers."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IIntentAnalyzer(Protocol):
    """Protocol for intent analyzers (LLM, SpaCy, Keyword).

    All intent analyzers must implement this protocol to ensure
    consistent interface across different analysis strategies.
    """

    async def analyze(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Analyze message and return intent result.

        Args:
            message: User message to analyze
            context: Optional context (customer_data, conversation_data)

        Returns:
            Dict with keys: primary_intent, confidence, entities, target_agent, method
        """
        ...

    def get_method_name(self) -> str:
        """Return analyzer method name for metrics tracking."""
        ...
