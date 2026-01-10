# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use case for sending appointment reminders.
# ============================================================================
"""Send Reminder Use Case.

Handles the sending of appointment reminders via WhatsApp.
"""

import logging
from typing import TYPE_CHECKING

from ..dto.appointment_dtos import SendReminderRequest, SendReminderResult

if TYPE_CHECKING:
    from ..ports import INotificationService, IReminderManager

logger = logging.getLogger(__name__)


class SendReminderUseCase:
    """Use case for sending appointment reminders.

    Retrieves appointments that need reminders and sends them
    via WhatsApp using the notification service.
    """

    def __init__(
        self,
        reminder_manager: "IReminderManager",
        notification_service: "INotificationService | None" = None,
    ) -> None:
        """Initialize use case.

        Args:
            reminder_manager: Reminder management interface (DIP).
            notification_service: Notification service interface (DIP).
        """
        self._client = reminder_manager
        self._notification_service = notification_service

    async def execute(self, request: SendReminderRequest) -> SendReminderResult:
        """Execute the send reminder use case.

        Args:
            request: Request with days_before parameter.

        Returns:
            SendReminderResult with counts of sent/failed reminders.
        """
        logger.info(f"Sending reminders for appointments in {request.days_before} day(s)")

        # Get appointments that need reminders
        response = await self._client.obtener_turnos_para_recordatorio(
            dias_anticipacion=request.days_before,
        )

        if not response.success:
            return SendReminderResult(
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
            )

        if not response.data:
            logger.info("No appointments found for reminders")
            return SendReminderResult(success=True, sent_count=0)

        # Parse appointments
        appointments = response.data if isinstance(response.data, list) else [response.data]

        sent_count = 0
        failed_count = 0
        sent_ids: list[str] = []

        for appointment in appointments:
            if not isinstance(appointment, dict):
                continue

            appointment_id = str(appointment.get("idTurno") or appointment.get("id") or "")
            patient_phone = appointment.get("celular") or appointment.get("telefono") or ""
            patient_name = appointment.get("paciente") or appointment.get("nombrePaciente") or ""

            if not patient_phone:
                logger.warning(f"No phone for appointment {appointment_id}, skipping")
                failed_count += 1
                continue

            try:
                if self._notification_service:
                    # Use notification service if available
                    await self._send_via_notification_service(
                        appointment=appointment,
                        days_before=request.days_before,
                    )
                    sent_count += 1
                    sent_ids.append(appointment_id)
                else:
                    # Just log if no notification service
                    logger.info(
                        f"Would send reminder to {patient_name} ({patient_phone}) " f"for appointment {appointment_id}"
                    )
                    sent_count += 1
                    sent_ids.append(appointment_id)

            except Exception as e:
                logger.error(f"Failed to send reminder for {appointment_id}: {e}")
                failed_count += 1

        # Mark reminders as sent in external system
        if sent_ids:
            is_weekly = request.days_before == 7
            await self._mark_reminders_sent(sent_ids, is_weekly)

        logger.info(f"Reminders completed: {sent_count} sent, {failed_count} failed")

        return SendReminderResult(
            success=True,
            sent_count=sent_count,
            failed_count=failed_count,
            appointment_ids=sent_ids,
        )

    async def _send_via_notification_service(
        self,
        appointment: dict,
        days_before: int,
    ) -> None:
        """Send reminder using notification service."""
        if not self._notification_service:
            return

        # Import here to avoid circular imports
        from ...domain.entities.appointment import Appointment
        from ...domain.entities.patient import Patient

        # Create minimal entities for notification
        apt = Appointment()
        apt.external_id = str(appointment.get("idTurno") or "")
        apt.provider_name = appointment.get("prestador") or ""

        # Parse date/time from appointment data
        fecha = appointment.get("fecha") or ""
        hora = appointment.get("hora") or ""

        if fecha:
            try:
                from datetime import datetime

                if "/" in fecha:
                    apt.appointment_date = datetime.strptime(fecha, "%d/%m/%Y").date()
                else:
                    apt.appointment_date = datetime.strptime(fecha, "%Y-%m-%d").date()
            except ValueError:
                pass

        if hora:
            try:
                from datetime import datetime

                apt.start_time = datetime.strptime(hora, "%H:%M").time()
            except ValueError:
                pass

        patient = Patient()
        patient.phone = appointment.get("celular") or appointment.get("telefono") or ""
        patient.full_name = appointment.get("paciente") or ""

        await self._notification_service.send_appointment_reminder(
            appointment=apt,
            patient=patient,
            days_before=days_before,
        )

    async def _mark_reminders_sent(
        self,
        appointment_ids: list[str],
        is_weekly: bool,
    ) -> None:
        """Mark reminders as sent in the external system."""
        try:
            int_ids = [int(id_) for id_ in appointment_ids if id_.isdigit()]
            if int_ids:
                await self._client.actualizar_turnos_recordatorio_enviado(
                    id_turnos=int_ids,
                    es_turno_semanal=is_weekly,
                )
                logger.info(f"Marked {len(int_ids)} appointments as reminder sent")
        except Exception as e:
            logger.warning(f"Failed to mark reminders as sent: {e}")

    async def get_appointments_for_reminder(self, days_before: int) -> SendReminderResult:
        """Get appointments that need reminders without sending.

        Args:
            days_before: Days until appointment.

        Returns:
            SendReminderResult with appointment count.
        """
        response = await self._client.obtener_turnos_para_recordatorio(
            dias_anticipacion=days_before,
        )

        if not response.success:
            return SendReminderResult(
                success=False,
                error_code=response.error_code,
                error_message=response.error_message,
            )

        appointments = response.data if isinstance(response.data, list) else []
        ids = [str(a.get("idTurno") or a.get("id") or "") for a in appointments if isinstance(a, dict)]

        return SendReminderResult(
            success=True,
            sent_count=len(ids),
            appointment_ids=ids,
        )
