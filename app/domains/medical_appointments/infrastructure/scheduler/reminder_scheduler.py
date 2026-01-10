"""Reminder Scheduler for Medical Appointments.

APScheduler-based async scheduler for sending appointment reminders.
Runs at 9:00 AM and 8:00 PM (Argentina/San_Juan timezone).
"""

import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-not-found]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-not-found]
from pytz import timezone

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler de recordatorios de turnos médicos.

    Sends WhatsApp reminders to patients:
    - 9:00 AM: Reminders for today's appointments
    - 8:00 PM: Reminders for tomorrow's appointments
    """

    def __init__(
        self,
        soap_url: str = "",
        institution_id: str = "",
        timezone_name: str = "America/Argentina/San_Juan",
        enabled: bool = True,
    ):
        """Initialize scheduler.

        Args:
            soap_url: HCWeb SOAP service URL.
            institution_id: Institution ID for HCWeb.
            timezone_name: Timezone for scheduling jobs.
            enabled: Whether scheduler is enabled.
        """
        self.soap_url = soap_url
        self.institution_id = institution_id
        self.tz = timezone(timezone_name)
        self.enabled = enabled

        self._scheduler: AsyncIOScheduler | None = None
        self._is_running = False

    async def start(self) -> None:
        """Start the scheduler."""
        if not self.enabled:
            logger.info("ReminderScheduler is disabled, skipping start")
            return

        if self._is_running:
            logger.warning("ReminderScheduler already running")
            return

        scheduler = AsyncIOScheduler()
        self._scheduler = scheduler

        # Morning reminders (9:00 AM) - for today's appointments
        scheduler.add_job(
            self._send_morning_reminders,
            CronTrigger(hour=9, minute=0, timezone=self.tz),
            id="morning_reminders",
            replace_existing=True,
            name="Morning Appointment Reminders",
        )

        # Evening reminders (8:00 PM) - for tomorrow's appointments
        scheduler.add_job(
            self._send_evening_reminders,
            CronTrigger(hour=20, minute=0, timezone=self.tz),
            id="evening_reminders",
            replace_existing=True,
            name="Evening Appointment Reminders",
        )

        scheduler.start()
        self._is_running = True
        logger.info(f"ReminderScheduler started with timezone {self.tz} " f"(morning=9:00, evening=20:00)")

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler and self._is_running:
            self._scheduler.shutdown(wait=True)
            self._is_running = False
            logger.info("ReminderScheduler stopped")

    async def _send_morning_reminders(self) -> None:
        """Send reminders for today's appointments."""
        logger.info("Starting morning reminder job")

        try:
            appointments = await self._fetch_todays_appointments()

            if not appointments:
                logger.info("No appointments found for today")
                return

            logger.info(f"Found {len(appointments)} appointments for today")

            for appointment in appointments:
                await self._send_reminder(appointment, reminder_type="today")
                # Rate limiting
                await asyncio.sleep(0.5)

            logger.info(f"Sent {len(appointments)} morning reminders")

        except Exception as e:
            logger.error(f"Error sending morning reminders: {e}", exc_info=True)

    async def _send_evening_reminders(self) -> None:
        """Send reminders for tomorrow's appointments."""
        logger.info("Starting evening reminder job")

        try:
            appointments = await self._fetch_tomorrows_appointments()

            if not appointments:
                logger.info("No appointments found for tomorrow")
                return

            logger.info(f"Found {len(appointments)} appointments for tomorrow")

            for appointment in appointments:
                await self._send_reminder(appointment, reminder_type="tomorrow")
                # Rate limiting
                await asyncio.sleep(0.5)

            logger.info(f"Sent {len(appointments)} evening reminders")

        except Exception as e:
            logger.error(f"Error sending evening reminders: {e}", exc_info=True)

    async def _fetch_todays_appointments(self) -> list[dict[str, Any]]:
        """Fetch today's appointments from HCWeb."""
        from ..external import HCWebSOAPClient

        if not self.soap_url:
            logger.warning("SOAP URL not configured, skipping fetch")
            return []

        soap = HCWebSOAPClient(
            base_url=self.soap_url,
            institution_id=self.institution_id,
        )

        try:
            response = await soap.obtener_turnos_hoy()

            if not response.success:
                logger.warning(f"Failed to fetch today's appointments: {response.error_message}")
                return []

            raw_data = response.data
            turnos: list = []
            if isinstance(raw_data, dict):
                turnos = raw_data.get("turnos", [])
            elif isinstance(raw_data, list):
                turnos = raw_data
            if isinstance(turnos, dict):
                turnos = [turnos]

            return turnos

        finally:
            await soap.close()

    async def _fetch_tomorrows_appointments(self) -> list[dict[str, Any]]:
        """Fetch tomorrow's appointments from HCWeb."""
        from ..external import HCWebSOAPClient

        if not self.soap_url:
            logger.warning("SOAP URL not configured, skipping fetch")
            return []

        soap = HCWebSOAPClient(
            base_url=self.soap_url,
            institution_id=self.institution_id,
        )

        try:
            response = await soap.obtener_turnos_manana()

            if not response.success:
                logger.warning(f"Failed to fetch tomorrow's appointments: {response.error_message}")
                return []

            raw_data = response.data
            turnos: list = []
            if isinstance(raw_data, dict):
                turnos = raw_data.get("turnos", [])
            elif isinstance(raw_data, list):
                turnos = raw_data
            if isinstance(turnos, dict):
                turnos = [turnos]

            return turnos

        finally:
            await soap.close()

    async def _send_reminder(self, appointment: dict[str, Any], reminder_type: str) -> None:
        """Send reminder to patient via WhatsApp.

        Args:
            appointment: Appointment data from HCWeb.
            reminder_type: "today" or "tomorrow".
        """
        phone = appointment.get("telefono") or appointment.get("celular")
        patient_name = appointment.get("paciente") or appointment.get("nombrePaciente")
        fecha = appointment.get("fecha")
        hora = appointment.get("hora")
        prestador = appointment.get("prestador") or appointment.get("nombrePrestador")
        id_turno = appointment.get("idTurno")

        if not phone:
            logger.warning(f"No phone number for appointment {id_turno}, skipping")
            return

        # Format message
        if reminder_type == "today":
            message = (
                f"👋 ¡Hola {patient_name}!\n\n"
                f"Te recordamos que hoy tenés turno:\n\n"
                f"📅 Fecha: {fecha}\n"
                f"🕐 Hora: {hora}\n"
                f"👨‍⚕️ Prestador: {prestador}\n\n"
                f"¡Te esperamos!"
            )
        else:
            message = (
                f"👋 ¡Hola {patient_name}!\n\n"
                f"Te recordamos que mañana tenés turno:\n\n"
                f"📅 Fecha: {fecha}\n"
                f"🕐 Hora: {hora}\n"
                f"👨‍⚕️ Prestador: {prestador}\n\n"
                f"Respondé *CONFIRMAR* para confirmar o *CANCELAR* para cancelar."
            )

        # Send via WhatsApp
        try:
            await self._send_whatsapp_message(phone, message)
            logger.debug(f"Reminder sent to {phone} for appointment {id_turno}")
        except Exception as e:
            logger.error(f"Failed to send reminder to {phone}: {e}")

    async def _send_whatsapp_message(self, phone: str, message: str) -> None:
        """Send WhatsApp message via Chattigo integration.

        Args:
            phone: Recipient phone number.
            message: Message text.
        """
        # Import here to avoid circular imports
        try:
            from app.integrations.whatsapp import WhatsAppClient  # type: ignore[attr-defined]

            # Normalize phone number
            normalized_phone = "".join(c for c in phone if c.isdigit())
            if not normalized_phone.startswith("54"):
                normalized_phone = "54" + normalized_phone

            # Get WhatsApp client and send
            client = WhatsAppClient()
            await client.send_text_message(
                to=normalized_phone,
                message=message,
            )

        except ImportError:
            logger.warning("WhatsApp integration not available, message not sent")
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            raise

    async def trigger_manual_reminders(self, reminder_type: str = "today") -> int:
        """Manually trigger reminders (for testing/admin).

        Args:
            reminder_type: "today" or "tomorrow".

        Returns:
            Number of reminders sent.
        """
        if reminder_type == "today":
            appointments = await self._fetch_todays_appointments()
        else:
            appointments = await self._fetch_tomorrows_appointments()

        count = 0
        for appointment in appointments:
            try:
                await self._send_reminder(appointment, reminder_type)
                count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Error sending reminder: {e}")

        return count

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    def get_jobs_info(self) -> list[dict[str, Any]]:
        """Get information about scheduled jobs."""
        if not self._scheduler:
            return []

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
            )
        return jobs


# Singleton instance
_scheduler_instance: ReminderScheduler | None = None


def get_reminder_scheduler(
    soap_url: str = "",
    institution_id: str = "",
    timezone_name: str = "America/Argentina/San_Juan",
    enabled: bool = True,
) -> ReminderScheduler:
    """Get or create the singleton scheduler instance.

    Args:
        soap_url: HCWeb SOAP service URL.
        institution_id: Institution ID for HCWeb.
        timezone_name: Timezone for scheduling.
        enabled: Whether scheduler is enabled.

    Returns:
        ReminderScheduler singleton instance.
    """
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = ReminderScheduler(
            soap_url=soap_url,
            institution_id=institution_id,
            timezone_name=timezone_name,
            enabled=enabled,
        )

    return _scheduler_instance


async def shutdown_scheduler() -> None:
    """Shutdown the scheduler singleton."""
    global _scheduler_instance

    if _scheduler_instance:
        await _scheduler_instance.stop()
        _scheduler_instance = None
