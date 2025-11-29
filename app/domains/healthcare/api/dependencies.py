"""
Healthcare API Dependencies

FastAPI dependencies for the healthcare domain.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import get_container
from app.database.async_db import get_async_db
from app.domains.healthcare.application.use_cases import (
    BookAppointmentUseCase,
    GetPatientRecordsUseCase,
    TriagePatientUseCase,
)

# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_async_db)]


def get_book_appointment_use_case(db: DbSession) -> BookAppointmentUseCase:
    """Get BookAppointmentUseCase instance with database session."""
    container = get_container()
    return container.create_book_appointment_use_case(db)


def get_patient_records_use_case(db: DbSession) -> GetPatientRecordsUseCase:
    """Get GetPatientRecordsUseCase instance with database session."""
    container = get_container()
    return container.create_get_patient_records_use_case(db)


def get_triage_patient_use_case(db: DbSession) -> TriagePatientUseCase:
    """Get TriagePatientUseCase instance with database session."""
    container = get_container()
    return container.create_triage_patient_use_case(db)


__all__ = [
    "get_book_appointment_use_case",
    "get_patient_records_use_case",
    "get_triage_patient_use_case",
]
