# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Booking confirmation node.
# ============================================================================
"""Booking Confirmation Node.

Handles the final booking confirmation and appointment creation.
Refactored with helpers to reduce code duplication (SRP).
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class BookingConfirmationNode(BaseNode):
    """Node for handling booking confirmation."""

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process booking confirmation."""
        message = self._get_message(state)
        phone = state.get("user_phone")

        if state.get("suggested_appointment"):
            return await self._handle_suggested(state, message, phone)
        if not self._is_confirmation(message):
            return self._cancel_response()
        return await self._create_appointment(state, phone)

    # =========================================================================
    # Handlers
    # =========================================================================

    async def _handle_suggested(
        self, state: "MedicalAppointmentsState", message: str, phone: str | None
    ) -> dict[str, Any]:
        """Handle suggested appointment confirmation."""
        if not self._is_confirmation(message):
            return self._text_response(
                "Entendido. Vamos a buscar otro turno.\n¿Qué especialidad necesitás?",
                suggested_appointment=None,
                awaiting_confirmation=False,
            )

        suggested: dict = state.get("suggested_appointment") or {}
        apt_id = suggested.get("idTurno") or suggested.get("id")

        if apt_id:
            result = await self._medical.confirmar_turno(str(apt_id))
            if result.success:
                return self._success_response(str(apt_id), suggested)

        return await self._create_from_suggested(state, suggested, phone)

    async def _create_from_suggested(
        self, state: "MedicalAppointmentsState", suggested: dict, phone: str | None
    ) -> dict[str, Any]:
        """Create appointment from suggested data."""
        return await self._do_create(
            state,
            phone,
            provider_id=str(suggested.get("idPrestador") or suggested.get("matricula") or ""),
            fecha=suggested.get("fecha", ""),
            hora=suggested.get("hora", ""),
            especialidad=str(suggested.get("especialidad") or suggested.get("idEspecialidad") or ""),
            provider_name=suggested.get("prestador", "N/A"),
        )

    async def _create_appointment(self, state: "MedicalAppointmentsState", phone: str | None) -> dict[str, Any]:
        """Create appointment from selected options."""
        return await self._do_create(
            state,
            phone,
            provider_id=self._get_provider_id(state),
            fecha=state.get("selected_date") or "",
            hora=state.get("selected_time") or "",
            especialidad=self._get_specialty_id(state),
            provider_name=state.get("selected_provider_name") or "N/A",
        )

    async def _do_create(
        self,
        state: "MedicalAppointmentsState",
        phone: str | None,
        provider_id: str,
        fecha: str,
        hora: str,
        especialidad: str,
        provider_name: str,
    ) -> dict[str, Any]:
        """Execute appointment creation."""
        result = await self._medical.crear_turno_whatsapp(
            id_paciente=self._get_patient_id(state),
            id_prestador=provider_id,
            fecha_hora=f"{fecha} {hora}",
            especialidad=especialidad,
            celular=phone or "",
        )

        if not result.success:
            return self._handle_error(result.error_code or "", result.error_message or "Error")

        data = result.get_dict()
        apt_id = str(data.get("idTurno") or data.get("id_turno") or "")

        # Send interactive buttons
        if phone and self._notification:
            await self._send_confirmation_buttons(phone, apt_id, fecha, hora, provider_name, state)

        return self._success_response(
            apt_id,
            {
                "fecha": fecha,
                "hora": hora,
                "prestador": provider_name,
            },
        )

    # =========================================================================
    # Response Helpers
    # =========================================================================

    def _success_response(self, apt_id: str, data: dict) -> dict[str, Any]:
        """Build success response."""
        return self._text_response(
            f"✅ *¡Turno confirmado!*\n\n"
            f"📋 Número: {apt_id or 'N/A'}\n"
            f"📅 Fecha: {data.get('fecha', 'N/A')}\n"
            f"🕐 Hora: {data.get('hora', 'N/A')}\n"
            f"👨‍⚕️ Profesional: {data.get('prestador', 'N/A')}\n\n"
            "Te enviaremos un recordatorio. ¡Gracias!",
            appointment_id=apt_id,
            is_complete=True,
            suggested_appointment=None,
            awaiting_confirmation=False,
        )

    def _cancel_response(self) -> dict[str, Any]:
        """Build cancellation response."""
        return self._text_response(
            "Turno cancelado.\nIngresá tu DNI para comenzar de nuevo.",
            awaiting_confirmation=False,
            selected_specialty=None,
            selected_specialty_name=None,
            selected_provider=None,
            selected_provider_id=None,
            selected_provider_name=None,
            selected_date=None,
            selected_time=None,
        )

    def _handle_error(self, error_code: str, error_msg: str) -> dict[str, Any]:
        """Handle creation errors."""
        code_upper = error_code.upper()

        if "TURNO_DUPLICADO" in code_upper:
            return self._text_response(
                "⚠️ Ya tenés un turno para esta especialidad.\n¿Querés ver tus turnos?",
                suggested_appointment=None,
                awaiting_confirmation=False,
            )
        if "HORARIO_OCUPADO" in code_upper:
            return self._text_response(
                "⚠️ El horario ya fue ocupado.\nSeleccioná otro horario.",
                suggested_appointment=None,
                awaiting_confirmation=False,
            )

        return self._text_response(
            f"❌ No se pudo crear el turno: {error_msg}\nContactá a la institución.",
            suggested_appointment=None,
            awaiting_confirmation=False,
        )

    async def _send_confirmation_buttons(
        self, phone: str, apt_id: str, fecha: str, hora: str, provider: str, state: "MedicalAppointmentsState"
    ) -> None:
        """Send confirmation with interactive buttons."""
        body = (
            f"✅ *¡Turno confirmado!*\n\n"
            f"📋 Número: {apt_id or 'N/A'}\n"
            f"👤 Paciente: {state.get('patient_name', 'N/A')}\n"
            f"🏥 Especialidad: {state.get('selected_specialty_name', 'N/A')}\n"
            f"👨‍⚕️ Profesional: {provider}\n"
            f"📅 Fecha: {fecha}\n🕐 Hora: {hora}\n\n"
            "Te enviaremos un recordatorio."
        )
        await self._send_interactive_buttons(
            phone,
            body,
            [{"id": "new_appointment", "title": "Nuevo Turno"}, {"id": "view_appointments", "title": "Mis Turnos"}],
        )
