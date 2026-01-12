# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Reschedule appointment node.
# ============================================================================
"""Reschedule Node.

Handles the rescheduling of existing appointments.
Refactored with helpers to reduce code duplication (SRP).
"""

import logging
from typing import TYPE_CHECKING, Any, Callable

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)

# Type alias for item formatters
ItemFormatter = Callable[[int, Any], dict[str, str]]


class RescheduleNode(BaseNode):
    """Node for handling appointment rescheduling.

    Guides the user through rescheduling an existing appointment.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process reschedule request."""
        phone = state.get("user_phone")
        appointment_id = state.get("appointment_id")

        # Route based on current stage
        if state.get("reschedule_time_selected"):
            return await self._confirm_reschedule(state)
        if state.get("reschedule_date_selected"):
            return await self._select_time(state, phone)
        if state.get("reschedule_dates_loaded"):
            return await self._process_date_selection(state, phone)
        if not appointment_id:
            return await self._show_appointments(state, phone)
        return await self._load_dates(state, appointment_id, phone)

    # =========================================================================
    # Stage Handlers
    # =========================================================================

    async def _show_appointments(self, state: "MedicalAppointmentsState", phone: str | None) -> dict[str, Any]:
        """Show patient's appointments for rescheduling."""
        patient_id = self._get_patient_id(state)
        if not patient_id:
            return self._text_response("Para reprogramar, primero necesito identificarte.\nIngresá tu DNI.")

        result = await self._medical.obtener_turnos_paciente(patient_id)
        appointments = result.get_list() if result.success else []

        if not appointments:
            return self._text_response("No encontramos turnos para reprogramar.\n¿Querés agendar uno nuevo?")

        def format_apt(i: int, apt: dict) -> dict[str, str]:
            return {
                "id": str(apt.get("idTurno") or apt.get("id") or i),
                "nombre": f"{apt.get('fecha', 'N/A')} - {apt.get('especialidad', '')}",
                "descripcion": apt.get("prestador", "")[:72],
            }

        return await self._show_list(
            phone,
            "Seleccioná el turno a reprogramar:",
            appointments,
            format_apt,
            "Ver turnos",
            "Ingresá el número del turno:",
            patient_appointments=appointments,
            is_rescheduling=True,
        )

    async def _load_dates(
        self, state: "MedicalAppointmentsState", appointment_id: str, phone: str | None
    ) -> dict[str, Any]:
        """Load available dates for rescheduling."""
        result = await self._medical.obtener_dias_turno(appointment_id)
        dates = result.get_list() if result.success else []

        if not dates:
            return self._text_response("No hay fechas disponibles.\nContactá a la institución.")

        date_list = [str(d) if isinstance(d, str) else d.get("fecha", str(d)) for d in dates]

        def format_date(i: int, d: str) -> dict[str, str]:
            return {"id": d, "nombre": d}

        return await self._show_list(
            phone,
            "Fechas disponibles para reprogramar:",
            date_list,
            format_date,
            "Ver fechas",
            "Ingresá el número de la nueva fecha:",
            reschedule_dates=date_list,
            reschedule_dates_loaded=True,
        )

    async def _process_date_selection(self, state: "MedicalAppointmentsState", phone: str | None) -> dict[str, Any]:
        """Process date selection and load times."""
        dates = state.get("reschedule_dates", [])
        selection = self._get_selection(state)

        if selection is None or not 0 <= selection < len(dates):
            return self._text_response(
                f"Opción inválida. Seleccioná un número del 1 al {len(dates)}.",
                reschedule_dates=dates,
                reschedule_dates_loaded=True,
            )

        selected_date = dates[selection]
        appointment_id = state.get("appointment_id") or ""
        result = await self._medical.obtener_horas_turno(appointment_id, selected_date)
        times = result.get_list() if result.success else []

        if not times:
            return self._text_response(
                f"No hay horarios para {selected_date}. Elegí otra fecha.",
                reschedule_dates=dates,
                reschedule_dates_loaded=True,
            )

        time_list = [str(t) if isinstance(t, str) else t.get("hora", str(t)) for t in times]

        def format_time(i: int, t: str) -> dict[str, str]:
            return {"id": t, "nombre": t}

        return await self._show_list(
            phone,
            f"Horarios para {selected_date}:",
            time_list,
            format_time,
            "Ver horarios",
            "Ingresá el número del nuevo horario:",
            reschedule_selected_date=selected_date,
            reschedule_times=time_list,
            reschedule_date_selected=True,
        )

    async def _select_time(self, state: "MedicalAppointmentsState", phone: str | None) -> dict[str, Any]:
        """Process time selection and show confirmation."""
        times = state.get("reschedule_times", [])
        selection = self._get_selection(state)

        if selection is None or not 0 <= selection < len(times):
            return self._text_response(
                f"Opción inválida. Seleccioná un número del 1 al {len(times)}.",
                reschedule_times=times,
                reschedule_date_selected=True,
            )

        selected_time = times[selection]
        selected_date = state.get("reschedule_selected_date", "")

        body = (
            "📋 *Reprogramar turno:*\n\n"
            f"📅 Nueva fecha: {selected_date}\n"
            f"🕐 Nuevo horario: {selected_time}\n\n"
            "¿Confirmás la reprogramación?"
        )

        if phone and self._notification:
            await self._send_interactive_buttons(
                phone,
                body,
                [{"id": "confirm_reschedule", "title": "Confirmar"}, {"id": "cancel_reschedule", "title": "Cancelar"}],
            )

        return self._text_response(
            body + " (Sí/No)",
            reschedule_selected_time=selected_time,
            reschedule_time_selected=True,
            awaiting_confirmation=True,
        )

    async def _confirm_reschedule(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Confirm and execute rescheduling."""
        message = self._get_message(state)

        if not self._is_confirmation(message):
            return self._text_response(
                "Reprogramación cancelada.\nIngresá tu DNI para comenzar.",
                **self._reset_state(),
            )

        appointment_id = state.get("appointment_id") or ""
        new_date = state.get("reschedule_selected_date") or ""
        new_time = state.get("reschedule_selected_time") or ""

        result = await self._medical.reprogramar_turno(
            id_turno=appointment_id,
            fecha_hora=f"{new_date} {new_time}",
        )

        if not result.success:
            return self._text_response(
                f"❌ No se pudo reprogramar: {result.error_message}\n"
                "Intentá nuevamente o contactá a la institución.",
                **self._reset_state(),
            )

        return self._text_response(
            f"✅ *¡Turno reprogramado!*\n\n"
            f"📅 Nueva fecha: {new_date}\n"
            f"🕐 Nuevo horario: {new_time}\n\n"
            "Te enviaremos un recordatorio. ¡Gracias!",
            is_complete=True,
            **self._reset_state(),
        )

    # =========================================================================
    # Helpers (SRP - reduce duplication)
    # =========================================================================

    async def _show_list(
        self,
        phone: str | None,
        title: str,
        items: list[Any],
        formatter: ItemFormatter,
        button_text: str,
        prompt: str,
        **state_updates: Any,
    ) -> dict[str, Any]:
        """Show a selection list with optional interactive message."""
        if phone and self._notification:
            formatted = [formatter(i, item) for i, item in enumerate(items[:10])]
            await self._send_interactive_list(phone, title, formatted, button_text)

        text = f"{title}\n\n"
        for i, item in enumerate(items[:10], 1):
            formatted = formatter(i - 1, item)
            text += f"{i}. {formatted.get('nombre', str(item))}\n"
        text += f"\n{prompt}"

        return self._text_response(text, **state_updates)

    def _reset_state(self) -> dict[str, Any]:
        """Reset reschedule-related state flags."""
        return {
            "is_rescheduling": False,
            "reschedule_dates_loaded": False,
            "reschedule_date_selected": False,
            "reschedule_time_selected": False,
            "awaiting_confirmation": False,
        }
