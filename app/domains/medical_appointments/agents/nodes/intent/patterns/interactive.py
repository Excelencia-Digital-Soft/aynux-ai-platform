# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Interactive response intent pattern.
# ============================================================================
"""Interactive Pattern.

Detects WhatsApp interactive button/list responses.
"""

from typing import TYPE_CHECKING

from .base import IntentPattern, IntentResult

if TYPE_CHECKING:
    from ....state import MedicalAppointmentsState


class InteractivePattern(IntentPattern):
    """Pattern for detecting WhatsApp interactive responses.

    Handles button IDs and list selections from WhatsApp UI.
    """

    # Button/list ID mappings to nodes
    BUTTON_MAPPINGS: dict[tuple[str, ...], tuple[str, str, dict]] = {
        # (button_ids): (next_node, intent, extra_state_updates)
        ("nuevo_turno", "new_appointment"): ("patient_identification", "new_booking", {}),
        ("mis_turnos", "view_appointments"): ("appointment_management", "view_appointments", {}),
        ("cancelar_turno", "cancel_appointment"): ("appointment_management", "cancel", {}),
        ("accept_suggested", "confirm_booking"): ("booking_confirmation", "confirm", {}),
        ("other_appointment", "change_time"): ("specialty_selection", "new_booking", {"suggested_appointment": None}),
        ("different_person",): (
            "greeting",
            "new_session",
            {"patient_data": None, "patient_id": None, "is_registered": False},
        ),
        ("confirm_reschedule",): ("reschedule", "confirm_reschedule", {}),
        ("cancel_reschedule", "cancel_booking"): ("fallback", "cancel", {}),
    }

    @property
    def name(self) -> str:
        return "interactive"

    @property
    def priority(self) -> int:
        return 85  # Check after greeting, before general management

    def detect(
        self,
        message: str,
        state: "MedicalAppointmentsState",
    ) -> IntentResult:
        """Detect interactive button/list response."""
        for button_ids, (next_node, intent, updates) in self.BUTTON_MAPPINGS.items():
            if message in button_ids:
                return IntentResult(
                    detected=True,
                    next_node=next_node,
                    intent=intent,
                    state_updates=updates,
                )
        return IntentResult()
