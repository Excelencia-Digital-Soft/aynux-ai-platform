# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: State extraction mixin for LangGraph nodes.
# ============================================================================
"""State Mixin.

Provides state extraction helpers for LangGraph nodes.
Single Responsibility: Extract values from state dictionary.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...state import MedicalAppointmentsState


class StateMixin:
    """Mixin providing state extraction helpers.

    Usage:
        class MyNode(BaseNode, StateMixin):
            async def process(self, state):
                message = self._get_message(state)
                patient_id = self._get_patient_id(state)
    """

    def _get_message(self, state: "MedicalAppointmentsState") -> str:
        """Extract the last user message from state.

        Args:
            state: Current state.

        Returns:
            Last message content as string, or empty string if none.
        """
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            if hasattr(last, "content"):
                return str(last.content)
            return str(last)
        return ""

    def _get_selection(self, state: "MedicalAppointmentsState") -> int | None:
        """Extract numeric selection from last message.

        Args:
            state: Current state.

        Returns:
            Selection index (0-based) or None if not a number.
        """
        message = self._get_message(state).strip()
        if message.isdigit():
            return int(message) - 1  # Convert to 0-based index
        return None

    def _get_patient_id(self, state: "MedicalAppointmentsState") -> str:
        """Get patient ID from state."""
        return str(state.get("patient_id") or "")

    def _get_provider_id(self, state: "MedicalAppointmentsState") -> str:
        """Get provider ID from state."""
        return str(state.get("selected_provider_id") or "")

    def _get_specialty_id(self, state: "MedicalAppointmentsState") -> str:
        """Get specialty ID from state."""
        return str(state.get("selected_specialty") or "")
