"""
Healthcare API Dependencies

FastAPI dependencies for the healthcare domain.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import DependencyContainer, get_container
from app.database.async_db import get_async_db
from app.domains.healthcare.application.use_cases import (
    BookAppointmentUseCase,
    GetPatientRecordsUseCase,
    TriagePatientUseCase,
)


def get_book_appointment_use_case(
    db: AsyncSession = Depends(get_async_db),
) -> BookAppointmentUseCase:
    """Get BookAppointmentUseCase instance with database session."""
    container = get_container()
    return container.create_book_appointment_use_case(db)


def get_patient_records_use_case(
    db: AsyncSession = Depends(get_async_db),
) -> GetPatientRecordsUseCase:
    """Get GetPatientRecordsUseCase instance with database session."""
    container = get_container()
    return container.create_get_patient_records_use_case(db)


def get_triage_patient_use_case(
    db: AsyncSession = Depends(get_async_db),
) -> TriagePatientUseCase:
    """Get TriagePatientUseCase instance with database session."""
    container = get_container()
    return container.create_triage_patient_use_case(db)


__all__ = [
    "get_book_appointment_use_case",
    "get_patient_records_use_case",
    "get_triage_patient_use_case",
]
