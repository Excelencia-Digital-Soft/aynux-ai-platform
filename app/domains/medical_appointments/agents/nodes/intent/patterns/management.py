# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Appointment management intent pattern.
# ============================================================================
"""Management Pattern.

Detects appointment management intents (view, cancel, reschedule).
"""

from typing import TYPE_CHECKING

from .base import IntentPattern, IntentResult

if TYPE_CHECKING:
    from ....state import MedicalAppointmentsState


class ManagementPattern(IntentPattern):
    """Pattern for detecting appointment management intents.

    Matches keywords for viewing, confirming, canceling, or rescheduling.
    """

    MANAGEMENT_PATTERNS = [
        "confirmar turno",
        "cancelar turno",
        "reprogramar",
        "mis turnos",
        "mi turno",
        "ver turno",
        "anular",
    ]

    RESCHEDULE_KEYWORDS = ["reprogramar", "cambiar fecha", "otra fecha"]
    CANCEL_KEYWORDS = ["cancelar", "anular"]
    CONFIRM_KEYWORDS = ["confirmar"]

    @property
    def name(self) -> str:
        return "management"

    @property
    def priority(self) -> int:
        return 80  # Check after greeting and document

    def detect(
        self,
        message: str,
        state: "MedicalAppointmentsState",
    ) -> IntentResult:
        """Detect appointment management intent."""
        if not any(kw in message for kw in self.MANAGEMENT_PATTERNS):
            return IntentResult()

        intent = self._detect_specific_intent(message)

        if intent == "reschedule":
            return IntentResult(
                detected=True,
                next_node="reschedule",
                intent="reschedule",
                state_updates={"is_rescheduling": True},
            )

        return IntentResult(
            detected=True,
            next_node="appointment_management",
            intent=intent,
        )

    def _detect_specific_intent(self, message: str) -> str:
        """Detect specific management intent type."""
        if any(kw in message for kw in self.RESCHEDULE_KEYWORDS):
            return "reschedule"
        if any(kw in message for kw in self.CANCEL_KEYWORDS):
            return "cancel"
        if any(kw in message for kw in self.CONFIRM_KEYWORDS):
            return "confirm"
        return "view"
