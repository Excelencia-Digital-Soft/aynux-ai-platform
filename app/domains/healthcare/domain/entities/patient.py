"""
Patient Entity for Healthcare Domain

Represents a patient with medical history and contact information.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from app.core.domain import Address, AggregateRoot, Email, PhoneNumber

from ..value_objects.appointment_status import PatientStatus, VitalSigns


@dataclass
class EmergencyContact:
    """Emergency contact information."""

    name: str
    relationship: str
    phone: str
    email: str | None = None


@dataclass
class Insurance:
    """Insurance information."""

    provider: str
    policy_number: str
    group_number: str | None = None
    valid_until: date | None = None

    def is_valid(self) -> bool:
        """Check if insurance is currently valid."""
        if self.valid_until is None:
            return True
        return self.valid_until >= date.today()


@dataclass
class Patient(AggregateRoot[int]):
    """
    Patient aggregate root for healthcare domain.

    Manages patient demographics, medical history, and appointments.

    Example:
        ```python
        patient = Patient(
            first_name="María",
            last_name="García",
            date_of_birth=date(1985, 3, 15),
            phone=PhoneNumber("1155551234"),
        )
        patient.add_allergy("Penicillin")
        patient.record_vital_signs(VitalSigns(heart_rate=72, temperature=36.5))
        ```
    """

    # Personal information
    first_name: str = ""
    last_name: str = ""
    date_of_birth: date | None = None
    gender: str | None = None  # "M", "F", "O"
    national_id: str | None = None  # DNI

    # Contact information
    email: Email | None = None
    phone: PhoneNumber | None = None
    address: Address | None = None
    emergency_contact: EmergencyContact | None = None

    # Medical information
    blood_type: str | None = None  # A+, A-, B+, B-, AB+, AB-, O+, O-
    allergies: list[str] = field(default_factory=list)
    chronic_conditions: list[str] = field(default_factory=list)
    current_medications: list[str] = field(default_factory=list)

    # Insurance
    insurance: Insurance | None = None

    # Status
    status: PatientStatus = PatientStatus.ACTIVE

    # Recent vitals
    last_vital_signs: VitalSigns | None = None
    last_vitals_date: datetime | None = None

    # Metadata
    medical_record_number: str | None = None  # MRN/HC
    notes: str | None = None

    def __post_init__(self):
        """Validate patient after initialization."""
        if not self.first_name:
            raise ValueError("Patient first name is required")

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self) -> int | None:
        """Calculate age from date of birth."""
        if self.date_of_birth is None:
            return None
        today = date.today()
        age = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            age -= 1
        return age

    @property
    def is_minor(self) -> bool:
        """Check if patient is a minor (<18 years)."""
        age = self.age
        return age is not None and age < 18

    # Medical Information Management

    def add_allergy(self, allergy: str) -> None:
        """Add an allergy to patient record."""
        if allergy not in self.allergies:
            self.allergies.append(allergy)
            self.touch()

    def remove_allergy(self, allergy: str) -> bool:
        """Remove an allergy from record."""
        if allergy in self.allergies:
            self.allergies.remove(allergy)
            self.touch()
            return True
        return False

    def has_allergy(self, substance: str) -> bool:
        """Check if patient has a specific allergy."""
        return substance.lower() in [a.lower() for a in self.allergies]

    def add_chronic_condition(self, condition: str) -> None:
        """Add a chronic condition."""
        if condition not in self.chronic_conditions:
            self.chronic_conditions.append(condition)
            self.touch()

    def add_medication(self, medication: str) -> None:
        """Add current medication."""
        if medication not in self.current_medications:
            self.current_medications.append(medication)
            self.touch()

    def remove_medication(self, medication: str) -> bool:
        """Remove a medication."""
        if medication in self.current_medications:
            self.current_medications.remove(medication)
            self.touch()
            return True
        return False

    def record_vital_signs(self, vitals: VitalSigns) -> None:
        """Record new vital signs."""
        self.last_vital_signs = vitals
        self.last_vitals_date = datetime.now(UTC)
        self.touch()

    # Insurance Management

    def update_insurance(self, insurance: Insurance) -> None:
        """Update insurance information."""
        self.insurance = insurance
        self.touch()

    def has_valid_insurance(self) -> bool:
        """Check if patient has valid insurance."""
        return self.insurance is not None and self.insurance.is_valid()

    # Status Management

    def activate(self) -> None:
        """Activate patient record."""
        self.status = PatientStatus.ACTIVE
        self.touch()

    def deactivate(self) -> None:
        """Deactivate patient record."""
        self.status = PatientStatus.INACTIVE
        self.touch()

    def mark_transferred(self, facility: str | None = None) -> None:
        """Mark patient as transferred."""
        self.status = PatientStatus.TRANSFERRED
        if facility:
            self.notes = f"Transferred to: {facility}"
        self.touch()

    def is_active(self) -> bool:
        """Check if patient record is active."""
        return self.status == PatientStatus.ACTIVE

    # Emergency Contact

    def set_emergency_contact(
        self,
        name: str,
        relationship: str,
        phone: str,
        email: str | None = None,
    ) -> None:
        """Set emergency contact."""
        self.emergency_contact = EmergencyContact(
            name=name,
            relationship=relationship,
            phone=phone,
            email=email,
        )
        self.touch()

    # Risk Assessment

    def needs_urgent_attention(self) -> bool:
        """Check if patient needs urgent attention based on vitals."""
        if self.last_vital_signs is None:
            return False
        return self.last_vital_signs.is_critical()

    # Serialization

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "age": self.age,
            "gender": self.gender,
            "phone": str(self.phone) if self.phone else None,
            "medical_record_number": self.medical_record_number,
            "status": self.status.value,
            "has_insurance": self.has_valid_insurance(),
        }

    def to_medical_dict(self) -> dict[str, Any]:
        """Convert to medical information dictionary."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "blood_type": self.blood_type,
            "allergies": self.allergies,
            "chronic_conditions": self.chronic_conditions,
            "current_medications": self.current_medications,
            "last_vitals": self.last_vital_signs.to_dict() if self.last_vital_signs else None,
            "emergency_contact": {
                "name": self.emergency_contact.name,
                "phone": self.emergency_contact.phone,
            }
            if self.emergency_contact
            else None,
        }

    def to_chat_context(self) -> dict[str, Any]:
        """Convert to chat context for agent conversations."""
        return {
            "patient_id": self.id,
            "name": self.first_name or self.full_name,
            "age": self.age,
            "allergies": self.allergies[:3] if self.allergies else [],  # Limit for chat
            "has_chronic_conditions": bool(self.chronic_conditions),
            "is_minor": self.is_minor,
        }
