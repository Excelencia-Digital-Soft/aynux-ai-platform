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
    TriagePriority,
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
        appointment = Appointment(
            id=model.id,
            patient_id=model.patient_id,
            patient_name=model.patient_name or "",
            doctor_id=model.doctor_id or 0,
            doctor_name=model.doctor_name or "",
            appointment_date=model.appointment_date,
            start_time=model.start_time,
            end_time=model.end_time,
            duration_minutes=model.duration_minutes or 30,
            specialty=model.specialty or DoctorSpecialty.GENERAL_PRACTICE,
            appointment_type=model.appointment_type or "consultation",
            is_emergency=model.is_emergency or False,
            triage_priority=model.triage_priority,
            status=model.status or AppointmentStatus.SCHEDULED,
            location=model.location,
            is_telemedicine=model.is_telemedicine or False,
            video_call_url=model.video_call_url,
            reason=model.reason,
            symptoms=model.symptoms or [],
            notes=model.notes,
            diagnosis=model.diagnosis,
            prescriptions=model.prescriptions or [],
            reminder_sent=model.reminder_sent or False,
            reminder_sent_at=model.reminder_sent_at,
            confirmed_at=model.confirmed_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            cancelled_at=model.cancelled_at,
            cancellation_reason=model.cancellation_reason,
            cancelled_by=model.cancelled_by,
        )

        if model.created_at:
            appointment.created_at = model.created_at
        if model.updated_at:
            appointment.updated_at = model.updated_at

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
        model.patient_id = appointment.patient_id
        model.patient_name = appointment.patient_name
        model.doctor_id = appointment.doctor_id if appointment.doctor_id else None
        model.doctor_name = appointment.doctor_name
        model.appointment_date = appointment.appointment_date
        model.start_time = appointment.start_time
        model.end_time = appointment.end_time
        model.duration_minutes = appointment.duration_minutes
        model.specialty = appointment.specialty
        model.appointment_type = appointment.appointment_type
        model.is_emergency = appointment.is_emergency
        model.triage_priority = appointment.triage_priority
        model.status = appointment.status
        model.location = appointment.location
        model.is_telemedicine = appointment.is_telemedicine
        model.video_call_url = appointment.video_call_url
        model.reason = appointment.reason
        model.symptoms = appointment.symptoms
        model.notes = appointment.notes
        model.diagnosis = appointment.diagnosis
        model.prescriptions = appointment.prescriptions
        model.reminder_sent = appointment.reminder_sent
        model.reminder_sent_at = appointment.reminder_sent_at
        model.confirmed_at = appointment.confirmed_at
        model.started_at = appointment.started_at
        model.completed_at = appointment.completed_at
        model.cancelled_at = appointment.cancelled_at
        model.cancellation_reason = appointment.cancellation_reason
        model.cancelled_by = appointment.cancelled_by
