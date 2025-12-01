"""
Doctor Repository Implementation

SQLAlchemy implementation of IDoctorRepository.
"""

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.healthcare.application.ports.doctor_repository import IDoctorRepository
from app.domains.healthcare.domain.entities.doctor import Doctor, WeeklySchedule
from app.domains.healthcare.domain.value_objects.appointment_status import DoctorSpecialty, TimeSlot
from app.domains.healthcare.infrastructure.persistence.sqlalchemy.models import DoctorModel
from app.core.domain import Email, PhoneNumber

logger = logging.getLogger(__name__)


class SQLAlchemyDoctorRepository(IDoctorRepository):
    """
    SQLAlchemy implementation of doctor repository.

    Handles all doctor data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def find_by_id(self, doctor_id: int) -> Doctor | None:
        """Find doctor by ID."""
        result = await self.session.execute(
            select(DoctorModel).where(DoctorModel.id == doctor_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_license(self, license_number: str) -> Doctor | None:
        """Find doctor by license number."""
        result = await self.session.execute(
            select(DoctorModel).where(DoctorModel.license_number == license_number)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_specialty(
        self,
        specialty: DoctorSpecialty,
        limit: int = 20,
    ) -> list[Doctor]:
        """Find doctors by specialty."""
        result = await self.session.execute(
            select(DoctorModel)
            .where(
                DoctorModel.specialty == specialty,
                DoctorModel.is_active == True,
            )
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def search(self, query: str, limit: int = 10) -> list[Doctor]:
        """Search doctors by name or specialty."""
        search_term = f"%{query}%"
        result = await self.session.execute(
            select(DoctorModel)
            .where(
                or_(
                    DoctorModel.first_name.ilike(search_term),
                    DoctorModel.last_name.ilike(search_term),
                    DoctorModel.license_number.ilike(search_term),
                )
            )
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_active(self, accepting_patients: bool = True) -> list[Doctor]:
        """Get active doctors, optionally filtering by accepting patients."""
        query = select(DoctorModel).where(DoctorModel.is_active == True)

        # Note: DoctorModel doesn't have an accepting_patients field
        # We filter only by is_active

        result = await self.session.execute(query)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def save(self, doctor: Doctor) -> Doctor:
        """Save or update doctor."""
        if doctor.id:
            # Update existing
            result = await self.session.execute(
                select(DoctorModel).where(DoctorModel.id == doctor.id)
            )
            model = result.scalar_one_or_none()
            if model:
                self._update_model(model, doctor)
            else:
                model = self._to_model(doctor)
                self.session.add(model)
        else:
            # Create new
            model = self._to_model(doctor)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        return self._to_entity(model)

    async def delete(self, doctor_id: int) -> bool:
        """Delete a doctor."""
        result = await self.session.execute(
            select(DoctorModel).where(DoctorModel.id == doctor_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    # Additional useful methods

    async def count(self) -> int:
        """Get total doctor count."""
        result = await self.session.execute(
            select(func.count()).select_from(DoctorModel)
        )
        return result.scalar_one()

    async def count_by_specialty(self, specialty: DoctorSpecialty) -> int:
        """Count doctors by specialty."""
        result = await self.session.execute(
            select(func.count()).where(DoctorModel.specialty == specialty)
        )
        return result.scalar_one()

    async def exists(self, doctor_id: int) -> bool:
        """Check if doctor exists."""
        result = await self.session.execute(
            select(func.count()).where(DoctorModel.id == doctor_id)
        )
        return result.scalar_one() > 0

    async def find_all(self, limit: int = 100) -> list[Doctor]:
        """Get all doctors."""
        result = await self.session.execute(
            select(DoctorModel).limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    # Mapping methods

    def _to_entity(self, model: DoctorModel) -> Doctor:
        """Convert model to entity."""
        # Note: SQLAlchemy Column() syntax - Pyright sees Column objects at class level.
        # Build optional value objects
        email = Email(model.email) if model.email else None  # type: ignore[arg-type]
        phone = PhoneNumber(model.phone) if model.phone else None  # type: ignore[arg-type]

        # Build weekly schedule from working days and hours
        weekly_schedule = WeeklySchedule()
        if model.working_days and model.working_hours_start and model.working_hours_end:
            day_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            for day_name in model.working_days:
                day_num = day_map.get(day_name.lower())
                if day_num is not None:
                    slot = TimeSlot(
                        start_time=model.working_hours_start,  # type: ignore[arg-type]
                        end_time=model.working_hours_end,  # type: ignore[arg-type]
                        duration_minutes=model.appointment_duration_minutes or 30,  # type: ignore[arg-type]
                    )
                    weekly_schedule.add_slot(day_num, slot)

        # Build secondary specialties list
        secondary_specialties: list[DoctorSpecialty] = []
        if model.secondary_specialties:
            for spec_value in model.secondary_specialties:
                try:
                    secondary_specialties.append(DoctorSpecialty(spec_value))
                except ValueError:
                    pass

        doctor = Doctor(
            id=model.id,  # type: ignore[arg-type]
            first_name=model.first_name,  # type: ignore[arg-type]
            last_name=model.last_name,  # type: ignore[arg-type]
            email=email,
            phone=phone,
            license_number=model.license_number,  # type: ignore[arg-type]
            specialty=model.specialty or DoctorSpecialty.GENERAL_PRACTICE,  # type: ignore[arg-type]
            secondary_specialties=secondary_specialties,
            weekly_schedule=weekly_schedule,
            appointment_duration_minutes=model.appointment_duration_minutes or 30,  # type: ignore[arg-type]
            is_active=model.is_active if model.is_active is not None else True,  # type: ignore[arg-type]
        )

        if model.created_at:
            doctor.created_at = model.created_at  # type: ignore[assignment]
        if model.updated_at:
            doctor.updated_at = model.updated_at  # type: ignore[assignment]

        return doctor

    def _to_model(self, doctor: Doctor) -> DoctorModel:
        """Convert entity to model."""
        # Build working days list from weekly schedule
        working_days = []
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        working_hours_start = None
        working_hours_end = None

        for day_num, day_name in enumerate(day_names):
            slots = doctor.weekly_schedule.get_slots_for_day(day_num)
            if slots:
                working_days.append(day_name)
                # Take first slot's times
                if not working_hours_start:
                    working_hours_start = slots[0].start_time
                    working_hours_end = slots[0].end_time

        return DoctorModel(
            first_name=doctor.first_name,
            last_name=doctor.last_name,
            national_id=None,
            license_number=doctor.license_number,
            specialty=doctor.specialty,
            secondary_specialties=[s.value for s in doctor.secondary_specialties],
            email=str(doctor.email) if doctor.email else None,
            phone=str(doctor.phone) if doctor.phone else None,
            working_days=working_days,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
            appointment_duration_minutes=doctor.appointment_duration_minutes,
            is_active=doctor.is_active,
        )

    def _update_model(self, model: DoctorModel, doctor: Doctor) -> None:
        """Update model from entity."""
        # Note: SQLAlchemy Column() syntax means Pyright sees Column objects at class level.
        model.first_name = doctor.first_name  # type: ignore[assignment]
        model.last_name = doctor.last_name  # type: ignore[assignment]
        model.license_number = doctor.license_number  # type: ignore[assignment]
        model.specialty = doctor.specialty  # type: ignore[assignment]
        model.secondary_specialties = [s.value for s in doctor.secondary_specialties]  # type: ignore[assignment]
        model.email = str(doctor.email) if doctor.email else None  # type: ignore[assignment]
        model.phone = str(doctor.phone) if doctor.phone else None  # type: ignore[assignment]
        model.appointment_duration_minutes = doctor.appointment_duration_minutes  # type: ignore[assignment]
        model.is_active = doctor.is_active  # type: ignore[assignment]

        # Update schedule
        working_days: list[str] = []
        day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        working_hours_start = None
        working_hours_end = None

        for day_num, day_name in enumerate(day_names):
            slots = doctor.weekly_schedule.get_slots_for_day(day_num)
            if slots:
                working_days.append(day_name)
                if not working_hours_start:
                    working_hours_start = slots[0].start_time
                    working_hours_end = slots[0].end_time

        model.working_days = working_days  # type: ignore[assignment]
        model.working_hours_start = working_hours_start  # type: ignore[assignment]
        model.working_hours_end = working_hours_end  # type: ignore[assignment]
