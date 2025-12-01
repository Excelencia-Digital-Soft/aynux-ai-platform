"""
Doctor Entity for Healthcare Domain

Represents a medical professional with schedule and specialties.
"""

from dataclasses import dataclass, field
from datetime import time
from typing import Any

from app.core.domain import AggregateRoot, Email, PhoneNumber

from ..value_objects.appointment_status import DoctorSpecialty, TimeSlot


@dataclass
class WeeklySchedule:
    """Doctor's weekly availability schedule."""

    # Day of week (0=Monday, 6=Sunday) -> list of TimeSlots
    schedule: dict[int, list[TimeSlot]] = field(default_factory=dict)

    def add_slot(self, day: int, slot: TimeSlot) -> None:
        """Add a time slot to a specific day."""
        if day not in self.schedule:
            self.schedule[day] = []
        self.schedule[day].append(slot)

    def get_slots_for_day(self, day: int) -> list[TimeSlot]:
        """Get available slots for a specific day."""
        return self.schedule.get(day, [])

    def is_available(self, day: int, slot: TimeSlot) -> bool:
        """Check if doctor is available for a specific slot."""
        day_slots = self.get_slots_for_day(day)
        for available in day_slots:
            if slot.overlaps_with(available):
                return True
        return False


@dataclass
class Doctor(AggregateRoot[int]):
    """
    Doctor aggregate root for healthcare domain.

    Manages doctor profile, specialties, and availability.

    Example:
        ```python
        doctor = Doctor(
            first_name="Carlos",
            last_name="Rodríguez",
            specialty=DoctorSpecialty.CARDIOLOGY,
            license_number="MP-12345",
        )
        doctor.add_secondary_specialty(DoctorSpecialty.GENERAL_PRACTICE)
        doctor.set_schedule(...)
        ```
    """

    # Personal information
    first_name: str = ""
    last_name: str = ""
    email: Email | None = None
    phone: PhoneNumber | None = None

    # Professional information
    license_number: str = ""  # Matrícula
    specialty: DoctorSpecialty = DoctorSpecialty.GENERAL_PRACTICE
    secondary_specialties: list[DoctorSpecialty] = field(default_factory=list)

    # Schedule
    weekly_schedule: WeeklySchedule = field(default_factory=WeeklySchedule)
    appointment_duration_minutes: int = 30
    max_daily_appointments: int = 20

    # Status
    is_active: bool = True
    is_accepting_patients: bool = True

    # Consultation fees
    consultation_fee: float = 0.0
    currency: str = "ARS"

    # Metadata
    bio: str | None = None
    languages: list[str] = field(default_factory=lambda: ["es"])
    profile_image_url: str | None = None

    # Ratings (optional)
    rating: float = 0.0
    total_reviews: int = 0

    def __post_init__(self):
        """Validate doctor after initialization."""
        if not self.first_name:
            raise ValueError("Doctor first name is required")
        if not self.license_number:
            raise ValueError("License number is required")

    @property
    def full_name(self) -> str:
        """Get full name with title."""
        return f"Dr. {self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        """Get display name for UI."""
        specialty_display = self.specialty.value.replace("_", " ").title()
        return f"Dr. {self.last_name} - {specialty_display}"

    # Specialty Management

    def add_secondary_specialty(self, specialty: DoctorSpecialty) -> None:
        """Add a secondary specialty."""
        if specialty not in self.secondary_specialties and specialty != self.specialty:
            self.secondary_specialties.append(specialty)
            self.touch()

    def remove_secondary_specialty(self, specialty: DoctorSpecialty) -> bool:
        """Remove a secondary specialty."""
        if specialty in self.secondary_specialties:
            self.secondary_specialties.remove(specialty)
            self.touch()
            return True
        return False

    def has_specialty(self, specialty: DoctorSpecialty) -> bool:
        """Check if doctor has a specific specialty."""
        return specialty == self.specialty or specialty in self.secondary_specialties

    def get_all_specialties(self) -> list[DoctorSpecialty]:
        """Get all specialties (primary + secondary)."""
        return [self.specialty] + self.secondary_specialties

    # Schedule Management

    def set_schedule(self, schedule: WeeklySchedule) -> None:
        """Set weekly schedule."""
        self.weekly_schedule = schedule
        self.touch()

    def add_schedule_slot(self, day: int, start: time, end: time) -> None:
        """Add a time slot to schedule."""
        slot = TimeSlot(start_time=start, end_time=end, duration_minutes=self.appointment_duration_minutes)
        self.weekly_schedule.add_slot(day, slot)
        self.touch()

    def is_available_on_day(self, day: int) -> bool:
        """Check if doctor works on a specific day."""
        return len(self.weekly_schedule.get_slots_for_day(day)) > 0

    def get_available_slots(self, day: int) -> list[TimeSlot]:
        """Get available time slots for a day."""
        return self.weekly_schedule.get_slots_for_day(day)

    # Status Management

    def activate(self) -> None:
        """Activate doctor profile."""
        self.is_active = True
        self.touch()

    def deactivate(self) -> None:
        """Deactivate doctor profile."""
        self.is_active = False
        self.is_accepting_patients = False
        self.touch()

    def start_accepting_patients(self) -> None:
        """Start accepting new patients."""
        self.is_accepting_patients = True
        self.touch()

    def stop_accepting_patients(self) -> None:
        """Stop accepting new patients."""
        self.is_accepting_patients = False
        self.touch()

    def can_accept_appointments(self) -> bool:
        """Check if doctor can accept new appointments."""
        return self.is_active and self.is_accepting_patients

    # Fees

    def set_consultation_fee(self, fee: float) -> None:
        """Set consultation fee."""
        if fee < 0:
            raise ValueError("Fee cannot be negative")
        self.consultation_fee = fee
        self.touch()

    def get_formatted_fee(self) -> str:
        """Get formatted consultation fee."""
        return f"${self.consultation_fee:,.2f} {self.currency}"

    # Ratings

    def add_review(self, rating: float) -> None:
        """Add a new review and update average rating."""
        if not (1 <= rating <= 5):
            raise ValueError("Rating must be between 1 and 5")

        # Calculate new average
        total_rating = self.rating * self.total_reviews + rating
        self.total_reviews += 1
        self.rating = round(total_rating / self.total_reviews, 1)
        self.touch()

    # Serialization

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "specialty": self.specialty.value,
            "license_number": self.license_number,
            "is_active": self.is_active,
            "is_accepting_patients": self.is_accepting_patients,
            "rating": self.rating,
            "consultation_fee": self.consultation_fee,
        }

    def to_profile_dict(self) -> dict[str, Any]:
        """Convert to full profile dictionary."""
        return {
            **self.to_summary_dict(),
            "secondary_specialties": [s.value for s in self.secondary_specialties],
            "bio": self.bio,
            "languages": self.languages,
            "profile_image_url": self.profile_image_url,
            "appointment_duration_minutes": self.appointment_duration_minutes,
            "total_reviews": self.total_reviews,
        }

    def to_chat_context(self) -> dict[str, Any]:
        """Convert to chat context for agent conversations."""
        return {
            "doctor_id": self.id,
            "name": self.full_name,
            "specialty": self.specialty.value.replace("_", " ").title(),
            "accepting_patients": self.is_accepting_patients,
            "fee": self.get_formatted_fee() if self.consultation_fee > 0 else "Consultar",
        }

    @classmethod
    def create_for_specialty(
        cls,
        first_name: str,
        last_name: str,
        license_number: str,
        specialty: DoctorSpecialty,
    ) -> "Doctor":
        """Factory method to create a doctor."""
        return cls(
            first_name=first_name,
            last_name=last_name,
            license_number=license_number,
            specialty=specialty,
        )
