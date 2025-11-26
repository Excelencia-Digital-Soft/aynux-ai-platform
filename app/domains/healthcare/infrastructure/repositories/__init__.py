"""
Healthcare Infrastructure Repositories

Repository implementations for healthcare domain.
"""

from app.domains.healthcare.infrastructure.repositories.patient_repository import (
    SQLAlchemyPatientRepository,
)
from app.domains.healthcare.infrastructure.repositories.appointment_repository import (
    SQLAlchemyAppointmentRepository,
)

__all__ = [
    "SQLAlchemyPatientRepository",
    "SQLAlchemyAppointmentRepository",
]
