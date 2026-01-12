# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Time selection node.
# ============================================================================
"""Time Selection Node.

Handles the selection of appointment times and shows booking confirmation.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class TimeSelectionNode(BaseNode):
    """Node for handling time selection.

    Displays available times and processes user selection
    to show booking confirmation.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process time selection.

        Args:
            state: Current state.

        Returns:
            State updates with selected time and confirmation prompt.
        """
        phone = state.get("user_phone")
        times = state.get("available_times", [])
        selection = self._get_selection(state)

        # If we have a selection, process it
        if selection is not None and times:
            return await self._process_selection(state, selection, times, phone)

        # Show times list
        if not times:
            return self._text_response("No hay horarios disponibles. " "Por favor, seleccioná otra fecha.")

        return await self._show_times(state, times, phone)

    async def _process_selection(
        self,
        state: "MedicalAppointmentsState",
        selection: int,
        times: list[str],
        phone: str | None,
    ) -> dict[str, Any]:
        """Process time selection and show confirmation."""
        if not 0 <= selection < len(times):
            return self._text_response(
                f"Opción inválida. Por favor, seleccioná un número del 1 al {len(times)}.",
                available_times=times,
            )

        selected_time = times[selection]

        # Build confirmation message
        patient_name = state.get("patient_name", "N/A")
        specialty_name = state.get("selected_specialty_name", "N/A")
        provider_name = state.get("selected_provider_name", "N/A")
        selected_date = state.get("selected_date", "N/A")

        confirmation_text = (
            "📋 *Resumen del turno:*\n\n"
            f"👤 Paciente: {patient_name}\n"
            f"🏥 Especialidad: {specialty_name}\n"
            f"👨‍⚕️ Profesional: {provider_name}\n"
            f"📅 Fecha: {selected_date}\n"
            f"🕐 Hora: {selected_time}\n\n"
            "¿Confirmás el turno?"
        )

        # Send interactive buttons if available
        if phone and self._notification:
            await self._send_interactive_buttons(
                phone=phone,
                body=confirmation_text,
                buttons=[
                    {"id": "confirm_booking", "title": "Confirmar"},
                    {"id": "cancel_booking", "title": "Cancelar"},
                    {"id": "change_time", "title": "Cambiar"},
                ],
            )

        return self._text_response(
            confirmation_text + " (Sí/No)",
            selected_time=selected_time,
            awaiting_confirmation=True,
        )

    async def _show_times(
        self,
        state: "MedicalAppointmentsState",
        times: list[str],
        phone: str | None,
    ) -> dict[str, Any]:
        """Show times list."""
        selected_date = state.get("selected_date", "la fecha")

        # Send interactive list if available
        if phone and self._notification:
            time_items = [{"id": t, "nombre": t} for t in times[:10]]
            await self._send_interactive_list(
                phone=phone,
                title=f"Horarios disponibles para {selected_date}:",
                items=time_items,
                button_text="Ver horarios",
            )

        response = f"Horarios disponibles para {selected_date}:\n\n"
        for i, time in enumerate(times[:10], 1):
            response += f"{i}. {time}\n"
        response += "\nIngresá el número del horario:"

        return self._text_response(response, available_times=times)
