"""
Healthcare Domain Container.

Single Responsibility: Wire all healthcare domain dependencies.
"""

import logging
from typing import TYPE_CHECKING

from app.domains.healthcare.application.use_cases import (
    BookAppointmentUseCase,
    GetPatientRecordsUseCase,
    TriagePatientUseCase,
)
from app.domains.healthcare.infrastructure.repositories import (
    SQLAlchemyAppointmentRepository,
    SQLAlchemyDoctorRepository,
    SQLAlchemyPatientRepository,
)

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class HealthcareContainer:
    """
    Healthcare domain container.

    Single Responsibility: Create healthcare repositories and use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize healthcare container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    # ==================== REPOSITORIES ====================

    def create_patient_repository(self, db) -> SQLAlchemyPatientRepository:
        """Create Patient Repository."""
        return SQLAlchemyPatientRepository(session=db)

    def create_appointment_repository(self, db) -> SQLAlchemyAppointmentRepository:
        """Create Appointment Repository."""
        return SQLAlchemyAppointmentRepository(session=db)

    def create_doctor_repository(self, db) -> SQLAlchemyDoctorRepository:
        """Create Doctor Repository."""
        return SQLAlchemyDoctorRepository(session=db)

    # ==================== USE CASES ====================

    def create_book_appointment_use_case(self, db) -> BookAppointmentUseCase:
        """Create BookAppointmentUseCase with dependencies."""
        return BookAppointmentUseCase(
            patient_repository=self.create_patient_repository(db),
            appointment_repository=self.create_appointment_repository(db),
        )

    def create_get_patient_records_use_case(self, db) -> GetPatientRecordsUseCase:
        """Create GetPatientRecordsUseCase with dependencies."""
        return GetPatientRecordsUseCase(
            patient_repository=self.create_patient_repository(db),
            appointment_repository=self.create_appointment_repository(db),
        )

    def create_triage_patient_use_case(self, db) -> TriagePatientUseCase:
        """Create TriagePatientUseCase with dependencies."""
        return TriagePatientUseCase(
            patient_repository=self.create_patient_repository(db),
            appointment_repository=self.create_appointment_repository(db),
        )
