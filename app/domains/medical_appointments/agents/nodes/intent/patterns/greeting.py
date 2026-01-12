# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Greeting intent pattern.
# ============================================================================
"""Greeting Pattern.

Detects greeting intents from user messages.
"""

from typing import TYPE_CHECKING

from .base import IntentPattern, IntentResult

if TYPE_CHECKING:
    from ....state import MedicalAppointmentsState


class GreetingPattern(IntentPattern):
    """Pattern for detecting greeting messages.

    Matches common Spanish and English greetings.
    """

    PATTERNS = [
        "hola",
        "buenos días",
        "buenas tardes",
        "buenas noches",
        "hi",
        "hello",
        "buen día",
        "que tal",
        "qué tal",
    ]

    @property
    def name(self) -> str:
        return "greeting"

    @property
    def priority(self) -> int:
        return 100  # High priority - check first

    def detect(
        self,
        message: str,
        state: "MedicalAppointmentsState",
    ) -> IntentResult:
        """Detect greeting intent."""
        if any(g in message for g in self.PATTERNS):
            return IntentResult(
                detected=True,
                next_node="greeting",
                intent="greeting",
            )
        return IntentResult()
