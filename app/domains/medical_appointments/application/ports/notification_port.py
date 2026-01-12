# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Notification service port (DIP compliant).
# ============================================================================
"""Notification Service Port.

Defines the interface for sending notifications via WhatsApp.
Used for dependency inversion in agent nodes and use cases.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ...domain.entities.appointment import Appointment
    from ...domain.entities.patient import Patient


@runtime_checkable
class INotificationService(Protocol):
    """Interface for notification services.

    Implementations: AppointmentNotificationService

    This interface allows nodes and use cases to depend on
    an abstraction rather than concrete notification implementations.
    """

    async def send_message(
        self,
        phone: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a text message.

        Args:
            phone: Recipient phone number.
            message: Message text.

        Returns:
            API response dict.
        """
        ...

    async def send_interactive_list(
        self,
        phone: str,
        title: str,
        items: list[dict[str, Any]],
        button_text: str = "Ver opciones",
    ) -> dict[str, Any]:
        """Send an interactive list message.

        Args:
            phone: Recipient phone number.
            title: List title/body text.
            items: List items with id, title, description.
            button_text: Button text to open list.

        Returns:
            API response dict.
        """
        ...

    async def send_interactive_buttons(
        self,
        phone: str,
        body: str,
        buttons: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send interactive buttons message.

        Args:
            phone: Recipient phone number.
            body: Message body.
            buttons: List of buttons with id and title.

        Returns:
            API response dict.
        """
        ...

    async def send_template(
        self,
        phone: str,
        template_name: str,
        parameters: list[str],
    ) -> dict[str, Any]:
        """Send a template message (HSM).

        Args:
            phone: Recipient phone number.
            template_name: Template name.
            parameters: Template parameters.

        Returns:
            API response dict.
        """
        ...

    async def close(self) -> None:
        """Close the notification service and release resources."""
        ...

    async def send_appointment_reminder(
        self,
        appointment: "Appointment",
        patient: "Patient",
        days_before: int = 1,
        special_instructions: str | None = None,
    ) -> dict[str, Any]:
        """Send appointment reminder via WhatsApp HSM template.

        Args:
            appointment: Appointment entity with details.
            patient: Patient entity with contact info.
            days_before: Days until appointment (for message text).
            special_instructions: Additional instructions.

        Returns:
            API response dict.
        """
        ...
