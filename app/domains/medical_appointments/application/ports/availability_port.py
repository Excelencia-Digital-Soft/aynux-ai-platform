# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Availability checking port (ISP compliant).
# ============================================================================
"""Availability Checking Port.

Defines the interface for checking available specialties, providers,
dates, and time slots.
Part of the segregated interface design (ISP).
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .response import ExternalResponse


@runtime_checkable
class IAvailabilityChecker(Protocol):
    """Interface for availability checking operations.

    Implementations: HCWebSOAPClient, MercedarioRESTClient

    This is a segregated interface (ISP) for clients that only need
    to check availability without managing appointments.
    """

    async def obtener_especialidades(self) -> "ExternalResponse":
        """Get list of available specialties.

        Returns:
            ExternalResponse with list of specialties or error.
        """
        ...

    async def obtener_especialidades_bot(self) -> "ExternalResponse":
        """Get list of specialties configured for bot.

        Returns:
            ExternalResponse with list of specialties or error.
        """
        ...

    async def obtener_prestadores(self, id_especialidad: str) -> "ExternalResponse":
        """Get providers for a specialty.

        Args:
            id_especialidad: Specialty ID.

        Returns:
            ExternalResponse with list of providers or error.
        """
        ...

    async def obtener_dias_disponibles(
        self,
        id_prestador: str,
        id_especialidad: str,
    ) -> "ExternalResponse":
        """Get available dates for a provider.

        Args:
            id_prestador: Provider ID.
            id_especialidad: Specialty ID.

        Returns:
            ExternalResponse with list of available dates or error.
        """
        ...

    async def obtener_horarios_disponibles(
        self,
        id_prestador: str,
        fecha: str,
    ) -> "ExternalResponse":
        """Get available time slots for a provider on a date.

        Args:
            id_prestador: Provider ID.
            fecha: Date string.

        Returns:
            ExternalResponse with list of available times or error.
        """
        ...

    async def get_proximo_turno_disponible(
        self,
        id_prestador: str,
    ) -> "ExternalResponse":
        """Get the next available appointment slot for a provider.

        Args:
            id_prestador: Provider ID.

        Returns:
            ExternalResponse with next available slot or error.
        """
        ...

    async def get_proximo_turno_disponible_especialidad(
        self,
        id_especialidad: str,
    ) -> "ExternalResponse":
        """Get the next available slot for any provider in a specialty.

        Args:
            id_especialidad: Specialty ID.

        Returns:
            ExternalResponse with next available slot or error.
        """
        ...

    async def obtener_especialidades_con_prestadores(self) -> "ExternalResponse":
        """Get specialties with their associated providers.

        Returns:
            ExternalResponse with specialties and providers data or error.
        """
        ...

    async def get_fechas_disponibles_prestador(
        self,
        id_prestador: str,
    ) -> "ExternalResponse":
        """Get available dates for a provider.

        Args:
            id_prestador: Provider ID.

        Returns:
            ExternalResponse with list of available dates or error.
        """
        ...

    async def obtener_dias_turno(self, id_turno: str) -> "ExternalResponse":
        """Get available dates for rescheduling an appointment.

        Args:
            id_turno: Appointment ID.

        Returns:
            ExternalResponse with list of available dates or error.
        """
        ...

    async def obtener_horas_turno(
        self,
        id_turno: str,
        fecha: str,
    ) -> "ExternalResponse":
        """Get available times for a specific date when rescheduling.

        Args:
            id_turno: Appointment ID.
            fecha: Date string.

        Returns:
            ExternalResponse with list of available times or error.
        """
        ...
