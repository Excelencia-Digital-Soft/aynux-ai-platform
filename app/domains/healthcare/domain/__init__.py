"""
Healthcare Domain Layer

This module contains the core business logic for the Healthcare bounded context,
following Domain-Driven Design (DDD) principles.

Components:
- Entities: Patient, Doctor, Appointment (Aggregate Roots with business logic)
- Value Objects: AppointmentStatus, VitalSigns, TimeSlot, DoctorSpecialty
- Domain Services: SchedulingService (complex scheduling logic)
"""

from app.domains.healthcare.domain.entities import (
    Appointment,
    Doctor,
    EmergencyContact,
    Insurance,
    Patient,
    WeeklySchedule,
)
from app.domains.healthcare.domain.services import (
    AvailableSlot,
    SchedulingResult,
    SchedulingService,
)
from app.domains.healthcare.domain.value_objects import (
    AppointmentStatus,
    DoctorSpecialty,
    MedicalRecordType,
    PatientStatus,
    TimeSlot,
    TriagePriority,
    VitalSigns,
)

__all__ = [
    # Entities
    "Patient",
    "EmergencyContact",
    "Insurance",
    "Doctor",
    "WeeklySchedule",
    "Appointment",
    # Value Objects
    "AppointmentStatus",
    "PatientStatus",
    "TriagePriority",
    "MedicalRecordType",
    "DoctorSpecialty",
    "TimeSlot",
    "VitalSigns",
    # Services
    "SchedulingService",
    "AvailableSlot",
    "SchedulingResult",
]
