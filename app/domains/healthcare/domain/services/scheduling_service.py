"""
Scheduling Service for Healthcare Domain

Domain service that handles complex appointment scheduling logic.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from ..entities.appointment import Appointment
from ..entities.doctor import Doctor
from ..value_objects.appointment_status import AppointmentStatus, DoctorSpecialty


@dataclass
class AvailableSlot:
    """Represents an available appointment slot."""

    doctor_id: int
    doctor_name: str
    specialty: DoctorSpecialty
    date: date
    start_time: time
    end_time: time
    is_telemedicine_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "specialty": self.specialty.value,
            "date": self.date.isoformat(),
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "is_telemedicine_available": self.is_telemedicine_available,
        }


@dataclass
class SchedulingResult:
    """Result of scheduling operation."""

    success: bool
    appointment: Appointment | None = None
    error: str | None = None
    available_alternatives: list[AvailableSlot] | None = None


class SchedulingService:
    """
    Domain service for appointment scheduling.

    Handles:
    - Finding available time slots
    - Conflict detection
    - Schedule optimization
    - Emergency scheduling

    Example:
        ```python
        service = SchedulingService()
        slots = service.find_available_slots(
            doctor=doctor,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            existing_appointments=appointments,
        )
        result = service.schedule_appointment(
            patient_id=123,
            patient_name="Juan Pérez",
            doctor=doctor,
            slot=slots[0],
            existing_appointments=appointments,
        )
        ```
    """

    def __init__(
        self,
        default_duration_minutes: int = 30,
        min_advance_hours: int = 2,
        max_advance_days: int = 30,
    ):
        """
        Initialize scheduling service.

        Args:
            default_duration_minutes: Default appointment duration
            min_advance_hours: Minimum hours in advance for booking
            max_advance_days: Maximum days in advance for booking
        """
        self.default_duration_minutes = default_duration_minutes
        self.min_advance_hours = min_advance_hours
        self.max_advance_days = max_advance_days

    def find_available_slots(
        self,
        doctor: Doctor,
        start_date: date,
        end_date: date,
        existing_appointments: list[Appointment],
        duration_minutes: int | None = None,
    ) -> list[AvailableSlot]:
        """
        Find available appointment slots for a doctor.

        Args:
            doctor: Doctor to find slots for
            start_date: Start of date range
            end_date: End of date range
            existing_appointments: List of existing appointments
            duration_minutes: Appointment duration (uses default if not specified)

        Returns:
            List of available slots
        """
        if not doctor.can_accept_appointments():
            return []

        duration = duration_minutes or self.default_duration_minutes
        available_slots: list[AvailableSlot] = []
        current_date = start_date

        while current_date <= end_date:
            # Get day of week (0=Monday)
            day_of_week = current_date.weekday()

            # Get doctor's schedule for this day
            day_slots = doctor.get_available_slots(day_of_week)

            for schedule_slot in day_slots:
                # Generate time slots within this schedule slot
                slot_start = schedule_slot.start_time
                slot_end_dt = datetime.combine(current_date, schedule_slot.end_time)

                while True:
                    start_dt = datetime.combine(current_date, slot_start)
                    end_dt = start_dt + timedelta(minutes=duration)

                    if end_dt > slot_end_dt:
                        break

                    # Check if slot is in the past
                    if start_dt < datetime.now():
                        slot_start = end_dt.time()
                        continue

                    # Check for conflicts with existing appointments
                    has_conflict = self._check_conflict(
                        doctor_id=doctor.id or 0,
                        date=current_date,
                        start_time=slot_start,
                        end_time=end_dt.time(),
                        existing_appointments=existing_appointments,
                    )

                    if not has_conflict:
                        available_slots.append(
                            AvailableSlot(
                                doctor_id=doctor.id or 0,
                                doctor_name=doctor.full_name,
                                specialty=doctor.specialty,
                                date=current_date,
                                start_time=slot_start,
                                end_time=end_dt.time(),
                                is_telemedicine_available=True,  # Configurable
                            )
                        )

                    # Move to next slot
                    slot_start = end_dt.time()

            current_date += timedelta(days=1)

        return available_slots

    def find_next_available(
        self,
        doctor: Doctor,
        existing_appointments: list[Appointment],
        after_datetime: datetime | None = None,
    ) -> AvailableSlot | None:
        """
        Find the next available slot for a doctor.

        Args:
            doctor: Doctor to find slot for
            existing_appointments: Existing appointments
            after_datetime: Minimum datetime (default: now + min_advance_hours)

        Returns:
            Next available slot or None
        """
        if after_datetime is None:
            after_datetime = datetime.now() + timedelta(hours=self.min_advance_hours)

        start_date = after_datetime.date()
        end_date = start_date + timedelta(days=self.max_advance_days)

        slots = self.find_available_slots(
            doctor=doctor,
            start_date=start_date,
            end_date=end_date,
            existing_appointments=existing_appointments,
        )

        # Filter slots after the minimum time
        for slot in slots:
            slot_dt = datetime.combine(slot.date, slot.start_time)
            if slot_dt >= after_datetime:
                return slot

        return None

    def schedule_appointment(
        self,
        patient_id: int,
        patient_name: str,
        doctor: Doctor,
        slot: AvailableSlot,
        existing_appointments: list[Appointment],
        reason: str | None = None,
        is_telemedicine: bool = False,
    ) -> SchedulingResult:
        """
        Schedule a new appointment.

        Args:
            patient_id: Patient ID
            patient_name: Patient name
            doctor: Doctor for appointment
            slot: Selected time slot
            existing_appointments: Existing appointments for conflict check
            reason: Appointment reason
            is_telemedicine: Whether it's a telemedicine appointment

        Returns:
            SchedulingResult with success status
        """
        # Validate slot is still available
        has_conflict = self._check_conflict(
            doctor_id=doctor.id or 0,
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            existing_appointments=existing_appointments,
        )

        if has_conflict:
            # Find alternatives
            alternatives = self.find_available_slots(
                doctor=doctor,
                start_date=slot.date,
                end_date=slot.date + timedelta(days=3),
                existing_appointments=existing_appointments,
            )[:5]  # Limit to 5 alternatives

            return SchedulingResult(
                success=False,
                error="El horario seleccionado ya no está disponible",
                available_alternatives=alternatives,
            )

        # Create appointment
        appointment = Appointment.create_consultation(
            patient_id=patient_id,
            patient_name=patient_name,
            doctor_id=doctor.id or 0,
            doctor_name=doctor.full_name,
            appointment_date=slot.date,
            start_time=slot.start_time,
            specialty=doctor.specialty,
            reason=reason,
        )

        if is_telemedicine:
            # Generate video URL (in real app, integrate with video service)
            video_url = f"https://meet.hospital.com/{appointment.id}"
            appointment.setup_telemedicine(video_url)

        return SchedulingResult(
            success=True,
            appointment=appointment,
        )

    def reschedule_appointment(
        self,
        appointment: Appointment,
        new_slot: AvailableSlot,
        existing_appointments: list[Appointment],
    ) -> SchedulingResult:
        """
        Reschedule an existing appointment.

        Args:
            appointment: Appointment to reschedule
            new_slot: New time slot
            existing_appointments: Existing appointments

        Returns:
            SchedulingResult with success status
        """
        # Filter out the current appointment from conflict check
        other_appointments = [a for a in existing_appointments if a.id != appointment.id]

        has_conflict = self._check_conflict(
            doctor_id=new_slot.doctor_id,
            date=new_slot.date,
            start_time=new_slot.start_time,
            end_time=new_slot.end_time,
            existing_appointments=other_appointments,
        )

        if has_conflict:
            return SchedulingResult(
                success=False,
                error="El nuevo horario tiene conflictos",
            )

        try:
            appointment.reschedule(new_slot.date, new_slot.start_time)
            return SchedulingResult(
                success=True,
                appointment=appointment,
            )
        except Exception as e:
            return SchedulingResult(
                success=False,
                error=str(e),
            )

    def _check_conflict(
        self,
        doctor_id: int,
        date: date,
        start_time: time,
        end_time: time,
        existing_appointments: list[Appointment],
    ) -> bool:
        """Check if there's a scheduling conflict."""
        for apt in existing_appointments:
            # Skip cancelled/completed appointments
            if apt.status in [AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED]:
                continue

            # Check same doctor and date
            if apt.doctor_id != doctor_id or apt.appointment_date != date:
                continue

            # Check time overlap
            if apt.start_time is None or apt.end_time is None:
                continue

            if not (end_time <= apt.start_time or start_time >= apt.end_time):
                return True

        return False

    def get_doctor_schedule_summary(
        self,
        doctor: Doctor,
        date: date,
        appointments: list[Appointment],
    ) -> dict[str, Any]:
        """
        Get summary of doctor's schedule for a day.

        Args:
            doctor: Doctor
            date: Date to summarize
            appointments: All appointments

        Returns:
            Schedule summary dictionary
        """
        day_appointments = [
            apt
            for apt in appointments
            if apt.doctor_id == doctor.id
            and apt.appointment_date == date
            and apt.status.is_active()
        ]

        available_slots = self.find_available_slots(
            doctor=doctor,
            start_date=date,
            end_date=date,
            existing_appointments=appointments,
        )

        return {
            "doctor_id": doctor.id,
            "doctor_name": doctor.full_name,
            "date": date.isoformat(),
            "total_appointments": len(day_appointments),
            "available_slots": len(available_slots),
            "appointments": [apt.to_summary_dict() for apt in day_appointments],
            "next_available": available_slots[0].to_dict() if available_slots else None,
        }

    def find_doctors_with_availability(
        self,
        doctors: list[Doctor],
        specialty: DoctorSpecialty | None,
        date: date,
        existing_appointments: list[Appointment],
    ) -> list[dict[str, Any]]:
        """
        Find doctors with available slots for a specific specialty.

        Args:
            doctors: List of doctors to check
            specialty: Required specialty (None for any)
            date: Date to check
            existing_appointments: Existing appointments

        Returns:
            List of doctors with their available slots
        """
        result = []

        for doctor in doctors:
            # Filter by specialty if specified
            if specialty and not doctor.has_specialty(specialty):
                continue

            if not doctor.can_accept_appointments():
                continue

            slots = self.find_available_slots(
                doctor=doctor,
                start_date=date,
                end_date=date,
                existing_appointments=existing_appointments,
            )

            if slots:
                result.append(
                    {
                        "doctor": doctor.to_summary_dict(),
                        "available_slots": [s.to_dict() for s in slots[:3]],  # Limit to 3
                        "total_available": len(slots),
                    }
                )

        return result
