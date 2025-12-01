"""
Appointment Repository Implementation

SQLAlchemy implementation of IAppointmentRepository.
"""

import logging
from datetime import date, time, datetime, timedelta, UTC

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.healthcare.application.ports.appointment_repository import IAppointmentRepository
from app.domains.healthcare.domain.entities.appointment import Appointment
from app.domains.healthcare.domain.value_objects.appointment_status import (
    AppointmentStatus,
    DoctorSpecialty,
)
from app.domains.healthcare.infrastructure.persistence.sqlalchemy.models import AppointmentModel

logger = logging.getLogger(__name__)


class SQLAlchemyAppointmentRepository(IAppointmentRepository):
    """
    SQLAlchemy implementation of appointment repository.

    Handles all appointment data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def find_by_id(self, appointment_id: int) -> Appointment | None:
        """Find appointment by ID."""
        result = await self.session.execute(
            select(AppointmentModel).where(AppointmentModel.id == appointment_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_patient(
        self,
        patient_id: int,
        include_past: bool = False,
        limit: int = 10,
    ) -> list[Appointment]:
        """Find appointments for a patient."""
        query = select(AppointmentModel).where(AppointmentModel.patient_id == patient_id)

        if not include_past:
            query = query.where(AppointmentModel.appointment_date >= date.today())

        query = query.order_by(AppointmentModel.appointment_date, AppointmentModel.start_time)
        query = query.limit(limit)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_by_doctor(
        self,
        doctor_id: int,
        appointment_date: date | None = None,
        limit: int = 50,
    ) -> list[Appointment]:
        """Find appointments for a doctor."""
        query = select(AppointmentModel).where(AppointmentModel.doctor_id == doctor_id)

        if appointment_date:
            query = query.where(AppointmentModel.appointment_date == appointment_date)

        query = query.order_by(AppointmentModel.appointment_date, AppointmentModel.start_time)
        query = query.limit(limit)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_by_date(
        self,
        appointment_date: date,
        status: AppointmentStatus | None = None,
    ) -> list[Appointment]:
        """Find appointments for a specific date."""
        query = select(AppointmentModel).where(
            AppointmentModel.appointment_date == appointment_date
        )

        if status:
            query = query.where(AppointmentModel.status == status)

        query = query.order_by(AppointmentModel.start_time)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        doctor_id: int | None = None,
        specialty: DoctorSpecialty | None = None,
    ) -> list[Appointment]:
        """Find appointments within date range."""
        query = select(AppointmentModel).where(
            AppointmentModel.appointment_date.between(start_date, end_date)
        )

        if doctor_id:
            query = query.where(AppointmentModel.doctor_id == doctor_id)

        if specialty:
            query = query.where(AppointmentModel.specialty == specialty)

        query = query.order_by(AppointmentModel.appointment_date, AppointmentModel.start_time)

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_upcoming_by_patient(
        self,
        patient_id: int,
        limit: int = 5,
    ) -> list[Appointment]:
        """Find upcoming appointments for patient."""
        today = date.today()
        now = datetime.now(UTC).time()

        result = await self.session.execute(
            select(AppointmentModel)
            .where(
                and_(
                    AppointmentModel.patient_id == patient_id,
                    or_(
                        AppointmentModel.appointment_date > today,
                        and_(
                            AppointmentModel.appointment_date == today,
                            AppointmentModel.start_time >= now,
                        ),
                    ),
                    AppointmentModel.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                    ]),
                )
            )
            .order_by(AppointmentModel.appointment_date, AppointmentModel.start_time)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_available_slots(
        self,
        doctor_id: int,
        appointment_date: date,
        duration_minutes: int = 30,
    ) -> list[time]:
        """Find available time slots for a doctor."""
        # Get existing appointments
        existing = await self.find_by_doctor(doctor_id, appointment_date)

        # Define working hours (9 AM to 6 PM)
        work_start = time(9, 0)
        work_end = time(18, 0)

        # Generate all possible slots
        available_slots: list[time] = []
        current = datetime.combine(appointment_date, work_start)
        end = datetime.combine(appointment_date, work_end)

        while current + timedelta(minutes=duration_minutes) <= end:
            slot_time = current.time()
            slot_end = (current + timedelta(minutes=duration_minutes)).time()

            # Check if slot conflicts with existing appointments
            has_conflict = False
            for apt in existing:
                if apt.status not in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]:
                    if apt.start_time and apt.end_time:
                        # Check overlap
                        if not (slot_end <= apt.start_time or slot_time >= apt.end_time):
                            has_conflict = True
                            break

            if not has_conflict:
                available_slots.append(slot_time)

            current += timedelta(minutes=duration_minutes)

        return available_slots

    async def check_conflict(
        self,
        doctor_id: int,
        appointment_date: date,
        start_time: time,
        end_time: time,
        exclude_appointment_id: int | None = None,
    ) -> bool:
        """Check if time slot has conflicts."""
        query = select(AppointmentModel).where(
            and_(
                AppointmentModel.doctor_id == doctor_id,
                AppointmentModel.appointment_date == appointment_date,
                AppointmentModel.status.notin_([
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW,
                ]),
                # Time overlap check
                AppointmentModel.start_time < end_time,
                AppointmentModel.end_time > start_time,
            )
        )

        if exclude_appointment_id:
            query = query.where(AppointmentModel.id != exclude_appointment_id)

        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def find_needing_reminder(self, hours_before: int = 24) -> list[Appointment]:
        """Find appointments needing reminders."""
        now = datetime.now(UTC)
        reminder_window_start = now
        reminder_window_end = now + timedelta(hours=hours_before)

        result = await self.session.execute(
            select(AppointmentModel).where(
                and_(
                    AppointmentModel.reminder_sent == False,
                    AppointmentModel.status.in_([
                        AppointmentStatus.SCHEDULED,
                        AppointmentStatus.CONFIRMED,
                    ]),
                    AppointmentModel.appointment_date >= reminder_window_start.date(),
                    AppointmentModel.appointment_date <= reminder_window_end.date(),
                )
            )
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_emergencies(self, include_completed: bool = False) -> list[Appointment]:
        """Find emergency appointments."""
        query = select(AppointmentModel).where(AppointmentModel.is_emergency == True)

        if not include_completed:
            query = query.where(
                AppointmentModel.status.in_([
                    AppointmentStatus.SCHEDULED,
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.IN_PROGRESS,
                ])
            )

        query = query.order_by(
            AppointmentModel.triage_priority,
            AppointmentModel.created_at,
        )

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def save(self, appointment: Appointment) -> Appointment:
        """Save or update appointment."""
        if appointment.id:
            result = await self.session.execute(
                select(AppointmentModel).where(AppointmentModel.id == appointment.id)
            )
            model = result.scalar_one_or_none()
            if model:
                self._update_model(model, appointment)
            else:
                model = self._to_model(appointment)
                self.session.add(model)
        else:
            model = self._to_model(appointment)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        return self._to_entity(model)

    async def delete(self, appointment_id: int) -> bool:
        """Delete appointment."""
        result = await self.session.execute(
            select(AppointmentModel).where(AppointmentModel.id == appointment_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    async def count_by_status(
        self,
        status: AppointmentStatus,
        appointment_date: date | None = None,
    ) -> int:
        """Count appointments by status."""
        query = select(func.count()).where(AppointmentModel.status == status)

        if appointment_date:
            query = query.where(AppointmentModel.appointment_date == appointment_date)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def count_by_doctor(
        self,
        doctor_id: int,
        start_date: date,
        end_date: date,
    ) -> int:
        """Count appointments for doctor in range."""
        result = await self.session.execute(
            select(func.count()).where(
                and_(
                    AppointmentModel.doctor_id == doctor_id,
                    AppointmentModel.appointment_date.between(start_date, end_date),
                )
            )
        )
        return result.scalar_one()

    # Mapping methods

    def _to_entity(self, model: AppointmentModel) -> Appointment:
        """Convert model to entity."""
        # Note: Using Column() syntax - attribute access returns Column objects at class level
        # At instance level, they return actual values. Type ignore needed for Pyright.
        appointment = Appointment(
            id=model.id,  # type: ignore[arg-type]
            patient_id=model.patient_id,  # type: ignore[arg-type]
            patient_name=model.patient_name or "",  # type: ignore[arg-type]
            doctor_id=model.doctor_id or 0,  # type: ignore[arg-type]
            doctor_name=model.doctor_name or "",  # type: ignore[arg-type]
            appointment_date=model.appointment_date,  # type: ignore[arg-type]
            start_time=model.start_time,  # type: ignore[arg-type]
            end_time=model.end_time,  # type: ignore[arg-type]
            duration_minutes=model.duration_minutes or 30,  # type: ignore[arg-type]
            specialty=model.specialty or DoctorSpecialty.GENERAL_PRACTICE,  # type: ignore[arg-type]
            appointment_type=model.appointment_type or "consultation",  # type: ignore[arg-type]
            is_emergency=model.is_emergency or False,  # type: ignore[arg-type]
            triage_priority=model.triage_priority,  # type: ignore[arg-type]
            status=model.status or AppointmentStatus.SCHEDULED,  # type: ignore[arg-type]
            location=model.location,  # type: ignore[arg-type]
            is_telemedicine=model.is_telemedicine or False,  # type: ignore[arg-type]
            video_call_url=model.video_call_url,  # type: ignore[arg-type]
            reason=model.reason,  # type: ignore[arg-type]
            symptoms=model.symptoms or [],  # type: ignore[arg-type]
            notes=model.notes,  # type: ignore[arg-type]
            diagnosis=model.diagnosis,  # type: ignore[arg-type]
            prescriptions=model.prescriptions or [],  # type: ignore[arg-type]
            reminder_sent=model.reminder_sent or False,  # type: ignore[arg-type]
            reminder_sent_at=model.reminder_sent_at,  # type: ignore[arg-type]
            confirmed_at=model.confirmed_at,  # type: ignore[arg-type]
            started_at=model.started_at,  # type: ignore[arg-type]
            completed_at=model.completed_at,  # type: ignore[arg-type]
            cancelled_at=model.cancelled_at,  # type: ignore[arg-type]
            cancellation_reason=model.cancellation_reason,  # type: ignore[arg-type]
            cancelled_by=model.cancelled_by,  # type: ignore[arg-type]
        )

        if model.created_at:
            appointment.created_at = model.created_at  # type: ignore[assignment]
        if model.updated_at:
            appointment.updated_at = model.updated_at  # type: ignore[assignment]

        return appointment

    def _to_model(self, appointment: Appointment) -> AppointmentModel:
        """Convert entity to model."""
        return AppointmentModel(
            patient_id=appointment.patient_id,
            patient_name=appointment.patient_name,
            doctor_id=appointment.doctor_id if appointment.doctor_id else None,
            doctor_name=appointment.doctor_name,
            appointment_date=appointment.appointment_date,
            start_time=appointment.start_time,
            end_time=appointment.end_time,
            duration_minutes=appointment.duration_minutes,
            specialty=appointment.specialty,
            appointment_type=appointment.appointment_type,
            is_emergency=appointment.is_emergency,
            triage_priority=appointment.triage_priority,
            status=appointment.status,
            location=appointment.location,
            is_telemedicine=appointment.is_telemedicine,
            video_call_url=appointment.video_call_url,
            reason=appointment.reason,
            symptoms=appointment.symptoms,
            notes=appointment.notes,
            diagnosis=appointment.diagnosis,
            prescriptions=appointment.prescriptions,
            reminder_sent=appointment.reminder_sent,
            reminder_sent_at=appointment.reminder_sent_at,
            confirmed_at=appointment.confirmed_at,
            started_at=appointment.started_at,
            completed_at=appointment.completed_at,
            cancelled_at=appointment.cancelled_at,
            cancellation_reason=appointment.cancellation_reason,
            cancelled_by=appointment.cancelled_by,
        )

    def _update_model(self, model: AppointmentModel, appointment: Appointment) -> None:
        """Update model from entity."""
        # Note: SQLAlchemy Column() syntax means Pyright sees Column objects at class level.
        # At runtime, these assignments work correctly.
        model.patient_id = appointment.patient_id  # type: ignore[assignment]
        model.patient_name = appointment.patient_name  # type: ignore[assignment]
        model.doctor_id = appointment.doctor_id if appointment.doctor_id else None  # type: ignore[assignment]
        model.doctor_name = appointment.doctor_name  # type: ignore[assignment]
        model.appointment_date = appointment.appointment_date  # type: ignore[assignment]
        model.start_time = appointment.start_time  # type: ignore[assignment]
        model.end_time = appointment.end_time  # type: ignore[assignment]
        model.duration_minutes = appointment.duration_minutes  # type: ignore[assignment]
        model.specialty = appointment.specialty  # type: ignore[assignment]
        model.appointment_type = appointment.appointment_type  # type: ignore[assignment]
        model.is_emergency = appointment.is_emergency  # type: ignore[assignment]
        model.triage_priority = appointment.triage_priority  # type: ignore[assignment]
        model.status = appointment.status  # type: ignore[assignment]
        model.location = appointment.location  # type: ignore[assignment]
        model.is_telemedicine = appointment.is_telemedicine  # type: ignore[assignment]
        model.video_call_url = appointment.video_call_url  # type: ignore[assignment]
        model.reason = appointment.reason  # type: ignore[assignment]
        model.symptoms = appointment.symptoms  # type: ignore[assignment]
        model.notes = appointment.notes  # type: ignore[assignment]
        model.diagnosis = appointment.diagnosis  # type: ignore[assignment]
        model.prescriptions = appointment.prescriptions  # type: ignore[assignment]
        model.reminder_sent = appointment.reminder_sent  # type: ignore[assignment]
        model.reminder_sent_at = appointment.reminder_sent_at  # type: ignore[assignment]
        model.confirmed_at = appointment.confirmed_at  # type: ignore[assignment]
        model.started_at = appointment.started_at  # type: ignore[assignment]
        model.completed_at = appointment.completed_at  # type: ignore[assignment]
        model.cancelled_at = appointment.cancelled_at  # type: ignore[assignment]
        model.cancellation_reason = appointment.cancellation_reason  # type: ignore[assignment]
        model.cancelled_by = appointment.cancelled_by  # type: ignore[assignment]
