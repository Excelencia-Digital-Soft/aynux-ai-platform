# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Intent detector using strategy pattern.
# ============================================================================
"""Intent Detector.

Orchestrates intent detection using strategy pattern.
Extensible without modifying detector code (OCP).

Usage:
    detector = IntentDetector()
    detector.add_pattern(GreetingPattern())
    detector.add_pattern(MyCustomPattern())

    result = detector.detect(message, state)
    if result.detected:
        return result.to_dict()
"""

import logging
from typing import TYPE_CHECKING

from .patterns import IntentPattern, IntentResult

if TYPE_CHECKING:
    from ...state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class IntentDetector:
    """Orchestrates intent detection using registered patterns.

    Implements Open/Closed Principle - new patterns can be added
    without modifying this class.
    """

    def __init__(self) -> None:
        """Initialize detector with empty pattern list."""
        self._patterns: list[IntentPattern] = []

    def add_pattern(self, pattern: IntentPattern) -> "IntentDetector":
        """Add a pattern to the detector.

        Args:
            pattern: IntentPattern to add.

        Returns:
            Self for method chaining.
        """
        self._patterns.append(pattern)
        # Sort by priority (descending) when adding
        self._patterns.sort(key=lambda p: p.priority, reverse=True)
        return self

    def detect(
        self,
        message: str,
        state: "MedicalAppointmentsState",
    ) -> IntentResult:
        """Detect intent from message using registered patterns.

        Args:
            message: User message (will be normalized).
            state: Current conversation state.

        Returns:
            IntentResult from first matching pattern, or empty result.
        """
        normalized = message.lower().strip()

        for pattern in self._patterns:
            result = pattern.detect(normalized, state)
            if result.detected:
                logger.debug(f"Intent detected: {result.intent} by {pattern.name}")
                return result

        return IntentResult()

    def list_patterns(self) -> list[str]:
        """List registered pattern names in priority order."""
        return [p.name for p in self._patterns]


def create_default_detector() -> IntentDetector:
    """Create detector with default patterns.

    Returns:
        IntentDetector with all standard patterns registered.
    """
    from .patterns import (
        DocumentPattern,
        GreetingPattern,
        InteractivePattern,
        ManagementPattern,
    )

    return (
        IntentDetector()
        .add_pattern(GreetingPattern())
        .add_pattern(DocumentPattern())
        .add_pattern(InteractivePattern())
        .add_pattern(ManagementPattern())
    )
