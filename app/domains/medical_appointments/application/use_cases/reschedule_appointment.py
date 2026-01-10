# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for rescheduling a medical appointment.
# ============================================================================
"""Reschedule Appointment Use Case.

Handles the rescheduling of existing medical appointments.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import (
    AvailableDateDTO,
    AvailableSlotDTO,
    GetAvailableSlotsResult,
    RescheduleAppointmentRequest,
    UseCaseResult,
)

if TYPE_CHECKING:
    from ..ports import IMedicalSystemClient

logger = logging.getLogger(__name__)


class RescheduleAppointmentUseCase:
    """Use case for rescheduling an appointment.

    Reschedules an existing appointment to a new date/time.
    """

    def __init__(self, medical_client: "IMedicalSystemClient") -> None:
        """Initialize use case.

        Args:
            medical_client: Medical system client interface (DIP).
        """
        self._client = medical_client

    async def execute(self, request: RescheduleAppointmentRequest) -> UseCaseResult:
        """Execute the reschedule appointment use case.

        Args:
            request: Reschedule request with new date/time.

        Returns:
            UseCaseResult indicating success or failure.
        """
        logger.info(f"Rescheduling appointment {request.appointment_id} " f"to {request.new_date} {request.new_time}")

        # Format datetime for SOAP API
        fecha_hora = f"{request.new_date.isoformat()} " f"{request.new_time.strftime('%H:%M')}"

        response = await self._client.reprogramar_turno(
            id_turno=request.appointment_id,
            fecha_hora=fecha_hora,
            frecuencia=str(request.frequency),
        )

        if not response.success:
            logger.warning(f"Failed to reschedule appointment: {response.error_code} - {response.error_message}")
            return UseCaseResult.error(
                code=response.error_code or "RESCHEDULE_ERROR",
                message=response.error_message or "Error al reprogramar el turno",
            )

        logger.info(f"Appointment {request.appointment_id} rescheduled successfully")

        return UseCaseResult.ok(
            data={
                "appointment_id": request.appointment_id,
                "new_date": request.new_date.strftime("%d/%m/%Y"),
                "new_time": request.new_time.strftime("%H:%M"),
                "status": "rescheduled",
            }
        )

    async def get_available_dates(self, appointment_id: str) -> GetAvailableSlotsResult:
        """Get available dates for rescheduling an appointment.

        Args:
            appointment_id: ID of the appointment to reschedule.

        Returns:
            GetAvailableSlotsResult with available dates.
        """
        logger.info(f"Getting available dates for appointment {appointment_id}")

        response = await self._client.obtener_dias_turno(id_turno=appointment_id)

        if not response.success:
            return GetAvailableSlotsResult(
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
            )

        # Parse dates from response
        dates: list[AvailableDateDTO] = []
        if response.data:
            raw_dates = response.data if isinstance(response.data, list) else [response.data]
            for date_str in raw_dates:
                if isinstance(date_str, str):
                    dates.append(AvailableDateDTO(date=date_str))

        return GetAvailableSlotsResult(success=True, dates=dates)

    async def get_available_times(self, appointment_id: str, date: str) -> GetAvailableSlotsResult:
        """Get available times for a specific date.

        Args:
            appointment_id: ID of the appointment to reschedule.
            date: Selected date (dd/mm/yyyy format).

        Returns:
            GetAvailableSlotsResult with available time slots.
        """
        logger.info(f"Getting available times for {date}")

        response = await self._client.obtener_horas_turno(
            id_turno=appointment_id,
            fecha=date,
        )

        if not response.success:
            return GetAvailableSlotsResult(
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
            )

        # Parse times from response
        slots: list[AvailableSlotDTO] = []
        if response.data:
            raw_times = response.data if isinstance(response.data, list) else [response.data]
            for time_str in raw_times:
                if isinstance(time_str, str):
                    slots.append(AvailableSlotDTO(date=date, time=time_str))

        return GetAvailableSlotsResult(success=True, slots=slots)
