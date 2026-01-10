# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Patient identification node.
# ============================================================================
"""Patient Identification Node.

Handles patient identification by DNI and retrieval of patient data.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class PatientIdentificationNode(BaseNode):
    """Node for identifying patients by DNI.

    Searches for patient in the external system and retrieves
    their data and suggested appointments.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process patient identification.

        Args:
            state: Current state with patient_document.

        Returns:
            State updates with patient data or registration prompt.
        """
        document = state.get("patient_document", "")
        phone = state.get("user_phone")

        if not document:
            return self._text_response("Por favor, ingresá tu número de DNI (sin puntos).")

        # Search patient in external system
        result = await self._medical.buscar_paciente_dni(document)

        if not result.success:
            logger.warning(f"Patient search failed for {document}: {result.error_message}")
            return self._text_response(
                f"No pudimos encontrar tu información con el DNI: {document}\n\n"
                "Si es correcto, probablemente necesites registrarte. "
                "Por favor, contactá a la institución para completar tu registro.",
                needs_registration=True,
            )

        # Extract patient data
        patient_data = result.get_dict()
        patient_id = str(
            patient_data.get("idPaciente") or patient_data.get("IdPaciente") or patient_data.get("id") or ""
        )
        patient_name = (
            patient_data.get("nombreCompleto") or patient_data.get("nombre") or patient_data.get("Nombre") or ""
        )

        # Check for suggested appointment
        suggested = await self._get_suggested_appointment(document)

        if suggested:
            return await self._handle_suggested_appointment(
                state, patient_data, patient_id, patient_name, suggested, phone
            )

        # No suggested appointment - show specialties
        return await self._show_specialties(state, patient_data, patient_id, patient_name, phone)

    async def _get_suggested_appointment(self, document: str) -> dict[str, Any] | None:
        """Get suggested appointment for patient."""
        result = await self._medical.obtener_turno_sugerido(document)
        if result.success and result.data:
            return result.get_dict()
        return None

    async def _handle_suggested_appointment(
        self,
        state: "MedicalAppointmentsState",
        patient_data: dict[str, Any],
        patient_id: str,
        patient_name: str,
        suggested: dict[str, Any],
        phone: str | None,
    ) -> dict[str, Any]:
        """Handle case where patient has a suggested appointment."""
        fecha = suggested.get("fecha", "N/A")
        hora = suggested.get("hora", "N/A")
        prestador = suggested.get("prestador", "N/A")
        _especialidad = suggested.get("especialidad", "")  # Reserved for future use

        # Send interactive buttons if WhatsApp available
        if phone and self._notification:
            await self._send_interactive_buttons(
                phone=phone,
                body=(
                    f"¡Hola {patient_name}! 👋\n\n"
                    f"Tenés un turno sugerido:\n"
                    f"📅 Fecha: {fecha}\n"
                    f"🕐 Hora: {hora}\n"
                    f"👨‍⚕️ Profesional: {prestador}\n\n"
                    "¿Querés confirmar este turno?"
                ),
                buttons=[
                    {"id": "accept_suggested", "title": "Confirmar"},
                    {"id": "other_appointment", "title": "Otro Turno"},
                    {"id": "different_person", "title": "Soy Otra Persona"},
                ],
            )

        response = (
            f"¡Hola {patient_name}! 👋\n\n"
            f"Tenés un turno sugerido:\n"
            f"📅 Fecha: {fecha}\n"
            f"🕐 Hora: {hora}\n"
            f"👨‍⚕️ Profesional: {prestador}\n\n"
            "¿Querés confirmar este turno? (Sí/No)"
        )

        return self._text_response(
            response,
            patient_data=patient_data,
            patient_id=patient_id,
            patient_name=patient_name,
            is_registered=True,
            suggested_appointment=suggested,
            awaiting_confirmation=True,
        )

    async def _show_specialties(
        self,
        state: "MedicalAppointmentsState",
        patient_data: dict[str, Any],
        patient_id: str,
        patient_name: str,
        phone: str | None,
    ) -> dict[str, Any]:
        """Show available specialties to patient."""
        result = await self._medical.obtener_especialidades_bot()

        specialties: list[dict[str, Any]] = []
        if result.success:
            data = result.data
            if isinstance(data, list):
                specialties = data
            elif isinstance(data, dict):
                specialties = data.get("especialidades", [])
                if isinstance(specialties, dict):
                    specialties = [specialties]

        if not specialties:
            return self._text_response(
                f"¡Hola {patient_name}! 👋\n\n"
                "No hay especialidades disponibles en este momento. "
                "Por favor, contactá a la institución.",
                patient_data=patient_data,
                patient_id=patient_id,
                patient_name=patient_name,
                is_registered=True,
            )

        # Send interactive list if WhatsApp available
        if phone and self._notification:
            await self._send_interactive_list(
                phone=phone,
                title=f"¡Hola {patient_name}! 👋\n\nSeleccioná la especialidad:",
                items=specialties,
                button_text="Ver especialidades",
            )

        # Build text response
        response = f"¡Hola {patient_name}! 👋\n\n¿Qué especialidad necesitás?\n\n"
        for i, spec in enumerate(specialties[:10], 1):
            name = spec.get("nombre") or spec.get("descripcion") or f"Opción {i}"
            response += f"{i}. {name}\n"

        return self._text_response(
            response,
            patient_data=patient_data,
            patient_id=patient_id,
            patient_name=patient_name,
            is_registered=True,
            specialties_list=specialties,
        )
