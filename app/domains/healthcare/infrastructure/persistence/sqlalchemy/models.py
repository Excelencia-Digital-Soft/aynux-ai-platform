"""
Healthcare SQLAlchemy Models

Database models for healthcare domain persistence.
"""

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database.setup import Base
from app.domains.healthcare.domain.value_objects.appointment_status import (
    AppointmentStatus,
    DoctorSpecialty,
    PatientStatus,
    TriagePriority,
)


class PatientModel(Base):
    """SQLAlchemy model for Patient entity."""

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)

    # Personal information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(1), nullable=True)  # M, F, O
    national_id = Column(String(20), unique=True, nullable=True, index=True)

    # Contact information
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    address_street = Column(String(255), nullable=True)
    address_city = Column(String(100), nullable=True)
    address_state = Column(String(100), nullable=True)
    address_postal_code = Column(String(20), nullable=True)
    address_country = Column(String(100), default="Argentina")

    # Emergency contact
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_relationship = Column(String(50), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    emergency_contact_email = Column(String(255), nullable=True)

    # Medical information
    blood_type = Column(String(5), nullable=True)
    allergies = Column(JSON, default=list)
    chronic_conditions = Column(JSON, default=list)
    current_medications = Column(JSON, default=list)

    # Insurance
    insurance_provider = Column(String(100), nullable=True)
    insurance_policy_number = Column(String(50), nullable=True)
    insurance_group_number = Column(String(50), nullable=True)
    insurance_valid_until = Column(Date, nullable=True)

    # Status
    status = Column(
        SQLEnum(PatientStatus),
        default=PatientStatus.ACTIVE,
        nullable=False,
    )

    # Vitals
    last_vitals = Column(JSON, nullable=True)
    last_vitals_date = Column(DateTime, nullable=True)

    # Metadata
    medical_record_number = Column(String(50), unique=True, nullable=True, index=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointments = relationship("AppointmentModel", back_populates="patient")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": f"{self.first_name} {self.last_name}",
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "gender": self.gender,
            "national_id": self.national_id,
            "email": self.email,
            "phone": self.phone,
            "blood_type": self.blood_type,
            "allergies": self.allergies or [],
            "status": self.status.value if self.status else None,
            "medical_record_number": self.medical_record_number,
        }


class DoctorModel(Base):
    """SQLAlchemy model for Doctor entity."""

    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)

    # Personal information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    national_id = Column(String(20), unique=True, nullable=True)

    # Professional information
    license_number = Column(String(50), unique=True, nullable=False, index=True)
    specialty = Column(
        SQLEnum(DoctorSpecialty),
        default=DoctorSpecialty.GENERAL_PRACTICE,
        nullable=False,
    )
    secondary_specialties = Column(JSON, default=list)

    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)

    # Schedule
    working_days = Column(JSON, default=list)  # ["monday", "tuesday", ...]
    working_hours_start = Column(Time, nullable=True)
    working_hours_end = Column(Time, nullable=True)
    appointment_duration_minutes = Column(Integer, default=30)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointments = relationship("AppointmentModel", back_populates="doctor")

    @property
    def full_name(self) -> str:
        """Get full name with title."""
        return f"Dr. {self.first_name} {self.last_name}"


class AppointmentModel(Base):
    """SQLAlchemy model for Appointment entity."""

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)

    # References
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True, index=True)
    patient_name = Column(String(200), nullable=True)
    doctor_name = Column(String(200), nullable=True)

    # Scheduling
    appointment_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=True)
    duration_minutes = Column(Integer, default=30)

    # Type
    specialty = Column(
        SQLEnum(DoctorSpecialty),
        default=DoctorSpecialty.GENERAL_PRACTICE,
        nullable=False,
    )
    appointment_type = Column(String(50), default="consultation")
    is_emergency = Column(Boolean, default=False)
    triage_priority = Column(SQLEnum(TriagePriority), nullable=True)

    # Status
    status = Column(
        SQLEnum(AppointmentStatus),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    # Location
    location = Column(String(100), nullable=True)
    is_telemedicine = Column(Boolean, default=False)
    video_call_url = Column(String(500), nullable=True)

    # Medical information
    reason = Column(Text, nullable=True)
    symptoms = Column(JSON, default=list)
    notes = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    prescriptions = Column(JSON, default=list)

    # Reminders
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime, nullable=True)

    # Timestamps
    confirmed_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    cancelled_by = Column(String(50), nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("PatientModel", back_populates="appointments")
    doctor = relationship("DoctorModel", back_populates="appointments")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "doctor_id": self.doctor_id,
            "doctor_name": self.doctor_name,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "specialty": self.specialty.value if self.specialty else None,
            "status": self.status.value if self.status else None,
            "is_emergency": self.is_emergency,
            "is_telemedicine": self.is_telemedicine,
            "reason": self.reason,
        }
