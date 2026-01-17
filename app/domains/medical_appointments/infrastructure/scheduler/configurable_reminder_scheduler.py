# ============================================================================
# SCOPE: MULTI-TENANT WORKFLOW
# Description: Configurable reminder scheduler that loads schedules from database.
#              Supports per-institution reminder configurations.
# Tenant-Aware: Yes - schedules per institution_config_id.
# ============================================================================
"""Configurable Reminder Scheduler for Medical Appointments.

APScheduler-based async scheduler that loads reminder schedules from database.
Supports multiple institutions with independent reminder configurations.

Features:
- Dynamic schedule loading from database
- Per-institution timezone support
- Configurable message templates with placeholders
- Interactive WhatsApp buttons support
- Hot-reload capability for schedule changes
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-not-found]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-not-found]
from pytz import timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from app.models.db.tenancy import TenantInstitutionConfig
    from app.models.db.workflow import ReminderSchedule

logger = logging.getLogger(__name__)


class ConfigurableReminderScheduler:
    """Configurable scheduler for medical appointment reminders.

    Loads reminder schedules from database and dynamically creates
    APScheduler jobs for each institution's configured reminders.

    Attributes:
        _scheduler: APScheduler instance.
        _is_running: Whether scheduler is currently running.
        _db_session_factory: Async session factory for database access.
        _loaded_schedules: Cache of loaded schedule IDs.
    """

    def __init__(
        self,
        db_session_factory: Any,
        enabled: bool = True,
    ):
        """Initialize the configurable scheduler.

        Args:
            db_session_factory: Async SQLAlchemy session factory.
            enabled: Whether the scheduler is enabled.
        """
        self._db_session_factory = db_session_factory
        self._enabled = enabled
        self._scheduler: AsyncIOScheduler | None = None
        self._is_running = False
        self._loaded_schedules: set[str] = set()

    async def start(self) -> None:
        """Start the scheduler and load all schedules from database."""
        if not self._enabled:
            logger.info("ConfigurableReminderScheduler is disabled, skipping start")
            return

        if self._is_running:
            logger.warning("ConfigurableReminderScheduler already running")
            return

        scheduler = AsyncIOScheduler()
        scheduler.start()
        self._scheduler = scheduler
        self._is_running = True

        # Load all schedules from database
        await self._load_all_schedules()

        logger.info("ConfigurableReminderScheduler started")

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler and self._is_running:
            self._scheduler.shutdown(wait=True)
            self._is_running = False
            self._loaded_schedules.clear()
            logger.info("ConfigurableReminderScheduler stopped")

    async def reload_schedules(self) -> None:
        """Reload all schedules from database (hot-reload)."""
        if not self._scheduler or not self._is_running:
            logger.warning("Scheduler not running, cannot reload")
            return

        # Remove all existing jobs
        for job_id in list(self._loaded_schedules):
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

        self._loaded_schedules.clear()

        # Reload from database
        await self._load_all_schedules()
        logger.info("Schedules reloaded successfully")

    async def reload_institution_schedules(self, institution_config_id: UUID) -> None:
        """Reload schedules for a specific institution.

        Args:
            institution_config_id: Institution config UUID to reload.
        """
        if not self._scheduler or not self._is_running:
            return

        # Remove existing jobs for this institution
        prefix = f"reminder_{institution_config_id}_"
        for job_id in list(self._loaded_schedules):
            if job_id.startswith(prefix):
                try:
                    self._scheduler.remove_job(job_id)
                    self._loaded_schedules.discard(job_id)
                except Exception:
                    pass

        # Load schedules for this institution
        async with self._db_session_factory() as session:
            schedules = await self._get_institution_schedules(session, institution_config_id)
            institution = await self._get_institution_config(session, institution_config_id)

            if institution:
                for schedule in schedules:
                    self._create_job_for_schedule(schedule, institution)

    async def _load_all_schedules(self) -> None:
        """Load all active schedules from database."""
        from app.models.db.tenancy import TenantInstitutionConfig
        from app.models.db.workflow import ReminderSchedule

        async with self._db_session_factory() as session:
            # Get all enabled institutions with medical type
            stmt = select(TenantInstitutionConfig).where(
                TenantInstitutionConfig.enabled == True,  # noqa: E712
                TenantInstitutionConfig.institution_type == "medical",
            )
            result = await session.execute(stmt)
            institutions = result.scalars().all()

            for institution in institutions:
                # Get active schedules for this institution
                schedules_stmt = (
                    select(ReminderSchedule)
                    .options(selectinload(ReminderSchedule.message_template))
                    .where(
                        ReminderSchedule.institution_config_id == institution.id,
                        ReminderSchedule.is_active == True,  # noqa: E712
                    )
                )
                schedules_result = await session.execute(schedules_stmt)
                schedules = schedules_result.scalars().all()

                logger.info(
                    f"Loading {len(schedules)} reminder schedules for "
                    f"institution '{institution.institution_name}'"
                )

                for schedule in schedules:
                    self._create_job_for_schedule(schedule, institution)

    async def _get_institution_schedules(
        self,
        session: AsyncSession,
        institution_config_id: UUID,
    ) -> list["ReminderSchedule"]:
        """Get active schedules for an institution."""
        from app.models.db.workflow import ReminderSchedule

        stmt = (
            select(ReminderSchedule)
            .options(selectinload(ReminderSchedule.message_template))
            .where(
                ReminderSchedule.institution_config_id == institution_config_id,
                ReminderSchedule.is_active == True,  # noqa: E712
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _get_institution_config(
        self,
        session: AsyncSession,
        institution_config_id: UUID,
    ) -> "TenantInstitutionConfig | None":
        """Get institution config by ID."""
        from app.models.db.tenancy import TenantInstitutionConfig

        stmt = select(TenantInstitutionConfig).where(
            TenantInstitutionConfig.id == institution_config_id,
            TenantInstitutionConfig.enabled == True,  # noqa: E712
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _create_job_for_schedule(
        self,
        schedule: "ReminderSchedule",
        institution: "TenantInstitutionConfig",
    ) -> None:
        """Create an APScheduler job for a reminder schedule.

        Args:
            schedule: ReminderSchedule configuration.
            institution: TenantInstitutionConfig for the institution.
        """
        if not self._scheduler:
            return

        job_id = f"reminder_{schedule.institution_config_id}_{schedule.schedule_key}"

        try:
            tz = timezone(schedule.timezone)

            # Create cron trigger for the execution hour
            trigger = CronTrigger(
                hour=schedule.execution_hour,
                minute=0,
                timezone=tz,
            )

            # Add job
            self._scheduler.add_job(
                self._execute_reminder_job,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                name=f"{schedule.display_name} ({institution.institution_name})",
                kwargs={
                    "schedule_id": str(schedule.id),
                    "institution_config_id": str(institution.id),
                    "trigger_type": schedule.trigger_type,
                    "trigger_value": schedule.trigger_value,
                },
            )

            self._loaded_schedules.add(job_id)

            logger.debug(
                f"Created job '{job_id}' - {schedule.display_name} at "
                f"{schedule.execution_hour}:00 ({schedule.timezone})"
            )

        except Exception as e:
            logger.error(f"Failed to create job for schedule {schedule.schedule_key}: {e}")

    async def _execute_reminder_job(
        self,
        schedule_id: str,
        institution_config_id: str,
        trigger_type: str,
        trigger_value: int,
    ) -> None:
        """Execute a reminder job - fetch appointments and send reminders.

        Args:
            schedule_id: ReminderSchedule UUID.
            institution_config_id: TenantInstitutionConfig UUID.
            trigger_type: Type of trigger (days_before, hours_before).
            trigger_value: Numeric trigger value.
        """
        logger.info(
            f"Executing reminder job: schedule={schedule_id}, "
            f"trigger={trigger_type}:{trigger_value}"
        )

        try:
            async with self._db_session_factory() as session:
                # Load schedule and institution
                schedule = await self._get_schedule_by_id(session, UUID(schedule_id))
                institution = await self._get_institution_config(
                    session, UUID(institution_config_id)
                )

                if not schedule or not institution:
                    logger.warning(
                        f"Schedule or institution not found for job {schedule_id}"
                    )
                    return

                # Fetch appointments based on trigger type
                appointments = await self._fetch_appointments_for_reminder(
                    institution=institution,
                    trigger_type=trigger_type,
                    trigger_value=trigger_value,
                )

                if not appointments:
                    logger.info(f"No appointments found for reminder {schedule.schedule_key}")
                    return

                logger.info(
                    f"Found {len(appointments)} appointments for "
                    f"reminder {schedule.schedule_key}"
                )

                # Send reminders
                sent_count = 0
                for appointment in appointments:
                    try:
                        await self._send_reminder(
                            appointment=appointment,
                            schedule=schedule,
                            institution=institution,
                        )
                        sent_count += 1
                        # Rate limiting
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Failed to send reminder: {e}")

                logger.info(
                    f"Sent {sent_count}/{len(appointments)} reminders for "
                    f"{schedule.schedule_key}"
                )

        except Exception as e:
            logger.error(f"Error executing reminder job {schedule_id}: {e}", exc_info=True)

    async def _get_schedule_by_id(
        self,
        session: AsyncSession,
        schedule_id: UUID,
    ) -> "ReminderSchedule | None":
        """Get a ReminderSchedule by ID with its message template."""
        from app.models.db.workflow import ReminderSchedule

        stmt = (
            select(ReminderSchedule)
            .options(selectinload(ReminderSchedule.message_template))
            .where(ReminderSchedule.id == schedule_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _fetch_appointments_for_reminder(
        self,
        institution: "TenantInstitutionConfig",
        trigger_type: str,
        trigger_value: int,
    ) -> list[dict[str, Any]]:
        """Fetch appointments that match the reminder trigger.

        Args:
            institution: Institution configuration.
            trigger_type: Type of trigger (days_before, hours_before).
            trigger_value: Numeric trigger value.

        Returns:
            List of appointment dictionaries.
        """
        from ..external import HCWebSOAPClient

        soap_url = institution.base_url
        if not soap_url:
            logger.warning(f"No SOAP URL for institution {institution.institution_key}")
            return []

        # Get institution_id from custom settings
        institution_id = institution.get_custom_value("institution_id", "")
        if not institution_id:
            institution_id = institution.get_setting_value("custom.hcweb_institution_id", "")

        soap = HCWebSOAPClient(
            base_url=soap_url,
            institution_id=str(institution_id),
        )

        try:
            # Determine which method to call based on trigger
            if trigger_type == "days_before":
                if trigger_value == 0:
                    # Today's appointments
                    response = await soap.obtener_turnos_hoy()
                elif trigger_value == 1:
                    # Tomorrow's appointments
                    response = await soap.obtener_turnos_manana()
                else:
                    # Future appointments - use dias_anticipacion parameter
                    response = await soap.obtener_turnos_para_recordatorio(
                        dias_anticipacion=trigger_value
                    )
            elif trigger_type == "hours_before":
                # For hours-based triggers, we need same-day appointments
                if trigger_value <= 24:
                    response = await soap.obtener_turnos_hoy()
                else:
                    response = await soap.obtener_turnos_manana()
            else:
                logger.warning(f"Unknown trigger type: {trigger_type}")
                return []

            if not response.success:
                logger.warning(
                    f"Failed to fetch appointments for {institution.institution_key}: "
                    f"{response.error_message}"
                )
                return []

            # Parse response data
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

    async def _send_reminder(
        self,
        appointment: dict[str, Any],
        schedule: "ReminderSchedule",
        institution: "TenantInstitutionConfig",
    ) -> None:
        """Send a reminder to a patient.

        Args:
            appointment: Appointment data from HCWeb.
            schedule: ReminderSchedule configuration.
            institution: Institution configuration.
        """
        phone = appointment.get("telefono") or appointment.get("celular")
        patient_name = appointment.get("paciente") or appointment.get("nombrePaciente")
        fecha = appointment.get("fecha")
        hora = appointment.get("hora")
        prestador = appointment.get("prestador") or appointment.get("nombrePrestador")
        especialidad = appointment.get("especialidad") or appointment.get("nombreEspecialidad")
        id_turno = appointment.get("idTurno")

        if not phone:
            logger.warning(f"No phone number for appointment {id_turno}, skipping")
            return

        # Format message using schedule's template
        message = schedule.format_message(
            patient_name=patient_name or "Paciente",
            appointment_date=fecha or "",
            appointment_time=hora or "",
            provider_name=prestador,
            specialty_name=especialidad,
            institution_name=institution.institution_name,
            appointment_id=id_turno,
        )

        # Get buttons from schedule
        buttons = schedule.buttons or []

        # Send via WhatsApp
        try:
            if buttons:
                await self._send_whatsapp_interactive(
                    phone=phone,
                    message=message,
                    buttons=buttons,
                    institution=institution,
                )
            else:
                await self._send_whatsapp_message(
                    phone=phone,
                    message=message,
                    institution=institution,
                )

            logger.debug(
                f"Reminder sent to {phone} for appointment {id_turno} "
                f"({schedule.schedule_key})"
            )

        except Exception as e:
            logger.error(f"Failed to send reminder to {phone}: {e}")
            raise

    async def _send_whatsapp_message(
        self,
        phone: str,
        message: str,
        institution: "TenantInstitutionConfig",  # Reserved for future DID-based routing
    ) -> None:
        """Send a text message via WhatsApp.

        Args:
            phone: Recipient phone number.
            message: Message text.
            institution: Institution configuration (for future DID-based routing).
        """
        # Note: institution param reserved for future WhatsApp Business API DID routing
        _ = institution  # Suppress unused warning

        try:
            from app.integrations.whatsapp import WhatsAppClient  # type: ignore[attr-defined]

            # Normalize phone number
            normalized_phone = "".join(c for c in phone if c.isdigit())
            if not normalized_phone.startswith("54"):
                normalized_phone = "54" + normalized_phone

            # Get WhatsApp client
            client = WhatsAppClient()
            await client.send_text_message(
                to=normalized_phone,
                message=message,
            )

        except ImportError:
            logger.warning("WhatsApp integration not available")
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            raise

    async def _send_whatsapp_interactive(
        self,
        phone: str,
        message: str,
        buttons: list[dict[str, str]],
        institution: "TenantInstitutionConfig",
    ) -> None:
        """Send an interactive message with buttons via WhatsApp.

        Args:
            phone: Recipient phone number.
            message: Message text.
            buttons: List of button configurations [{id, title}].
            institution: Institution configuration.
        """
        try:
            from app.integrations.whatsapp import WhatsAppClient  # type: ignore[attr-defined]

            # Normalize phone number
            normalized_phone = "".join(c for c in phone if c.isdigit())
            if not normalized_phone.startswith("54"):
                normalized_phone = "54" + normalized_phone

            # Format buttons for WhatsApp (max 3 buttons, 20 char titles)
            formatted_buttons = [
                {
                    "id": btn.get("id", f"btn_{i}"),
                    "title": btn.get("title", f"Option {i + 1}")[:20],
                }
                for i, btn in enumerate(buttons[:3])
            ]

            # Get WhatsApp client
            client = WhatsAppClient()
            await client.send_interactive_buttons(
                to=normalized_phone,
                body=message,
                buttons=formatted_buttons,
            )

        except ImportError:
            logger.warning("WhatsApp integration not available")
            # Fallback to text message
            await self._send_whatsapp_message(phone, message, institution)
        except AttributeError:
            # Method might not exist, fallback to text
            await self._send_whatsapp_message(phone, message, institution)
        except Exception as e:
            logger.error(f"WhatsApp interactive send error: {e}")
            raise

    async def trigger_manual_reminder(
        self,
        schedule_id: UUID,
        institution_config_id: UUID,
    ) -> int:
        """Manually trigger a specific reminder (for testing/admin).

        Args:
            schedule_id: ReminderSchedule UUID.
            institution_config_id: TenantInstitutionConfig UUID.

        Returns:
            Number of reminders sent.
        """
        async with self._db_session_factory() as session:
            schedule = await self._get_schedule_by_id(session, schedule_id)
            institution = await self._get_institution_config(session, institution_config_id)

            if not schedule or not institution:
                logger.warning("Schedule or institution not found")
                return 0

            appointments = await self._fetch_appointments_for_reminder(
                institution=institution,
                trigger_type=schedule.trigger_type,
                trigger_value=schedule.trigger_value,
            )

            count = 0
            for appointment in appointments:
                try:
                    await self._send_reminder(
                        appointment=appointment,
                        schedule=schedule,
                        institution=institution,
                    )
                    count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending manual reminder: {e}")

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

    def get_loaded_schedules(self) -> list[str]:
        """Get list of loaded schedule job IDs."""
        return list(self._loaded_schedules)


# Module-level singleton
_configurable_scheduler_instance: ConfigurableReminderScheduler | None = None


def get_configurable_reminder_scheduler(
    db_session_factory: Any | None = None,
    enabled: bool = True,
) -> ConfigurableReminderScheduler:
    """Get or create the singleton configurable scheduler instance.

    Args:
        db_session_factory: Async SQLAlchemy session factory (required on first call).
        enabled: Whether scheduler is enabled.

    Returns:
        ConfigurableReminderScheduler singleton instance.

    Raises:
        ValueError: If called without db_session_factory on first call.
    """
    global _configurable_scheduler_instance

    if _configurable_scheduler_instance is None:
        if db_session_factory is None:
            raise ValueError("db_session_factory required on first call")

        _configurable_scheduler_instance = ConfigurableReminderScheduler(
            db_session_factory=db_session_factory,
            enabled=enabled,
        )

    return _configurable_scheduler_instance


async def shutdown_configurable_scheduler() -> None:
    """Shutdown the configurable scheduler singleton."""
    global _configurable_scheduler_instance

    if _configurable_scheduler_instance:
        await _configurable_scheduler_instance.stop()
        _configurable_scheduler_instance = None
