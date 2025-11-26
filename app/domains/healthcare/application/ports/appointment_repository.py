"""
Appointment Repository Port

Interface for appointment data access following Clean Architecture.
"""

from datetime import date, time
from typing import Protocol, runtime_checkable

from app.domains.healthcare.domain.entities.appointment import Appointment
from app.domains.healthcare.domain.value_objects.appointment_status import (
    AppointmentStatus,
    DoctorSpecialty,
)


@runtime_checkable
class IAppointmentRepository(Protocol):
    """
    Appointment repository interface.

    Defines the contract for appointment data access operations.

    Example:
        ```python
        class SQLAlchemyAppointmentRepository(IAppointmentRepository):
            async def find_by_id(self, appointment_id: int) -> Appointment | None:
                # SQLAlchemy implementation
                pass
        ```
    """

    async def find_by_id(self, appointment_id: int) -> Appointment | None:
        """
        Find appointment by ID.

        Args:
            appointment_id: Unique appointment identifier

        Returns:
            Appointment if found, None otherwise
        """
        ...

    async def find_by_patient(
        self,
        patient_id: int,
        include_past: bool = False,
        limit: int = 10,
    ) -> list[Appointment]:
        """
        Find appointments for a patient.

        Args:
            patient_id: Patient ID
            include_past: Include past appointments
            limit: Maximum results

        Returns:
            List of patient's appointments
        """
        ...

    async def find_by_doctor(
        self,
        doctor_id: int,
        appointment_date: date | None = None,
        limit: int = 50,
    ) -> list[Appointment]:
        """
        Find appointments for a doctor.

        Args:
            doctor_id: Doctor ID
            appointment_date: Optional specific date filter
            limit: Maximum results

        Returns:
            List of doctor's appointments
        """
        ...

    async def find_by_date(
        self,
        appointment_date: date,
        status: AppointmentStatus | None = None,
    ) -> list[Appointment]:
        """
        Find appointments for a specific date.

        Args:
            appointment_date: Date to search
            status: Optional status filter

        Returns:
            List of appointments on that date
        """
        ...

    async def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        doctor_id: int | None = None,
        specialty: DoctorSpecialty | None = None,
    ) -> list[Appointment]:
        """
        Find appointments within date range.

        Args:
            start_date: Start of range
            end_date: End of range
            doctor_id: Optional doctor filter
            specialty: Optional specialty filter

        Returns:
            List of appointments in range
        """
        ...

    async def find_upcoming_by_patient(
        self,
        patient_id: int,
        limit: int = 5,
    ) -> list[Appointment]:
        """
        Find upcoming appointments for patient.

        Args:
            patient_id: Patient ID
            limit: Maximum results

        Returns:
            List of upcoming appointments
        """
        ...

    async def find_available_slots(
        self,
        doctor_id: int,
        appointment_date: date,
        duration_minutes: int = 30,
    ) -> list[time]:
        """
        Find available time slots for a doctor.

        Args:
            doctor_id: Doctor ID
            appointment_date: Date to check
            duration_minutes: Required duration

        Returns:
            List of available start times
        """
        ...

    async def check_conflict(
        self,
        doctor_id: int,
        appointment_date: date,
        start_time: time,
        end_time: time,
        exclude_appointment_id: int | None = None,
    ) -> bool:
        """
        Check if time slot has conflicts.

        Args:
            doctor_id: Doctor ID
            appointment_date: Date
            start_time: Proposed start time
            end_time: Proposed end time
            exclude_appointment_id: Appointment ID to exclude (for reschedule)

        Returns:
            True if conflict exists
        """
        ...

    async def find_needing_reminder(
        self,
        hours_before: int = 24,
    ) -> list[Appointment]:
        """
        Find appointments needing reminders.

        Args:
            hours_before: Hours before appointment

        Returns:
            List of appointments needing reminder
        """
        ...

    async def find_emergencies(
        self,
        include_completed: bool = False,
    ) -> list[Appointment]:
        """
        Find emergency appointments.

        Args:
            include_completed: Include completed emergencies

        Returns:
            List of emergency appointments
        """
        ...

    async def save(self, appointment: Appointment) -> Appointment:
        """
        Save or update appointment.

        Args:
            appointment: Appointment to save

        Returns:
            Saved appointment with ID
        """
        ...

    async def delete(self, appointment_id: int) -> bool:
        """
        Delete appointment.

        Args:
            appointment_id: Appointment ID

        Returns:
            True if deleted
        """
        ...

    async def count_by_status(
        self,
        status: AppointmentStatus,
        appointment_date: date | None = None,
    ) -> int:
        """
        Count appointments by status.

        Args:
            status: Status to count
            appointment_date: Optional date filter

        Returns:
            Count of appointments
        """
        ...

    async def count_by_doctor(
        self,
        doctor_id: int,
        start_date: date,
        end_date: date,
    ) -> int:
        """
        Count appointments for doctor in range.

        Args:
            doctor_id: Doctor ID
            start_date: Start date
            end_date: End date

        Returns:
            Appointment count
        """
        ...
