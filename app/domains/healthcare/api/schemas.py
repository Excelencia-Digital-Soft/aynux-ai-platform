"""
Healthcare API Schemas

Pydantic schemas for API request/response validation.
"""

from datetime import date, time

from pydantic import BaseModel, Field


class PatientResponse(BaseModel):
    """Patient response schema."""

    id: int
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    phone: str | None = None
    email: str | None = None
    medical_record_number: str | None = None

    class Config:
        from_attributes = True


class AppointmentRequest(BaseModel):
    """Appointment request schema."""

    patient_id: int
    doctor_id: int
    appointment_date: date
    start_time: time
    specialty: str
    reason: str | None = None
    duration_minutes: int = Field(default=30, ge=15, le=120)
    is_telemedicine: bool = False


class AppointmentResponse(BaseModel):
    """Appointment response schema."""

    id: int
    patient_id: int
    doctor_id: int
    appointment_date: date
    start_time: time
    end_time: time
    specialty: str
    status: str
    is_telemedicine: bool

    class Config:
        from_attributes = True


class TriageRequest(BaseModel):
    """Triage assessment request schema."""

    patient_id: int
    symptoms: list[str]
    pain_level: int | None = Field(default=None, ge=1, le=10)


class TriageResponse(BaseModel):
    """Triage assessment response schema."""

    patient_id: int
    priority: str
    wait_time_minutes: int
    recommendations: list[str]
    requires_immediate_attention: bool
    confidence_score: float


class DoctorResponse(BaseModel):
    """Doctor response schema."""

    id: int
    first_name: str
    last_name: str
    specialty: str
    license_number: str | None = None
    is_active: bool = True

    class Config:
        from_attributes = True


class AvailableSlotResponse(BaseModel):
    """Available appointment slot response schema."""

    doctor_id: int
    doctor_name: str
    date: date
    start_time: time
    end_time: time
    is_telemedicine: bool


__all__ = [
    "PatientResponse",
    "AppointmentRequest",
    "AppointmentResponse",
    "TriageRequest",
    "TriageResponse",
    "DoctorResponse",
    "AvailableSlotResponse",
]
