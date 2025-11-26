"""
Healthcare Domain Ports

Interfaces (ports) for healthcare domain following Clean Architecture.
"""

from app.domains.healthcare.application.ports.patient_repository import IPatientRepository
from app.domains.healthcare.application.ports.appointment_repository import IAppointmentRepository

__all__ = [
    "IPatientRepository",
    "IAppointmentRepository",
]
