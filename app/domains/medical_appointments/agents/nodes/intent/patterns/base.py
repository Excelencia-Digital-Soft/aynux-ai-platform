# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Base intent pattern class.
# ============================================================================
"""Base Intent Pattern.

Abstract base for intent detection patterns (Strategy pattern).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....state import MedicalAppointmentsState


@dataclass
class IntentResult:
    """Result of intent detection.

    Attributes:
        detected: Whether the pattern matched.
        next_node: Target node for routing.
        intent: Detected intent name.
        state_updates: Additional state changes.
    """

    detected: bool = False
    next_node: str = ""
    intent: str = ""
    state_updates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to state update dictionary."""
        if not self.detected:
            return {}
        return {
            "next_node": self.next_node,
            "detected_intent": self.intent,
            **self.state_updates,
        }


class IntentPattern(ABC):
    """Abstract base for intent detection patterns.

    Implements Strategy pattern for extensible intent detection.
    Each pattern handles a specific type of user intent.

    Usage:
        class MyPattern(IntentPattern):
            def detect(self, message, state):
                if "keyword" in message:
                    return IntentResult(True, "my_node", "my_intent")
                return IntentResult()
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Pattern name for logging/debugging."""
        ...

    @property
    def priority(self) -> int:
        """Pattern priority (higher = checked first). Default: 50."""
        return 50

    @abstractmethod
    def detect(
        self,
        message: str,
        state: "MedicalAppointmentsState",
    ) -> IntentResult:
        """Detect intent from message and state.

        Args:
            message: User message (lowercase, stripped).
            state: Current conversation state.

        Returns:
            IntentResult with detection result.
        """
        ...
