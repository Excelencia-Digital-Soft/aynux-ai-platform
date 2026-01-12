# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Appointment management node.
# ============================================================================
"""Appointment Management Node.

Handles viewing, confirming, and cancelling existing appointments.
Refactored with helpers to reduce code duplication (SRP).
"""

import logging
import re
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class AppointmentManagementNode(BaseNode):
    """Node for managing existing appointments."""

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process appointment management request."""
        phone = state.get("user_phone")
        intent = state.get("detected_intent", "view")
        patient_id = self._get_patient_id(state)

        if not patient_id:
            return self._text_response("Para gestionar tus turnos, primero ingresá tu DNI.")

        if intent == "confirm":
            return await self._handle_action(state, "confirmar", self._medical.confirmar_turno)
        if intent == "cancel":
            return await self._handle_action(state, "cancelar", self._medical.cancelar_turno)

        return await self._show_appointments(patient_id, phone)

    async def _show_appointments(self, patient_id: str, phone: str | None) -> dict[str, Any]:
        """Show patient's appointments."""
        result = await self._medical.obtener_turnos_paciente(patient_id)
        appointments = result.get_list() if result.success else []

        if not appointments:
            return self._text_response("No tenés turnos pendientes.\n¿Querés agendar uno nuevo?")

        # Build text response
        response = "📋 *Tus turnos:*\n\n"
        for i, apt in enumerate(appointments[:10], 1):
            response += self._format_appointment(i, apt)

        response += (
            "Para gestionar un turno, escribí:\n"
            "• 'Confirmar [número]'\n"
            "• 'Cancelar [número]'\n"
            "• 'Reprogramar [número]'"
        )

        # Send interactive list
        if phone and self._notification:
            items = [self._format_apt_item(i, apt) for i, apt in enumerate(appointments[:10])]
            await self._send_interactive_list(phone, "Tus turnos:", items, "Ver turnos")

        return self._text_response(response, patient_appointments=appointments)

    async def _handle_action(self, state: "MedicalAppointmentsState", action: str, api_method: Any) -> dict[str, Any]:
        """Handle confirm/cancel action."""
        appointment_id = self._get_appointment_id(state)

        if not appointment_id:
            return self._text_response(
                f"Indicá qué turno querés {action}.\n"
                f"Escribí '{action.capitalize()} [número]' o seleccioná de la lista."
            )

        result = await api_method(appointment_id)

        if result.success:
            msg = "✅ Turno confirmado." if action == "confirmar" else "❌ Turno cancelado."
            return self._text_response(f"{msg}\n\n¿Querés hacer otra cosa?", appointment_id=None)

        return self._text_response(
            f"❌ No se pudo {action}: {result.error_message}\n" "Intentá nuevamente o contactá a la institución."
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_appointment_id(self, state: "MedicalAppointmentsState") -> str | None:
        """Extract appointment ID from state or message."""
        if apt_id := state.get("appointment_id"):
            return apt_id

        message = self._get_message(state)
        match = re.search(r"\d+", message)
        if not match:
            return None

        selection = int(match.group())
        appointments = state.get("patient_appointments", [])

        # Check if it's a list index (1-based)
        if 1 <= selection <= len(appointments):
            apt = appointments[selection - 1]
            return str(apt.get("idTurno") or apt.get("id") or "")

        return match.group()  # Assume it's the appointment ID

    def _format_appointment(self, i: int, apt: dict) -> str:
        """Format appointment for text display."""
        return (
            f"{i}. {apt.get('fecha', 'N/A')} {apt.get('hora', '')}\n"
            f"   {apt.get('especialidad', '')} - {apt.get('prestador', '')}\n"
            f"   Estado: {apt.get('estado', 'Pendiente')}\n\n"
        )

    def _format_apt_item(self, i: int, apt: dict) -> dict[str, str]:
        """Format appointment for interactive list."""
        return {
            "id": str(apt.get("idTurno") or apt.get("id") or i),
            "nombre": f"{apt.get('fecha', 'N/A')} {apt.get('hora', '')}",
            "descripcion": f"{apt.get('especialidad', '')} - {apt.get('prestador', '')}"[:72],
        }
