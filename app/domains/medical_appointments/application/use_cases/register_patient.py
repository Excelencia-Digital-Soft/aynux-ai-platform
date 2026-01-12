# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for registering a new patient.
# ============================================================================
"""Register Patient Use Case.

Handles the registration of new patients in the external medical system.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import PatientDTO, RegisterPatientRequest, UseCaseResult
from ..utils import ExternalFieldMapper, ResponseExtractor

if TYPE_CHECKING:
    from ..ports import IPatientManager

logger = logging.getLogger(__name__)


class RegisterPatientUseCase:
    """Use case for registering a new patient.

    Registers a patient in the external medical system and optionally
    marks them as WhatsApp verified.
    """

    def __init__(self, patient_manager: "IPatientManager") -> None:
        """Initialize use case.

        Args:
            patient_manager: Patient management interface (DIP).
        """
        self._patients = patient_manager

    async def execute(
        self,
        request: RegisterPatientRequest,
        verify_whatsapp: bool = True,
    ) -> UseCaseResult:
        """Execute the register patient use case.

        Args:
            request: Registration request with patient details.
            verify_whatsapp: Whether to mark the patient as WhatsApp verified.

        Returns:
            UseCaseResult with registered patient data or error.
        """
        logger.info(f"Registering patient with document {request.document}")

        # Note: birth_date is available in request but not currently used by registrar_paciente
        response = await self._patients.registrar_paciente(
            dni=request.document,
            nombre=request.first_name,
            apellido=request.last_name,
            telefono=request.phone,
            email=request.email,
            obra_social=request.obra_social,
        )

        if not response.success:
            logger.warning(f"Failed to register patient: {response.error_code} - {response.error_message}")
            return UseCaseResult.error(
                code=response.error_code or "REGISTRATION_ERROR",
                message=response.error_message or "Error al registrar el paciente",
            )

        # Get patient ID from response using ResponseExtractor
        patient_data = ResponseExtractor.as_dict(response.data)
        patient_id = ExternalFieldMapper.get_patient_id(patient_data)

        # Optionally verify WhatsApp
        if verify_whatsapp and patient_id:
            await self._verify_whatsapp(patient_id)

        patient = PatientDTO(
            id=patient_id,
            external_id=patient_id,
            document=request.document,
            first_name=request.first_name,
            last_name=request.last_name,
            full_name=f"{request.first_name} {request.last_name}",
            phone=request.phone,
            email=request.email,
            obra_social=request.obra_social,
            is_registered=True,
            is_verified=verify_whatsapp,
        )

        logger.info(f"Patient {patient_id} registered successfully")

        return UseCaseResult.ok(data=patient)

    async def _verify_whatsapp(self, patient_id: str) -> bool:
        """Mark patient as WhatsApp verified.

        Args:
            patient_id: The patient ID to verify.

        Returns:
            True if verification succeeded, False otherwise.

        Note:
            Previously this method silently swallowed exceptions.
            Now it logs and returns False on failure for proper error handling.
        """
        try:
            response = await self._patients.actualizar_verificacion_whatsapp(
                id_paciente=patient_id,
                verificado=True,
            )
            if response.success:
                logger.info(f"Patient {patient_id} marked as WhatsApp verified")
                return True
            logger.warning(
                f"Failed to verify WhatsApp for patient {patient_id}: "
                f"{response.error_code} - {response.error_message}"
            )
            return False
        except Exception as e:
            logger.warning(
                f"Exception verifying WhatsApp for patient {patient_id}: {e}",
                exc_info=True,
            )
            return False

    async def find_by_document(self, document: str) -> UseCaseResult:
        """Find patient by document number.

        Args:
            document: Patient's document number (DNI).

        Returns:
            UseCaseResult with patient data or error.
        """
        logger.info(f"Searching patient by document {document}")

        response = await self._patients.buscar_paciente_dni(dni=document)

        if not response.success:
            return UseCaseResult.error(
                code=response.error_code or "PATIENT_NOT_FOUND",
                message=response.error_message or "Paciente no encontrado",
            )

        # HCWeb returns a list, get first item using ResponseExtractor
        patient_data = ResponseExtractor.as_dict(response.data)

        if not patient_data:
            return UseCaseResult.error(
                code="PATIENT_NOT_FOUND",
                message="Paciente no encontrado",
            )

        patient = PatientDTO.from_external_data(patient_data)
        return UseCaseResult.ok(data=patient)

    async def find_by_phone(self, phone: str) -> UseCaseResult:
        """Find patient by phone number.

        Args:
            phone: Patient's phone number.

        Returns:
            UseCaseResult with patient data or error.
        """
        logger.info(f"Searching patient by phone {phone}")

        response = await self._patients.buscar_paciente_celular(celular=phone)

        if not response.success:
            return UseCaseResult.error(
                code=response.error_code or "PATIENT_NOT_FOUND",
                message=response.error_message or "Paciente no encontrado",
            )

        # HCWeb returns a list, get first item using ResponseExtractor
        patient_data = ResponseExtractor.as_dict(response.data)

        if not patient_data:
            return UseCaseResult.error(
                code="PATIENT_NOT_FOUND",
                message="Paciente no encontrado",
            )

        patient = PatientDTO.from_external_data(patient_data)
        return UseCaseResult.ok(data=patient)
