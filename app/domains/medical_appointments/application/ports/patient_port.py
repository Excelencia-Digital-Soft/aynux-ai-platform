# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Patient management port (ISP compliant).
# ============================================================================
"""Patient Management Port.

Defines the interface for patient-related operations in medical systems.
Part of the segregated interface design (ISP).
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .response import ExternalResponse


@runtime_checkable
class IPatientManager(Protocol):
    """Interface for patient management operations.

    Implementations: HCWebSOAPClient, MercedarioRESTClient

    This is a segregated interface (ISP) for clients that only need
    patient-related functionality.
    """

    async def buscar_paciente_dni(self, dni: str) -> "ExternalResponse":
        """Search patient by DNI (national ID).

        Args:
            dni: Patient's DNI number (7-8 digits).

        Returns:
            ExternalResponse with patient data or error.
        """
        ...

    async def buscar_paciente_celular(self, celular: str) -> "ExternalResponse":
        """Search patient by phone number.

        Args:
            celular: Patient's phone number.

        Returns:
            ExternalResponse with patient data or error.
        """
        ...

    async def registrar_paciente(
        self,
        dni: str,
        nombre: str,
        apellido: str,
        telefono: str,
        email: str = "",
        obra_social: str = "",
    ) -> "ExternalResponse":
        """Register a new patient.

        Args:
            dni: Patient's DNI number.
            nombre: First name.
            apellido: Last name.
            telefono: Phone number.
            email: Email address (optional).
            obra_social: Health insurance (optional).

        Returns:
            ExternalResponse with new patient ID or error.
        """
        ...

    async def actualizar_verificacion_whatsapp(
        self,
        id_paciente: str,
        verificado: bool = True,
    ) -> "ExternalResponse":
        """Update patient's WhatsApp verification status.

        Args:
            id_paciente: Patient ID.
            verificado: Verification status.

        Returns:
            ExternalResponse with success or error.
        """
        ...
