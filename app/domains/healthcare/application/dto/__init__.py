"""
Healthcare Application DTOs

Data Transfer Objects for the Healthcare domain.
"""

from dataclasses import dataclass, field
from datetime import datetime


# ==================== Patient DTOs ====================


@dataclass
class PatientDTO:
    """Patient data transfer object"""

    id: str
    first_name: str
    last_name: str
    date_of_birth: datetime
    gender: str
    phone: str | None
    email: str | None
    address: str | None
    insurance_id: str | None
    blood_type: str | None
    allergies: list[str] = field(default_factory=list)


@dataclass
class GetPatientRecordsRequest:
    """Request for patient records"""

    patient_id: str
    include_history: bool = True


@dataclass
class GetPatientRecordsResponse:
    """Response with patient records"""

    patient: PatientDTO | None
    medical_history: list[dict]
    recent_visits: list[dict]
    found: bool


# ==================== Appointment DTOs ====================


@dataclass
class DoctorDTO:
    """Doctor data transfer object"""

    id: str
    first_name: str
    last_name: str
    specialty: str
    phone: str | None
    email: str | None
    available_days: list[str] = field(default_factory=list)


@dataclass
class AppointmentDTO:
    """Appointment data transfer object"""

    id: str
    patient_id: str
    doctor_id: str
    scheduled_at: datetime
    duration_minutes: int
    reason: str
    status: str
    notes: str | None
    created_at: datetime


@dataclass
class BookAppointmentRequest:
    """Request to book an appointment"""

    patient_id: str
    doctor_id: str
    scheduled_at: datetime
    duration_minutes: int = 30
    reason: str = ""
    notes: str = ""


@dataclass
class BookAppointmentResponse:
    """Response after booking appointment"""

    appointment: AppointmentDTO | None
    success: bool
    message: str
    confirmation_code: str | None


@dataclass
class GetAppointmentsRequest:
    """Request for appointments"""

    patient_id: str | None = None
    doctor_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None


@dataclass
class GetAppointmentsResponse:
    """Response with appointments"""

    appointments: list[AppointmentDTO]
    total_count: int


@dataclass
class CancelAppointmentRequest:
    """Request to cancel appointment"""

    appointment_id: str
    reason: str = ""


@dataclass
class CancelAppointmentResponse:
    """Response after cancelling appointment"""

    success: bool
    message: str


# ==================== Triage DTOs ====================


@dataclass
class TriageRequest:
    """Request for triage assessment"""

    patient_id: str
    symptoms: list[str]
    pain_level: int  # 1-10
    temperature: float | None = None
    blood_pressure: str | None = None
    notes: str = ""


@dataclass
class TriageResponse:
    """Response with triage assessment"""

    priority_level: str  # emergency, urgent, standard, low
    recommended_action: str
    estimated_wait_time: int | None  # minutes
    assigned_doctor_id: str | None
    notes: str


__all__ = [
    # Patient DTOs
    "PatientDTO",
    "GetPatientRecordsRequest",
    "GetPatientRecordsResponse",
    # Doctor DTOs
    "DoctorDTO",
    # Appointment DTOs
    "AppointmentDTO",
    "BookAppointmentRequest",
    "BookAppointmentResponse",
    "GetAppointmentsRequest",
    "GetAppointmentsResponse",
    "CancelAppointmentRequest",
    "CancelAppointmentResponse",
    # Triage DTOs
    "TriageRequest",
    "TriageResponse",
]
