# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Fallback node for unrecognized messages.
# ============================================================================
"""Fallback Node.

Handles unrecognized messages and error recovery.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState

logger = logging.getLogger(__name__)


class FallbackNode(BaseNode):
    """Node for handling fallback scenarios.

    Handles:
    - Unrecognized messages
    - Error recovery
    - Help requests
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process fallback.

        Args:
            state: Current state.

        Returns:
            State updates with help message.
        """
        error_count = state.get("error_count", 0) + 1
        max_errors = state.get("max_errors", 3)
        phone = state.get("user_phone")

        # Check if too many errors
        if error_count >= max_errors:
            return await self._handle_max_errors(state, phone)

        # Check context for appropriate response
        if state.get("is_registered"):
            return await self._handle_registered_fallback(state, error_count, phone)

        return await self._handle_general_fallback(state, error_count, phone)

    async def _handle_max_errors(
        self,
        state: "MedicalAppointmentsState",
        phone: str | None,
    ) -> dict[str, Any]:
        """Handle case where user has reached max errors."""
        institution_name = self._config.get("institution_name", "la institución")
        contact_phone = self._config.get("contact_phone", "")

        contact_info = f"al teléfono {contact_phone}" if contact_phone else ""

        response = (
            "Parece que estás teniendo dificultades. 😕\n\n"
            f"Te recomendamos contactar directamente a {institution_name} {contact_info} "
            "para recibir asistencia personalizada.\n\n"
            "O podés comenzar de nuevo ingresando tu DNI."
        )

        if phone and self._notification:
            await self._send_interactive_buttons(
                phone=phone,
                body=response,
                buttons=[
                    {"id": "new_session", "title": "Comenzar de Nuevo"},
                    {"id": "contact_institution", "title": "Contactar"},
                ],
            )

        return self._text_response(
            response,
            error_count=0,  # Reset error count
        )

    async def _handle_registered_fallback(
        self,
        state: "MedicalAppointmentsState",
        error_count: int,
        phone: str | None,
    ) -> dict[str, Any]:
        """Handle fallback for registered users."""
        patient_name = state.get("patient_name", "")

        response = (
            f"No entendí tu mensaje{', ' + patient_name if patient_name else ''}. 🤔\n\n"
            "Por favor, seleccioná una opción:\n"
            "1. Agendar un turno\n"
            "2. Ver mis turnos\n"
            "3. Cancelar un turno\n"
            "4. Reprogramar un turno\n\n"
            "O escribí el número de la opción que necesitás."
        )

        if phone and self._notification:
            await self._send_interactive_buttons(
                phone=phone,
                body="No entendí tu mensaje. ¿Qué querés hacer?",
                buttons=[
                    {"id": "nuevo_turno", "title": "Nuevo Turno"},
                    {"id": "mis_turnos", "title": "Mis Turnos"},
                    {"id": "reprogramar", "title": "Reprogramar"},
                ],
            )

        return self._text_response(response, error_count=error_count)

    async def _handle_general_fallback(
        self,
        state: "MedicalAppointmentsState",
        error_count: int,
        phone: str | None,
    ) -> dict[str, Any]:
        """Handle general fallback for unregistered users."""
        response = (
            "No entendí tu mensaje. 🤔\n\n"
            "Para agendar un turno, por favor:\n"
            "• Ingresá tu DNI (sin puntos)\n"
            "• O escribí 'Hola' para comenzar\n\n"
            "Ejemplo: 12345678"
        )

        if phone and self._notification:
            await self._send_interactive_buttons(
                phone=phone,
                body="No entendí tu mensaje. ¿Cómo puedo ayudarte?",
                buttons=[
                    {"id": "nuevo_turno", "title": "Agendar Turno"},
                    {"id": "ayuda", "title": "Necesito Ayuda"},
                ],
            )

        return self._text_response(response, error_count=error_count)
