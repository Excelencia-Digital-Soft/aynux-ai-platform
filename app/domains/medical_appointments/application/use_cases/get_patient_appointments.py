# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for getting patient's appointments.
# ============================================================================
"""Get Patient Appointments Use Case.

Handles retrieval of a patient's existing appointments.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import (
    AppointmentDTO,
    GetPatientAppointmentsRequest,
    GetPatientAppointmentsResult,
    UseCaseResult,
)
from ..utils import ExternalFieldMapper, ResponseExtractor

if TYPE_CHECKING:
    from ..ports import IMedicalSystemClient

logger = logging.getLogger(__name__)


class GetPatientAppointmentsUseCase:
    """Use case for getting a patient's appointments.

    Retrieves all appointments for a patient from the external system.
    """

    def __init__(self, medical_client: "IMedicalSystemClient") -> None:
        """Initialize use case.

        Args:
            medical_client: Medical system client interface (DIP).
        """
        self._client = medical_client

    async def execute(self, request: GetPatientAppointmentsRequest) -> GetPatientAppointmentsResult:
        """Execute the get patient appointments use case.

        Args:
            request: Request with patient ID or document.

        Returns:
            GetPatientAppointmentsResult with appointments list.
        """
        patient_id = request.patient_id

        # If no patient_id, try to find by document
        if not patient_id and request.patient_document:
            patient_result = await self._find_patient_id(request.patient_document)
            if not patient_result.success:
                return GetPatientAppointmentsResult(
                    success=False,
                    error_code=patient_result.error_code,
                    error_message=patient_result.error_message,
                )
            patient_id = patient_result.data

        if not patient_id:
            return GetPatientAppointmentsResult(
                success=False,
                error_code="INVALID_REQUEST",
                error_message="Se requiere ID o documento del paciente",
            )

        logger.info(f"Getting appointments for patient {patient_id}")

        response = await self._client.obtener_turnos_paciente(id_paciente=patient_id)

        if not response.success:
            return GetPatientAppointmentsResult(
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
            )

        # Parse appointments from response using ResponseExtractor
        appointment_list = ResponseExtractor.as_list(response.data)
        appointments = [AppointmentDTO.from_external_data(item) for item in appointment_list]

        logger.info(f"Found {len(appointments)} appointments for patient {patient_id}")

        return GetPatientAppointmentsResult(
            success=True,
            appointments=appointments,
        )

    async def _find_patient_id(self, document: str) -> UseCaseResult:
        """Find patient ID by document number."""
        response = await self._client.buscar_paciente_dni(dni=document)

        if not response.success:
            return UseCaseResult.error(
                code="PATIENT_NOT_FOUND",
                message="Paciente no encontrado",
            )

        # Use ResponseExtractor for consistent parsing
        data = ResponseExtractor.as_dict(response.data)

        if not data:
            return UseCaseResult.error(
                code="PATIENT_NOT_FOUND",
                message="Paciente no encontrado",
            )

        # Use ExternalFieldMapper for consistent field access
        patient_id = ExternalFieldMapper.get_patient_id(data)
        if not patient_id:
            return UseCaseResult.error(
                code="PATIENT_NOT_FOUND",
                message="No se pudo obtener el ID del paciente",
            )

        return UseCaseResult.ok(data=patient_id)

    async def get_suggested_appointment(self, document: str) -> UseCaseResult:
        """Get suggested appointment for a patient.

        Args:
            document: Patient's document number.

        Returns:
            UseCaseResult with suggested appointment data.
        """
        logger.info(f"Getting suggested appointment for document {document}")

        response = await self._client.obtener_turno_sugerido(dni=document)

        if not response.success:
            return UseCaseResult.error(
                code=response.error_code or "NO_SUGGESTION",
                message=response.error_message or "No hay turno sugerido",
            )

        raw_data = response.data
        if not raw_data or not isinstance(raw_data, dict):
            return UseCaseResult.error(
                code="NO_SUGGESTION",
                message="No hay turno sugerido disponible",
            )

        appointment = AppointmentDTO.from_external_data(raw_data)
        return UseCaseResult.ok(data=appointment)
