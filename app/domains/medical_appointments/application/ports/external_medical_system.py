# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: External Medical System Port - Combined interface.
# ============================================================================
"""External Medical System Port.

Defines the combined interface for interacting with external medical systems
like HCWeb (SOAP) and Mercedario (REST).
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .appointment_port import IAppointmentManager
from .availability_port import IAvailabilityChecker
from .patient_port import IPatientManager
from .reminder_port import IReminderManager
from .response import ExternalResponse

if TYPE_CHECKING:
    pass

# Re-export ExternalResponse for backward compatibility
__all__ = ["ExternalResponse", "IMedicalSystemClient"]


@runtime_checkable
class IMedicalSystemClient(
    IPatientManager,
    IAppointmentManager,
    IAvailabilityChecker,
    IReminderManager,
    Protocol,
):
    """Combined interface for medical system clients.

    This interface inherits from all segregated interfaces:
    - IPatientManager: Patient CRUD operations
    - IAppointmentManager: Appointment CRUD operations
    - IAvailabilityChecker: Availability queries
    - IReminderManager: Reminder operations

    Implementations: HCWebSOAPClient, MercedarioRESTClient

    Use segregated interfaces when only a subset of functionality is needed.
    Use this combined interface for components that need full access.
    """

    institution_id: str
    """The institution ID for this client."""

    async def close(self) -> None:
        """Close connections and release resources."""
        ...

    async def obtener_informacion_institucion(self) -> "ExternalResponse":
        """Get institution information.

        Returns:
            ExternalResponse with institution data or error.
        """
        ...

    async def obtener_instituciones_activas(self) -> "ExternalResponse":
        """Get list of active institutions.

        Returns:
            ExternalResponse with list of institutions or error.
        """
        ...
