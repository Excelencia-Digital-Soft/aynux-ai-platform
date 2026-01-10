# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for cancelling a medical appointment.
# ============================================================================
"""Cancel Appointment Use Case.

Handles the cancellation of existing medical appointments.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import CancelAppointmentRequest, UseCaseResult

if TYPE_CHECKING:
    from ..ports import IAppointmentManager

logger = logging.getLogger(__name__)


class CancelAppointmentUseCase:
    """Use case for cancelling an appointment.

    Cancels an existing appointment in the external medical system.
    """

    def __init__(self, appointment_manager: "IAppointmentManager") -> None:
        """Initialize use case.

        Args:
            appointment_manager: Appointment management interface (DIP).
        """
        self._appointments = appointment_manager

    async def execute(self, request: CancelAppointmentRequest) -> UseCaseResult:
        """Execute the cancel appointment use case.

        Args:
            request: Cancellation request with appointment ID and reason.

        Returns:
            UseCaseResult indicating success or failure.
        """
        logger.info(f"Cancelling appointment {request.appointment_id}")

        response = await self._appointments.cancelar_turno(
            id_turno=request.appointment_id,
            motivo=request.reason,
        )

        if not response.success:
            logger.warning(f"Failed to cancel appointment: {response.error_code} - {response.error_message}")
            return UseCaseResult.error(
                code=response.error_code or "CANCELLATION_ERROR",
                message=response.error_message or "Error al cancelar el turno",
            )

        logger.info(f"Appointment {request.appointment_id} cancelled successfully")

        return UseCaseResult.ok(
            data={
                "appointment_id": request.appointment_id,
                "status": "cancelled",
                "reason": request.reason,
            }
        )
