# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: Interactive selection messages for appointment booking.
# ============================================================================
"""Interactive Selection Service.

Handles sending interactive WhatsApp messages for appointment booking flow:
- Specialty selection
- Provider selection
- Date selection
- Time selection
- Suggested appointments
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.integrations.chattigo import ChattigoMultiDIDAdapter

logger = logging.getLogger(__name__)


class InteractiveSelectionService:
    """Service for sending interactive selection messages.

    Handles the interactive list and button messages used during
    the appointment booking flow.
    """

    def __init__(self, adapter: "ChattigoMultiDIDAdapter") -> None:
        """Initialize with Chattigo adapter.

        Args:
            adapter: Initialized Chattigo adapter for sending messages.
        """
        self._adapter = adapter

    async def send_specialty_selection(
        self,
        phone: str,
        specialties: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send interactive list for specialty selection.

        Args:
            phone: Recipient phone number.
            specialties: List of specialty dicts with "code" and "name" keys.

        Returns:
            API response dict.
        """
        rows = [
            {
                "id": spec["code"],
                "title": spec["name"][:24],
                "description": spec.get("description", "")[:72],
            }
            for spec in specialties[:10]
        ]

        result = await self._adapter.send_interactive_list(
            msisdn=phone,
            body="Seleccione la especialidad para su turno:",
            button_text="Ver opciones",
            sections=[{"title": "Especialidades", "rows": rows}],
            header="Agendar Turno",
            footer="Elija una especialidad de la lista.",
        )

        logger.info(f"Specialty selection sent to {phone}")
        return result

    async def send_provider_selection(
        self,
        phone: str,
        providers: list[dict[str, Any]],
        specialty_name: str,
    ) -> dict[str, Any]:
        """Send interactive list for provider selection.

        Args:
            phone: Recipient phone number.
            providers: List of provider dicts with "id", "name", "next_available".
            specialty_name: Name of selected specialty (for context).

        Returns:
            API response dict.
        """
        rows = [
            {
                "id": str(prov["id"]),
                "title": prov["name"][:24],
                "description": prov.get("next_available", "")[:72],
            }
            for prov in providers[:10]
        ]

        result = await self._adapter.send_interactive_list(
            msisdn=phone,
            body=f"Profesionales disponibles en {specialty_name}:",
            button_text="Ver profesionales",
            sections=[{"title": "Profesionales", "rows": rows}],
            header="Seleccionar Profesional",
            footer="Elija un profesional de la lista.",
        )

        logger.info(f"Provider selection sent to {phone}")
        return result

    async def send_date_selection(
        self,
        phone: str,
        available_dates: list[str],
        provider_name: str,
    ) -> dict[str, Any]:
        """Send interactive list for date selection.

        Args:
            phone: Recipient phone number.
            available_dates: List of available dates (formatted strings).
            provider_name: Name of selected provider (for context).

        Returns:
            API response dict.
        """
        rows = [
            {
                "id": f"date_{i}",
                "title": date[:24],
                "description": "",
            }
            for i, date in enumerate(available_dates[:10])
        ]

        result = await self._adapter.send_interactive_list(
            msisdn=phone,
            body=f"Fechas disponibles con {provider_name}:",
            button_text="Ver fechas",
            sections=[{"title": "Fechas Disponibles", "rows": rows}],
            header="Seleccionar Fecha",
        )

        logger.info(f"Date selection sent to {phone}")
        return result

    async def send_time_selection(
        self,
        phone: str,
        available_times: list[str],
        selected_date: str,
    ) -> dict[str, Any]:
        """Send interactive list for time selection.

        Args:
            phone: Recipient phone number.
            available_times: List of available times (formatted strings).
            selected_date: Selected date (for context).

        Returns:
            API response dict.
        """
        rows = [
            {
                "id": f"time_{i}",
                "title": time[:24],
                "description": "",
            }
            for i, time in enumerate(available_times[:10])
        ]

        result = await self._adapter.send_interactive_list(
            msisdn=phone,
            body=f"Horarios disponibles para el {selected_date}:",
            button_text="Ver horarios",
            sections=[{"title": "Horarios Disponibles", "rows": rows}],
            header="Seleccionar Horario",
        )

        logger.info(f"Time selection sent to {phone}")
        return result

    async def send_suggested_appointment(
        self,
        phone: str,
        appointment_details: dict[str, Any],
    ) -> dict[str, Any]:
        """Send suggested appointment with accept/other buttons.

        Args:
            phone: Recipient phone number.
            appointment_details: Dict with "date", "time", "provider", "specialty".

        Returns:
            API response dict.
        """
        body = (
            f"Tenemos un turno disponible para usted:\n\n"
            f"Fecha: {appointment_details['date']}\n"
            f"Hora: {appointment_details['time']}\n"
            f"Profesional: {appointment_details['provider']}\n"
            f"Especialidad: {appointment_details['specialty']}"
        )

        result = await self._adapter.send_interactive_buttons(
            msisdn=phone,
            body=body,
            buttons=[
                {"id": "accept_suggested", "title": "Agendar"},
                {"id": "other_appointment", "title": "Otro Turno"},
                {"id": "different_person", "title": "Soy Otra Persona"},
            ],
            header="Turno Sugerido",
            footer="Seleccione una opcion.",
        )

        logger.info(f"Suggested appointment sent to {phone}")
        return result
