# ============================================================================
# SCOPE: DOMAIN-SPECIFIC (Medical Appointments)
# Description: Service for sending appointment-related notifications via WhatsApp.
#              Uses the global Chattigo adapter for communication.
# ============================================================================
"""
Appointment Notification Service.

Sends appointment confirmations, reminders, and interactive messages
using the global Chattigo adapter.

Usage:
    from app.domains.medical_appointments.infrastructure.services import (
        AppointmentNotificationService,
    )

    service = AppointmentNotificationService(db=session, did="5492645668671")
    await service.send_appointment_confirmation(appointment, patient)
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from app.integrations.chattigo import get_chattigo_adapter_factory

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.medical_appointments.domain.entities import (
        Appointment,
        Patient,
    )
    from app.integrations.chattigo import ChattigoMultiDIDAdapter

logger = logging.getLogger(__name__)


class AppointmentNotificationService:
    """
    Service for sending appointment-related notifications via WhatsApp.

    Uses the global Chattigo adapter (multi-DID) for all communications.
    Credentials are stored in database (chattigo_credentials table).

    Implements INotificationService for DIP compliance.
    Single Responsibility: Build and send appointment-specific messages.
    """

    def __init__(self, db: "AsyncSession", did: str) -> None:
        """
        Initialize notification service.

        Args:
            db: Database session (for credential lookup)
            did: WhatsApp Business DID (phone number)
        """
        self._db = db
        self._did = did
        self._adapter: "ChattigoMultiDIDAdapter | None" = None

    async def _get_adapter(self) -> "ChattigoMultiDIDAdapter":
        """Get or create Chattigo adapter for configured DID."""
        if self._adapter is None:
            factory = get_chattigo_adapter_factory()
            self._adapter = await factory.get_adapter(self._db, did=self._did)
            await self._adapter.initialize()
        return self._adapter

    async def close(self) -> None:
        """Close adapter connection."""
        if self._adapter:
            await self._adapter.close()
            self._adapter = None

    async def __aenter__(self) -> "AppointmentNotificationService":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    # =========================================================================
    # INotificationService Interface Methods
    # =========================================================================

    async def send_message(self, phone: str, message: str) -> dict:
        """Send a text message.

        Args:
            phone: Recipient phone number.
            message: Message text.

        Returns:
            API response dict.
        """
        adapter = await self._get_adapter()
        result = await adapter.send_message(msisdn=phone, message=message)
        logger.info(f"Message sent to {phone}")
        return result

    async def send_interactive_list(
        self,
        phone: str,
        title: str,
        items: list[dict],
        button_text: str = "Ver opciones",
    ) -> dict:
        """Send an interactive list message.

        Args:
            phone: Recipient phone number.
            title: List title/body text.
            items: List items with id, title, description.
            button_text: Button text to open list.

        Returns:
            API response dict.
        """
        adapter = await self._get_adapter()

        rows = [
            {
                "id": str(item.get("id", f"item_{i}")),
                "title": str(item.get("title", ""))[:24],
                "description": str(item.get("description", ""))[:72],
            }
            for i, item in enumerate(items[:10])
        ]

        result = await adapter.send_interactive_list(
            msisdn=phone,
            body=title,
            button_text=button_text,
            sections=[{"title": "Opciones", "rows": rows}],
        )
        logger.info(f"Interactive list sent to {phone}")
        return result

    async def send_interactive_buttons(
        self,
        phone: str,
        body: str,
        buttons: list[dict],
    ) -> dict:
        """Send interactive buttons message.

        Args:
            phone: Recipient phone number.
            body: Message body.
            buttons: List of buttons with id and title.

        Returns:
            API response dict.
        """
        adapter = await self._get_adapter()

        formatted_buttons = [
            {"id": str(btn.get("id", f"btn_{i}")), "title": str(btn.get("title", ""))[:20]}
            for i, btn in enumerate(buttons[:3])
        ]

        result = await adapter.send_interactive_buttons(
            msisdn=phone,
            body=body,
            buttons=formatted_buttons,
        )
        logger.info(f"Interactive buttons sent to {phone}")
        return result

    async def send_template(
        self,
        phone: str,
        template_name: str,
        parameters: list[str],
    ) -> dict:
        """Send a template message (HSM).

        Args:
            phone: Recipient phone number.
            template_name: Template name.
            parameters: Template parameters as strings.

        Returns:
            API response dict.
        """
        adapter = await self._get_adapter()

        components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": param} for param in parameters],
            }
        ]

        result = await adapter.send_template(
            msisdn=phone,
            template_name=template_name,
            components=components,
        )
        logger.info(f"Template '{template_name}' sent to {phone}")
        return result

    # =========================================================================
    # Appointment Confirmations
    # =========================================================================

    async def send_appointment_confirmation(
        self,
        appointment: "Appointment",
        patient: "Patient",
    ) -> dict:
        """
        Send appointment confirmation message to patient.

        Args:
            appointment: Confirmed appointment
            patient: Patient to notify

        Returns:
            API response dict
        """
        adapter = await self._get_adapter()

        message = self._build_confirmation_message(appointment, patient)

        result = await adapter.send_message(
            msisdn=patient.phone,
            message=message,
        )

        logger.info(f"Appointment confirmation sent to {patient.phone} " f"for appointment {appointment.id}")

        return result

    async def send_appointment_confirmation_with_buttons(
        self,
        appointment: "Appointment",
        patient: "Patient",
        _confirm_url: str,  # Reserved for future URL-based confirmation
        _cancel_url: str,  # Reserved for future URL-based cancellation
    ) -> dict:
        """
        Send appointment confirmation with confirm/cancel buttons.

        Args:
            appointment: Appointment to confirm
            patient: Patient to notify
            confirm_url: URL for confirmation action
            cancel_url: URL for cancellation action

        Returns:
            API response dict
        """
        adapter = await self._get_adapter()

        body = self._build_confirmation_message(appointment, patient)

        result = await adapter.send_interactive_buttons(
            msisdn=patient.phone,
            body=body,
            buttons=[
                {"id": f"confirm_{appointment.id}", "title": "Confirmar"},
                {"id": f"cancel_{appointment.id}", "title": "Cancelar"},
            ],
            footer="Seleccione una opcion.",
        )

        logger.info(f"Appointment confirmation (with buttons) sent to {patient.phone}")

        return result

    # =========================================================================
    # Appointment Reminders
    # =========================================================================

    async def send_appointment_reminder(
        self,
        appointment: "Appointment",
        patient: "Patient",
        days_before: int = 1,
        special_instructions: str | None = None,
    ) -> dict:
        """
        Send appointment reminder using HSM template.

        Args:
            appointment: Upcoming appointment
            patient: Patient to remind
            days_before: Days until appointment (for message customization)
            special_instructions: Optional preparation instructions

        Returns:
            API response dict
        """
        adapter = await self._get_adapter()

        # Build template components
        components = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": patient.display_name},
                    {"type": "text", "text": self._format_day_of_week(appointment.appointment_datetime)},
                    {"type": "text", "text": appointment.formatted_date},
                    {"type": "text", "text": appointment.formatted_time},
                    {"type": "text", "text": appointment.provider_name},
                ],
            }
        ]

        # Add button parameters if template supports them
        if special_instructions:
            components.append(
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": special_instructions}],
                }
            )

        result = await adapter.send_template(
            msisdn=patient.phone,
            template_name="recordatorio_turno",
            components=components,
        )

        logger.info(f"Appointment reminder sent to {patient.phone} " f"({days_before} days before)")

        return result

    # =========================================================================
    # Patient Registration
    # =========================================================================

    async def send_registration_flow(
        self,
        phone: str,
        flow_id: str = "2244089509373557",
        screen: str = "Screen_A",
    ) -> dict:
        """
        Send WhatsApp Flow for patient registration.

        Args:
            phone: Recipient phone number
            flow_id: WhatsApp Flow ID
            screen: Initial screen to display

        Returns:
            API response dict
        """
        adapter = await self._get_adapter()

        result = await adapter.send_whatsapp_flow(
            msisdn=phone,
            body="Para continuar, necesitamos registrar sus datos.",
            flow_id=flow_id,
            flow_cta="Registrarse",
            screen=screen,
            header="Registro de Paciente",
        )

        logger.info(f"Registration flow sent to {phone}")

        return result

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_confirmation_message(
        self,
        appointment: "Appointment",
        patient: "Patient",
    ) -> str:
        """Build confirmation message text."""
        return (
            f"Turno confirmado para {patient.display_name}\n\n"
            f"Fecha: {appointment.formatted_date}\n"
            f"Hora: {appointment.formatted_time}\n"
            f"Profesional: {appointment.provider_name}\n"
            f"Especialidad: {appointment.specialty_name}\n\n"
            "Gracias por confiar en nosotros."
        )

    @staticmethod
    def _format_day_of_week(dt: datetime | None) -> str:
        """Format datetime to Spanish day of week."""
        if dt is None:
            return ""
        days = {
            0: "Lunes",
            1: "Martes",
            2: "Miércoles",
            3: "Jueves",
            4: "Viernes",
            5: "Sábado",
            6: "Domingo",
        }
        return days.get(dt.weekday(), "")
