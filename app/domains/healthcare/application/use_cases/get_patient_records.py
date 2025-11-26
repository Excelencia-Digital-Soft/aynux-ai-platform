"""
Get Patient Records Use Case

Use case for retrieving patient information and medical history.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.domain import EntityNotFoundException
from app.domains.healthcare.application.ports.appointment_repository import IAppointmentRepository
from app.domains.healthcare.application.ports.patient_repository import IPatientRepository
from app.domains.healthcare.domain.entities.patient import Patient
from app.domains.healthcare.domain.entities.appointment import Appointment

logger = logging.getLogger(__name__)


@dataclass
class GetPatientRecordsRequest:
    """Request for getting patient records."""

    patient_id: int | None = None
    phone: str | None = None
    national_id: str | None = None
    medical_record_number: str | None = None
    include_appointments: bool = True
    include_medical_history: bool = True
    appointments_limit: int = 10


@dataclass
class PatientRecordsResponse:
    """Response containing patient records."""

    success: bool
    patient: Patient | None = None
    appointments: list[Appointment] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class GetPatientRecordsUseCase:
    """
    Use case for retrieving patient records.

    Single Responsibility: Only handles patient record retrieval
    Dependency Inversion: Depends on interfaces, not implementations
    """

    def __init__(
        self,
        patient_repository: IPatientRepository,
        appointment_repository: IAppointmentRepository | None = None,
    ):
        """
        Initialize use case with dependencies.

        Args:
            patient_repository: Repository for patient data
            appointment_repository: Optional repository for appointments
        """
        self.patient_repo = patient_repository
        self.appointment_repo = appointment_repository

    async def execute(self, request: GetPatientRecordsRequest) -> PatientRecordsResponse:
        """
        Execute patient records retrieval.

        Args:
            request: Request parameters

        Returns:
            Response with patient records
        """
        try:
            # 1. Find patient by various identifiers
            patient = await self._find_patient(request)

            if not patient:
                return PatientRecordsResponse(
                    success=False,
                    error="Patient not found",
                )

            # 2. Get appointments if requested
            appointments: list[Appointment] = []
            if request.include_appointments and self.appointment_repo:
                appointments = await self.appointment_repo.find_by_patient(
                    patient_id=patient.id,
                    include_past=True,
                    limit=request.appointments_limit,
                )

            # 3. Build summary
            summary = self._build_summary(patient, appointments, request.include_medical_history)

            logger.info(f"Retrieved records for patient {patient.id}: {patient.full_name}")

            return PatientRecordsResponse(
                success=True,
                patient=patient,
                appointments=appointments,
                summary=summary,
            )

        except EntityNotFoundException as e:
            logger.warning(f"Patient not found: {e}")
            return PatientRecordsResponse(
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Error retrieving patient records: {e}", exc_info=True)
            return PatientRecordsResponse(
                success=False,
                error=f"Failed to retrieve records: {str(e)}",
            )

    async def _find_patient(self, request: GetPatientRecordsRequest) -> Patient | None:
        """Find patient using available identifiers."""
        if request.patient_id:
            return await self.patient_repo.find_by_id(request.patient_id)
        elif request.phone:
            return await self.patient_repo.find_by_phone(request.phone)
        elif request.national_id:
            return await self.patient_repo.find_by_national_id(request.national_id)
        elif request.medical_record_number:
            return await self.patient_repo.find_by_medical_record_number(request.medical_record_number)
        return None

    def _build_summary(
        self,
        patient: Patient,
        appointments: list[Appointment],
        include_medical: bool,
    ) -> dict[str, Any]:
        """Build patient summary dictionary."""
        summary: dict[str, Any] = {
            "patient_id": patient.id,
            "full_name": patient.full_name,
            "age": patient.age,
            "status": patient.status.value,
            "has_valid_insurance": patient.has_valid_insurance(),
        }

        if include_medical:
            summary["medical"] = {
                "blood_type": patient.blood_type,
                "allergies_count": len(patient.allergies),
                "chronic_conditions_count": len(patient.chronic_conditions),
                "current_medications_count": len(patient.current_medications),
                "needs_urgent_attention": patient.needs_urgent_attention(),
            }

        if appointments:
            upcoming = [a for a in appointments if a.is_upcoming]
            past = [a for a in appointments if a.is_past]

            summary["appointments"] = {
                "total": len(appointments),
                "upcoming_count": len(upcoming),
                "past_count": len(past),
                "next_appointment": upcoming[0].to_summary_dict() if upcoming else None,
            }

        return summary
