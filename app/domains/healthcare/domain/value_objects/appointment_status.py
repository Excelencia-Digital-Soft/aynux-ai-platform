"""
Healthcare Domain Value Objects

Status enums and value objects for the healthcare domain.
"""

from dataclasses import dataclass
from datetime import time
from enum import Enum

from app.core.domain import StatusEnum, ValueObject


class AppointmentStatus(StatusEnum):
    """
    Appointment lifecycle states.

    Valid transitions:
    - SCHEDULED -> CONFIRMED, CANCELLED, NO_SHOW
    - CONFIRMED -> IN_PROGRESS, CANCELLED, NO_SHOW
    - IN_PROGRESS -> COMPLETED, CANCELLED
    - COMPLETED -> (terminal)
    - CANCELLED -> RESCHEDULED
    - NO_SHOW -> RESCHEDULED
    - RESCHEDULED -> SCHEDULED
    """

    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"

    _transitions: dict[str, list[str]] = {
        "scheduled": ["confirmed", "cancelled", "no_show"],
        "confirmed": ["in_progress", "cancelled", "no_show"],
        "in_progress": ["completed", "cancelled"],
        "completed": [],
        "cancelled": ["rescheduled"],
        "no_show": ["rescheduled"],
        "rescheduled": ["scheduled"],
    }

    def can_transition_to(self, new_status: "AppointmentStatus") -> bool:
        """Check if transition to new status is valid."""
        allowed = self._transitions.get(self.value, [])
        return new_status.value in allowed

    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self.value == "completed"

    def is_active(self) -> bool:
        """Check if appointment is still active."""
        return self.value in ["scheduled", "confirmed", "in_progress"]

    def can_be_cancelled(self) -> bool:
        """Check if appointment can be cancelled."""
        return self.value in ["scheduled", "confirmed", "in_progress"]


class TriagePriority(StatusEnum):
    """Emergency triage priority levels (ESI - Emergency Severity Index)."""

    RESUSCITATION = "resuscitation"  # Level 1: Immediate life-saving
    EMERGENT = "emergent"  # Level 2: High risk, severe pain
    URGENT = "urgent"  # Level 3: Potential threat to life
    LESS_URGENT = "less_urgent"  # Level 4: Non-urgent conditions
    NON_URGENT = "non_urgent"  # Level 5: Minor conditions

    def get_max_wait_minutes(self) -> int:
        """Get maximum recommended wait time in minutes."""
        wait_times = {
            "resuscitation": 0,
            "emergent": 10,
            "urgent": 30,
            "less_urgent": 60,
            "non_urgent": 120,
        }
        return wait_times.get(self.value, 60)

    def get_color_code(self) -> str:
        """Get color code for visual triage."""
        colors = {
            "resuscitation": "red",
            "emergent": "orange",
            "urgent": "yellow",
            "less_urgent": "green",
            "non_urgent": "blue",
        }
        return colors.get(self.value, "white")


class PatientStatus(StatusEnum):
    """Patient registration status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DECEASED = "deceased"
    TRANSFERRED = "transferred"


class MedicalRecordType(StatusEnum):
    """Types of medical records."""

    CONSULTATION = "consultation"
    DIAGNOSIS = "diagnosis"
    PRESCRIPTION = "prescription"
    LAB_RESULT = "lab_result"
    IMAGING = "imaging"
    PROCEDURE = "procedure"
    VACCINATION = "vaccination"
    ALLERGY = "allergy"
    VITAL_SIGNS = "vital_signs"
    NOTE = "note"


class DoctorSpecialty(StatusEnum):
    """Medical specialties."""

    GENERAL_PRACTICE = "general_practice"
    CARDIOLOGY = "cardiology"
    DERMATOLOGY = "dermatology"
    EMERGENCY = "emergency"
    ENDOCRINOLOGY = "endocrinology"
    GASTROENTEROLOGY = "gastroenterology"
    GYNECOLOGY = "gynecology"
    NEUROLOGY = "neurology"
    ONCOLOGY = "oncology"
    OPHTHALMOLOGY = "ophthalmology"
    ORTHOPEDICS = "orthopedics"
    PEDIATRICS = "pediatrics"
    PSYCHIATRY = "psychiatry"
    PULMONOLOGY = "pulmonology"
    RADIOLOGY = "radiology"
    SURGERY = "surgery"
    UROLOGY = "urology"


@dataclass(frozen=True)
class TimeSlot(ValueObject):
    """
    Time slot for appointments.

    Represents a specific time window for scheduling.
    """

    start_time: time
    end_time: time
    duration_minutes: int = 30

    def _validate(self) -> None:
        """Validate time slot constraints."""
        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time")
        if self.duration_minutes <= 0:
            raise ValueError("Duration must be positive")

    def overlaps_with(self, other: "TimeSlot") -> bool:
        """Check if time slot overlaps with another."""
        return not (self.end_time <= other.start_time or self.start_time >= other.end_time)

    def __str__(self) -> str:
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


@dataclass(frozen=True)
class VitalSigns(ValueObject):
    """
    Vital signs measurement value object.

    Contains key vital measurements for patient assessment.
    """

    heart_rate: int | None = None  # BPM
    blood_pressure_systolic: int | None = None  # mmHg
    blood_pressure_diastolic: int | None = None  # mmHg
    temperature: float | None = None  # Celsius
    respiratory_rate: int | None = None  # Breaths per minute
    oxygen_saturation: float | None = None  # Percentage
    weight: float | None = None  # kg
    height: float | None = None  # cm

    def _validate(self) -> None:
        """Validate vital signs ranges."""
        if self.heart_rate is not None and not (30 <= self.heart_rate <= 250):
            raise ValueError(f"Heart rate {self.heart_rate} out of valid range (30-250)")
        if self.oxygen_saturation is not None and not (0 <= self.oxygen_saturation <= 100):
            raise ValueError(f"Oxygen saturation {self.oxygen_saturation} out of range (0-100)")
        if self.temperature is not None and not (30 <= self.temperature <= 45):
            raise ValueError(f"Temperature {self.temperature} out of range (30-45°C)")

    @property
    def blood_pressure(self) -> str | None:
        """Get blood pressure as formatted string."""
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return None

    @property
    def bmi(self) -> float | None:
        """Calculate BMI if weight and height are available."""
        if self.weight and self.height:
            height_m = self.height / 100
            return round(self.weight / (height_m * height_m), 1)
        return None

    def is_critical(self) -> bool:
        """Check if any vital signs are in critical range."""
        critical = False
        if self.heart_rate is not None:
            critical = critical or self.heart_rate < 50 or self.heart_rate > 150
        if self.oxygen_saturation is not None:
            critical = critical or self.oxygen_saturation < 90
        if self.blood_pressure_systolic is not None:
            critical = critical or self.blood_pressure_systolic < 90 or self.blood_pressure_systolic > 180
        return critical

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "heart_rate": self.heart_rate,
            "blood_pressure": self.blood_pressure,
            "temperature": self.temperature,
            "respiratory_rate": self.respiratory_rate,
            "oxygen_saturation": self.oxygen_saturation,
            "weight": self.weight,
            "height": self.height,
            "bmi": self.bmi,
        }
