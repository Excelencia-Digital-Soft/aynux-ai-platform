# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Reminder management port (ISP compliant).
# ============================================================================
"""Reminder Management Port.

Defines the interface for reminder-related operations.
Part of the segregated interface design (ISP).
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .response import ExternalResponse


@runtime_checkable
class IReminderManager(Protocol):
    """Interface for reminder management operations.

    Implementations: HCWebSOAPClient, MercedarioRESTClient

    This is a segregated interface (ISP) for clients that only need
    reminder-related functionality.
    """

    async def obtener_turnos_hoy(self) -> "ExternalResponse":
        """Get today's appointments for sending reminders.

        Returns:
            ExternalResponse with list of appointments or error.
        """
        ...

    async def obtener_turnos_manana(self) -> "ExternalResponse":
        """Get tomorrow's appointments for sending reminders.

        Returns:
            ExternalResponse with list of appointments or error.
        """
        ...

    async def obtener_turnos_para_recordatorio(
        self,
        dias_anticipacion: int = 1,
    ) -> "ExternalResponse":
        """Get appointments that need reminders.

        Args:
            dias_anticipacion: Days before appointment to send reminder.

        Returns:
            ExternalResponse with list of appointments or error.
        """
        ...

    async def marcar_recordatorio_enviado(
        self,
        id_turno: str,
    ) -> "ExternalResponse":
        """Mark that a reminder was sent for an appointment.

        Args:
            id_turno: Appointment ID.

        Returns:
            ExternalResponse with success or error.
        """
        ...

    async def actualizar_turnos_recordatorio_enviado(
        self,
        id_turnos: list[int],
        es_turno_semanal: bool = False,
    ) -> "ExternalResponse":
        """Mark multiple appointments as reminder sent.

        Args:
            id_turnos: List of appointment IDs.
            es_turno_semanal: Whether this is a weekly reminder.

        Returns:
            ExternalResponse with success or error.
        """
        ...
