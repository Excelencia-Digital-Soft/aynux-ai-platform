"""
Appointment Entity for Healthcare Domain

Represents a medical appointment with scheduling and status tracking.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from app.core.domain import (
    AggregateRoot,
    InvalidOperationException,
)

from ..value_objects.appointment_status import (
    AppointmentStatus,
    DoctorSpecialty,
    TriagePriority,
)


@dataclass
class Appointment(AggregateRoot[int]):
    """
    Appointment aggregate root for healthcare domain.

    Manages appointment lifecycle, scheduling, and related information.

    Example:
        ```python
        appointment = Appointment(
            patient_id=123,
            doctor_id=456,
            appointment_date=date(2024, 1, 15),
            start_time=time(10, 0),
            specialty=DoctorSpecialty.CARDIOLOGY,
        )
        appointment.confirm()
        appointment.start()
        appointment.complete(notes="Regular checkup, all good")
        ```
    """

    # References
    patient_id: int = 0
    patient_name: str = ""
    doctor_id: int = 0
    doctor_name: str = ""

    # Scheduling
    appointment_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int = 30

    # Type and specialty
    specialty: DoctorSpecialty = DoctorSpecialty.GENERAL_PRACTICE
    appointment_type: str = "consultation"  # consultation, follow_up, emergency, procedure
    is_emergency: bool = False
    triage_priority: TriagePriority | None = None

    # Status
    status: AppointmentStatus = AppointmentStatus.SCHEDULED

    # Location
    location: str | None = None  # Room/office number
    is_telemedicine: bool = False
    video_call_url: str | None = None

    # Medical information
    reason: str | None = None  # Chief complaint
    symptoms: list[str] = field(default_factory=list)
    notes: str | None = None
    diagnosis: str | None = None
    prescriptions: list[str] = field(default_factory=list)

    # Reminders
    reminder_sent: bool = False
    reminder_sent_at: datetime | None = None

    # Timestamps
    confirmed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None

    # Cancellation
    cancellation_reason: str | None = None
    cancelled_by: str | None = None  # "patient" or "doctor" or "system"

    def __post_init__(self):
        """Initialize appointment."""
        # Calculate end time if not provided
        if self.start_time and not self.end_time:
            start_dt = datetime.combine(date.today(), self.start_time)
            end_dt = start_dt + timedelta(minutes=self.duration_minutes)
            self.end_time = end_dt.time()

    @property
    def datetime_start(self) -> datetime | None:
        """Get start as datetime."""
        if self.appointment_date and self.start_time:
            return datetime.combine(self.appointment_date, self.start_time)
        return None

    @property
    def datetime_end(self) -> datetime | None:
        """Get end as datetime."""
        if self.appointment_date and self.end_time:
            return datetime.combine(self.appointment_date, self.end_time)
        return None

    @property
    def is_today(self) -> bool:
        """Check if appointment is today."""
        return self.appointment_date == date.today()

    @property
    def is_upcoming(self) -> bool:
        """Check if appointment is in the future."""
        if self.appointment_date is None:
            return False
        return self.appointment_date >= date.today()

    @property
    def is_past(self) -> bool:
        """Check if appointment has passed."""
        if self.appointment_date is None:
            return False
        return self.appointment_date < date.today()

    # Status Transitions

    def confirm(self) -> None:
        """Confirm the appointment."""
        if not self.status.can_transition_to(AppointmentStatus.CONFIRMED):
            raise InvalidOperationException(
                operation="confirm",
                current_state=self.status.value,
            )

        self.status = AppointmentStatus.CONFIRMED
        self.confirmed_at = datetime.now(UTC)
        self.touch()

    def start(self) -> None:
        """Start the appointment (patient arrived)."""
        if not self.status.can_transition_to(AppointmentStatus.IN_PROGRESS):
            raise InvalidOperationException(
                operation="start",
                current_state=self.status.value,
            )

        self.status = AppointmentStatus.IN_PROGRESS
        self.started_at = datetime.now(UTC)
        self.touch()

    def complete(self, notes: str | None = None, diagnosis: str | None = None) -> None:
        """Complete the appointment."""
        if not self.status.can_transition_to(AppointmentStatus.COMPLETED):
            raise InvalidOperationException(
                operation="complete",
                current_state=self.status.value,
            )

        self.status = AppointmentStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        if notes:
            self.notes = notes
        if diagnosis:
            self.diagnosis = diagnosis
        self.touch()

    def cancel(self, reason: str | None = None, cancelled_by: str = "system") -> None:
        """Cancel the appointment."""
        if not self.status.can_be_cancelled():
            raise InvalidOperationException(
                operation="cancel",
                current_state=self.status.value,
                message="Cannot cancel appointment in current state",
            )

        self.status = AppointmentStatus.CANCELLED
        self.cancelled_at = datetime.now(UTC)
        self.cancellation_reason = reason
        self.cancelled_by = cancelled_by
        self.touch()

    def mark_no_show(self) -> None:
        """Mark patient as no-show."""
        if not self.status.can_transition_to(AppointmentStatus.NO_SHOW):
            raise InvalidOperationException(
                operation="mark_no_show",
                current_state=self.status.value,
            )

        self.status = AppointmentStatus.NO_SHOW
        self.touch()

    def reschedule(self, new_date: date, new_time: time) -> None:
        """Reschedule the appointment."""
        if self.status not in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]:
            if not self.status.is_active():
                raise InvalidOperationException(
                    operation="reschedule",
                    current_state=self.status.value,
                )

        self.appointment_date = new_date
        self.start_time = new_time
        # Recalculate end time
        start_dt = datetime.combine(new_date, new_time)
        end_dt = start_dt + timedelta(minutes=self.duration_minutes)
        self.end_time = end_dt.time()

        self.status = AppointmentStatus.SCHEDULED
        self.touch()

    # Medical Information

    def add_symptom(self, symptom: str) -> None:
        """Add a symptom to the appointment."""
        if symptom not in self.symptoms:
            self.symptoms.append(symptom)
            self.touch()

    def add_prescription(self, prescription: str) -> None:
        """Add a prescription."""
        self.prescriptions.append(prescription)
        self.touch()

    def set_triage_priority(self, priority: TriagePriority) -> None:
        """Set triage priority."""
        self.triage_priority = priority
        if priority in [TriagePriority.RESUSCITATION, TriagePriority.EMERGENT]:
            self.is_emergency = True
        self.touch()

    # Reminders

    def mark_reminder_sent(self) -> None:
        """Mark that reminder was sent."""
        self.reminder_sent = True
        self.reminder_sent_at = datetime.now(UTC)
        self.touch()

    def needs_reminder(self, hours_before: int = 24) -> bool:
        """Check if appointment needs a reminder."""
        if self.reminder_sent:
            return False
        if not self.status.is_active():
            return False
        if self.datetime_start is None:
            return False

        now = datetime.now(UTC)
        reminder_time = self.datetime_start - timedelta(hours=hours_before)
        return now >= reminder_time and now < self.datetime_start

    # Telemedicine

    def setup_telemedicine(self, video_url: str) -> None:
        """Setup telemedicine appointment."""
        self.is_telemedicine = True
        self.video_call_url = video_url
        self.touch()

    # Conflict Detection

    def conflicts_with(self, other: "Appointment") -> bool:
        """Check if appointment conflicts with another."""
        if self.appointment_date != other.appointment_date:
            return False
        if self.doctor_id != other.doctor_id:
            return False

        # Check time overlap
        if self.start_time is None or other.start_time is None:
            return False
        if self.end_time is None or other.end_time is None:
            return False

        return not (self.end_time <= other.start_time or self.start_time >= other.end_time)

    # Helpers

    def can_be_modified(self) -> bool:
        """Check if appointment can be modified."""
        return self.status.is_active()

    def get_wait_time_minutes(self) -> int | None:
        """Get wait time for emergency appointments."""
        if self.triage_priority is None:
            return None
        return self.triage_priority.get_max_wait_minutes()

    def get_formatted_datetime(self) -> str:
        """Get formatted date and time string."""
        if self.appointment_date and self.start_time:
            return f"{self.appointment_date.strftime('%d/%m/%Y')} {self.start_time.strftime('%H:%M')}"
        return "Sin programar"

    # Serialization

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "id": self.id,
            "patient_name": self.patient_name,
            "doctor_name": self.doctor_name,
            "date": self.appointment_date.isoformat() if self.appointment_date else None,
            "time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "specialty": self.specialty.value,
            "status": self.status.value,
            "is_emergency": self.is_emergency,
            "is_telemedicine": self.is_telemedicine,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """Convert to detailed dictionary."""
        return {
            **self.to_summary_dict(),
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "duration_minutes": self.duration_minutes,
            "appointment_type": self.appointment_type,
            "reason": self.reason,
            "symptoms": self.symptoms,
            "location": self.location,
            "video_call_url": self.video_call_url if self.is_telemedicine else None,
            "triage_priority": self.triage_priority.value if self.triage_priority else None,
            "notes": self.notes,
            "diagnosis": self.diagnosis,
        }

    def to_chat_context(self) -> dict[str, Any]:
        """Convert to chat context for agent conversations."""
        return {
            "appointment_id": self.id,
            "doctor": self.doctor_name,
            "specialty": self.specialty.value.replace("_", " ").title(),
            "datetime": self.get_formatted_datetime(),
            "status": self.status.value,
            "is_emergency": self.is_emergency,
        }

    @classmethod
    def create_consultation(
        cls,
        patient_id: int,
        patient_name: str,
        doctor_id: int,
        doctor_name: str,
        appointment_date: date,
        start_time: time,
        specialty: DoctorSpecialty,
        reason: str | None = None,
    ) -> "Appointment":
        """Factory method to create a consultation appointment."""
        return cls(
            patient_id=patient_id,
            patient_name=patient_name,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            appointment_date=appointment_date,
            start_time=start_time,
            specialty=specialty,
            appointment_type="consultation",
            reason=reason,
        )

    @classmethod
    def create_emergency(
        cls,
        patient_id: int,
        patient_name: str,
        priority: TriagePriority,
        symptoms: list[str] | None = None,
    ) -> "Appointment":
        """Factory method to create an emergency appointment."""
        appointment = cls(
            patient_id=patient_id,
            patient_name=patient_name,
            appointment_date=date.today(),
            start_time=datetime.now(UTC).time(),
            appointment_type="emergency",
            is_emergency=True,
            triage_priority=priority,
            specialty=DoctorSpecialty.EMERGENCY,
        )
        if symptoms:
            appointment.symptoms = symptoms
        return appointment
