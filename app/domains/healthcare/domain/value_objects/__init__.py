"""
Healthcare Domain Value Objects

Immutable value objects for the healthcare domain.
"""

from app.domains.healthcare.domain.value_objects.appointment_status import (
    AppointmentStatus,
    DoctorSpecialty,
    MedicalRecordType,
    PatientStatus,
    TimeSlot,
    TriagePriority,
    VitalSigns,
)

__all__ = [
    "AppointmentStatus",
    "PatientStatus",
    "TriagePriority",
    "MedicalRecordType",
    "DoctorSpecialty",
    "TimeSlot",
    "VitalSigns",
]
