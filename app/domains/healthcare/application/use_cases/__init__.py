"""
Healthcare Use Cases

Application layer use cases for healthcare domain.
"""

from app.domains.healthcare.application.use_cases.book_appointment import (
    BookAppointmentRequest,
    BookAppointmentResponse,
    BookAppointmentUseCase,
)
from app.domains.healthcare.application.use_cases.get_patient_records import (
    GetPatientRecordsRequest,
    PatientRecordsResponse,
    GetPatientRecordsUseCase,
)
from app.domains.healthcare.application.use_cases.triage_patient import (
    TriagePatientRequest,
    TriagePatientResponse,
    TriagePatientUseCase,
)

__all__ = [
    # Book Appointment
    "BookAppointmentRequest",
    "BookAppointmentResponse",
    "BookAppointmentUseCase",
    # Get Patient Records
    "GetPatientRecordsRequest",
    "PatientRecordsResponse",
    "GetPatientRecordsUseCase",
    # Triage
    "TriagePatientRequest",
    "TriagePatientResponse",
    "TriagePatientUseCase",
]
