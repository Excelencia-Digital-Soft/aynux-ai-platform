# ============================================================================
# SCOPE: AGENTS LAYER (Medical Appointments)
# Description: Greeting node for welcoming users.
# ============================================================================
"""Greeting Node.

Handles the initial greeting when a user starts a conversation.
"""

from typing import TYPE_CHECKING, Any

from .base import BaseNode

if TYPE_CHECKING:
    from ..state import MedicalAppointmentsState


class GreetingNode(BaseNode):
    """Node for handling greeting messages.

    Welcomes the user and prompts for DNI to begin the booking flow.
    """

    async def process(self, state: "MedicalAppointmentsState") -> dict[str, Any]:
        """Process greeting.

        Args:
            state: Current state.

        Returns:
            State updates with greeting message.
        """
        institution_name = self._config.get("institution_name", "la institución")
        phone = state.get("user_phone")

        # Try to send interactive buttons via WhatsApp
        if phone and self._notification:
            await self._send_interactive_buttons(
                phone=phone,
                body=(
                    f"¡Hola! 👋 Bienvenido al sistema de turnos de {institution_name}.\n\n" "¿Qué te gustaría hacer?"
                ),
                buttons=[
                    {"id": "nuevo_turno", "title": "Nuevo Turno"},
                    {"id": "mis_turnos", "title": "Mis Turnos"},
                    {"id": "cancelar_turno", "title": "Cancelar Turno"},
                ],
            )

        response = (
            f"¡Hola! 👋 Bienvenido al sistema de turnos de {institution_name}.\n\n"
            "Para agendar un turno, por favor ingresá tu número de DNI (sin puntos)."
        )

        return self._text_response(response)
