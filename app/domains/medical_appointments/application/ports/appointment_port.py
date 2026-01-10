# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Appointment management port (ISP compliant).
# ============================================================================
"""Appointment Management Port.

Defines the interface for appointment-related operations.
Part of the segregated interface design (ISP).
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .response import ExternalResponse


@runtime_checkable
class IAppointmentManager(Protocol):
    """Interface for appointment management operations.

    Implementations: HCWebSOAPClient, MercedarioRESTClient

    This is a segregated interface (ISP) for clients that only need
    appointment CRUD functionality.
    """

    async def crear_turno(
        self,
        id_paciente: str,
        id_prestador: str,
        fecha_hora: str,
    ) -> "ExternalResponse":
        """Create a new appointment.

        Args:
            id_paciente: Patient ID.
            id_prestador: Provider ID.
            fecha_hora: Appointment date and time (format varies by system).

        Returns:
            ExternalResponse with appointment ID or error.
        """
        ...

    async def confirmar_turno(self, id_turno: str) -> "ExternalResponse":
        """Confirm an existing appointment.

        Args:
            id_turno: Appointment ID.

        Returns:
            ExternalResponse with success or error.
        """
        ...

    async def cancelar_turno(
        self,
        id_turno: str,
        motivo: str = "",
    ) -> "ExternalResponse":
        """Cancel an existing appointment.

        Args:
            id_turno: Appointment ID.
            motivo: Cancellation reason (optional).

        Returns:
            ExternalResponse with success or error.
        """
        ...

    async def reprogramar_turno(
        self,
        id_turno: str,
        fecha_hora: str,
        frecuencia: str = "",
    ) -> "ExternalResponse":
        """Reschedule an appointment to a new date/time.

        Args:
            id_turno: Appointment ID.
            fecha_hora: New date and time.
            frecuencia: Appointment frequency (optional).

        Returns:
            ExternalResponse with success or error.
        """
        ...

    async def obtener_turnos_paciente(
        self,
        id_paciente: str,
    ) -> "ExternalResponse":
        """Get all appointments for a patient.

        Args:
            id_paciente: Patient ID.

        Returns:
            ExternalResponse with list of appointments or error.
        """
        ...

    async def obtener_turno_sugerido(self, dni: str) -> "ExternalResponse":
        """Get suggested appointment for a patient.

        Args:
            dni: Patient's DNI.

        Returns:
            ExternalResponse with suggested appointment or error.
        """
        ...

    async def crear_turno_whatsapp(
        self,
        id_paciente: str,
        id_prestador: str,
        fecha_hora: str,
        especialidad: str = "",
        celular: str = "",
        frecuencia: str = "",
    ) -> "ExternalResponse":
        """Create appointment via WhatsApp bot integration.

        Args:
            id_paciente: Patient ID.
            id_prestador: Provider ID.
            fecha_hora: Appointment date and time.
            especialidad: Specialty code (optional).
            celular: Patient phone (optional).
            frecuencia: Appointment frequency (optional).

        Returns:
            ExternalResponse with appointment details or error.
        """
        ...
