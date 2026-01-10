# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for confirming a medical appointment.
# ============================================================================
"""Confirm Appointment Use Case.

Handles the confirmation of pending medical appointments.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import ConfirmAppointmentRequest, UseCaseResult

if TYPE_CHECKING:
    from ..ports import IAppointmentManager

logger = logging.getLogger(__name__)


class ConfirmAppointmentUseCase:
    """Use case for confirming an appointment.

    Confirms a pending appointment in the external medical system.
    """

    def __init__(self, appointment_manager: "IAppointmentManager") -> None:
        """Initialize use case.

        Args:
            appointment_manager: Appointment management interface (DIP).
        """
        self._appointments = appointment_manager

    async def execute(self, request: ConfirmAppointmentRequest) -> UseCaseResult:
        """Execute the confirm appointment use case.

        Args:
            request: Confirmation request with appointment ID.

        Returns:
            UseCaseResult indicating success or failure.
        """
        logger.info(f"Confirming appointment {request.appointment_id}")

        response = await self._appointments.confirmar_turno(
            id_turno=request.appointment_id,
        )

        if not response.success:
            logger.warning(f"Failed to confirm appointment: {response.error_code} - {response.error_message}")
            return UseCaseResult.error(
                code=response.error_code or "CONFIRMATION_ERROR",
                message=response.error_message or "Error al confirmar el turno",
            )

        logger.info(f"Appointment {request.appointment_id} confirmed successfully")

        return UseCaseResult.ok(
            data={
                "appointment_id": request.appointment_id,
                "status": "confirmed",
            }
        )
