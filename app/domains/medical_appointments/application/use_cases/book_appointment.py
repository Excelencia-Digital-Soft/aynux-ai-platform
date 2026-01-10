# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for booking a new medical appointment.
# ============================================================================
"""Book Appointment Use Case.

Handles the creation of new medical appointments through the external
medical system (HCWeb SOAP API).
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import (
    AppointmentDTO,
    BookAppointmentRequest,
    BookAppointmentResult,
)
from ..utils import ExternalFieldMapper, ResponseExtractor

if TYPE_CHECKING:
    from ..ports import IMedicalSystemClient

logger = logging.getLogger(__name__)


class BookAppointmentUseCase:
    """Use case for booking a new appointment.

    Creates an appointment in the external medical system and returns
    the booking details.
    """

    def __init__(self, medical_client: "IMedicalSystemClient") -> None:
        """Initialize use case.

        Args:
            medical_client: Medical system client interface (DIP).
        """
        self._client = medical_client

    async def execute(self, request: BookAppointmentRequest) -> BookAppointmentResult:
        """Execute the book appointment use case.

        Args:
            request: Booking request with patient and appointment details.

        Returns:
            BookAppointmentResult with created appointment or error.
        """
        logger.info(
            f"Booking appointment for patient {request.patient_document} " f"with provider {request.provider_id}"
        )

        # Format datetime for SOAP API
        fecha_hora = f"{request.appointment_date.isoformat()} " f"{request.appointment_time.strftime('%H:%M')}"

        # Call external system
        response = await self._client.crear_turno_whatsapp(
            id_paciente=request.patient_id,
            id_prestador=request.provider_id,
            fecha_hora=fecha_hora,
            especialidad=request.specialty_code,
            celular=request.patient_phone,
            frecuencia=str(request.frequency),
        )

        if not response.success:
            logger.warning(f"Failed to book appointment: {response.error_code} - {response.error_message}")
            return BookAppointmentResult(
                success=False,
                error_code=response.error_code or "BOOKING_ERROR",
                error_message=response.error_message or "Error al crear el turno",
            )

        # Build appointment DTO from response using ResponseExtractor
        appointment_data = ResponseExtractor.as_dict(response.data)
        appointment_id = ExternalFieldMapper.get_appointment_id(appointment_data)

        appointment = AppointmentDTO(
            id=appointment_id,
            external_id=appointment_data.get("idTurno"),
            patient_document=request.patient_document,
            patient_name=request.patient_name,
            provider_id=request.provider_id,
            provider_name=ResponseExtractor.get_field(appointment_data, "prestador", "nombrePrestador"),
            specialty_code=request.specialty_code,
            specialty_name=ResponseExtractor.get_field(appointment_data, "especialidad", "nombreEspecialidad"),
            appointment_date=request.appointment_date.strftime("%d/%m/%Y"),
            appointment_time=request.appointment_time.strftime("%H:%M"),
            status="pending",
            status_display="Pendiente",
            institution=self._client.institution_id,
        )

        logger.info(f"Appointment booked successfully: {appointment.id}")

        return BookAppointmentResult(
            success=True,
            data=appointment_data,
            appointment=appointment,
        )
