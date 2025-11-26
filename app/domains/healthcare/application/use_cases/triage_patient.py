"""
Triage Patient Use Case

Use case for emergency triage assessment.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass
from datetime import date, time
from datetime import datetime, UTC

from app.core.domain import EntityNotFoundException
from app.domains.healthcare.application.ports.appointment_repository import IAppointmentRepository
from app.domains.healthcare.application.ports.patient_repository import IPatientRepository
from app.domains.healthcare.domain.entities.appointment import Appointment
from app.domains.healthcare.domain.entities.patient import Patient
from app.domains.healthcare.domain.value_objects.appointment_status import (
    TriagePriority,
    VitalSigns,
)

logger = logging.getLogger(__name__)


@dataclass
class TriagePatientRequest:
    """Request for patient triage."""

    patient_id: int
    symptoms: list[str]
    vital_signs: VitalSigns | None = None
    chief_complaint: str | None = None
    pain_level: int | None = None  # 1-10 scale


@dataclass
class TriagePatientResponse:
    """Response from triage assessment."""

    success: bool
    priority: TriagePriority | None = None
    wait_time_minutes: int | None = None
    emergency_appointment: Appointment | None = None
    recommendations: list[str] | None = None
    error: str | None = None


class TriagePatientUseCase:
    """
    Use case for emergency triage.

    Assesses patient urgency and creates emergency appointment if needed.
    """

    # Symptom severity mapping
    CRITICAL_SYMPTOMS = [
        "chest pain",
        "difficulty breathing",
        "severe bleeding",
        "unconscious",
        "stroke symptoms",
        "severe allergic reaction",
        "heart attack",
    ]

    EMERGENT_SYMPTOMS = [
        "high fever",
        "severe pain",
        "broken bone",
        "deep cut",
        "severe headache",
        "seizure",
    ]

    def __init__(
        self,
        patient_repository: IPatientRepository,
        appointment_repository: IAppointmentRepository,
    ):
        """
        Initialize use case.

        Args:
            patient_repository: Repository for patient data
            appointment_repository: Repository for appointments
        """
        self.patient_repo = patient_repository
        self.appointment_repo = appointment_repository

    async def execute(self, request: TriagePatientRequest) -> TriagePatientResponse:
        """
        Execute triage assessment.

        Args:
            request: Triage request

        Returns:
            Triage response with priority and recommendations
        """
        try:
            # 1. Get patient
            patient = await self.patient_repo.find_by_id(request.patient_id)
            if not patient:
                raise EntityNotFoundException(
                    entity_type="Patient",
                    entity_id=request.patient_id,
                )

            # 2. Record vital signs if provided
            if request.vital_signs:
                patient.record_vital_signs(request.vital_signs)
                await self.patient_repo.save(patient)

            # 3. Assess priority
            priority = self._assess_priority(
                symptoms=request.symptoms,
                vital_signs=request.vital_signs,
                pain_level=request.pain_level,
                patient=patient,
            )

            # 4. Get wait time
            wait_time = priority.get_max_wait_minutes()

            # 5. Create emergency appointment for high priority
            emergency_appointment = None
            if priority in [TriagePriority.RESUSCITATION, TriagePriority.EMERGENT, TriagePriority.URGENT]:
                emergency_appointment = await self._create_emergency_appointment(
                    patient=patient,
                    priority=priority,
                    symptoms=request.symptoms,
                    chief_complaint=request.chief_complaint,
                )

            # 6. Generate recommendations
            recommendations = self._generate_recommendations(
                priority=priority,
                patient=patient,
                vital_signs=request.vital_signs,
            )

            logger.info(
                f"Triage completed for patient {patient.id}: "
                f"Priority={priority.value}, Wait time={wait_time}min"
            )

            return TriagePatientResponse(
                success=True,
                priority=priority,
                wait_time_minutes=wait_time,
                emergency_appointment=emergency_appointment,
                recommendations=recommendations,
            )

        except EntityNotFoundException as e:
            logger.warning(f"Entity not found: {e}")
            return TriagePatientResponse(
                success=False,
                error=str(e),
            )
        except Exception as e:
            logger.error(f"Error in triage: {e}", exc_info=True)
            return TriagePatientResponse(
                success=False,
                error=f"Triage failed: {str(e)}",
            )

    def _assess_priority(
        self,
        symptoms: list[str],
        vital_signs: VitalSigns | None,
        pain_level: int | None,
        patient: Patient,
    ) -> TriagePriority:
        """
        Assess triage priority based on symptoms and vitals.

        Args:
            symptoms: Patient symptoms
            vital_signs: Vital signs measurements
            pain_level: Pain level (1-10)
            patient: Patient record

        Returns:
            Triage priority level
        """
        # Check critical symptoms
        symptoms_lower = [s.lower() for s in symptoms]

        for critical in self.CRITICAL_SYMPTOMS:
            if any(critical in symptom for symptom in symptoms_lower):
                return TriagePriority.RESUSCITATION

        # Check vital signs
        if vital_signs and vital_signs.is_critical():
            return TriagePriority.EMERGENT

        # Check emergent symptoms
        for emergent in self.EMERGENT_SYMPTOMS:
            if any(emergent in symptom for symptom in symptoms_lower):
                return TriagePriority.EMERGENT

        # Check pain level
        if pain_level is not None:
            if pain_level >= 9:
                return TriagePriority.EMERGENT
            elif pain_level >= 7:
                return TriagePriority.URGENT
            elif pain_level >= 4:
                return TriagePriority.LESS_URGENT

        # Check patient risk factors
        if patient.is_minor or (patient.age and patient.age > 70):
            # Higher priority for children and elderly
            return TriagePriority.URGENT

        if patient.chronic_conditions:
            return TriagePriority.URGENT

        # Default to less urgent
        return TriagePriority.LESS_URGENT

    async def _create_emergency_appointment(
        self,
        patient: Patient,
        priority: TriagePriority,
        symptoms: list[str],
        chief_complaint: str | None,
    ) -> Appointment:
        """Create emergency appointment."""
        appointment = Appointment.create_emergency(
            patient_id=patient.id,
            patient_name=patient.full_name,
            priority=priority,
            symptoms=symptoms,
        )

        if chief_complaint:
            appointment.reason = chief_complaint

        saved = await self.appointment_repo.save(appointment)
        return saved

    def _generate_recommendations(
        self,
        priority: TriagePriority,
        patient: Patient,
        vital_signs: VitalSigns | None,
    ) -> list[str]:
        """Generate recommendations based on triage."""
        recommendations = []

        if priority == TriagePriority.RESUSCITATION:
            recommendations.append("Immediate medical attention required")
            recommendations.append("Patient will be seen immediately")

        elif priority == TriagePriority.EMERGENT:
            recommendations.append(f"High priority - maximum wait {priority.get_max_wait_minutes()} minutes")
            recommendations.append("Stay in waiting area, you will be called soon")

        elif priority == TriagePriority.URGENT:
            recommendations.append(f"Urgent - estimated wait {priority.get_max_wait_minutes()} minutes")
            recommendations.append("Please inform staff if symptoms worsen")

        else:
            recommendations.append(f"Estimated wait time: {priority.get_max_wait_minutes()} minutes")
            recommendations.append("Consider scheduling a regular appointment if not urgent")

        # Patient-specific recommendations
        if patient.allergies:
            recommendations.append(f"Allergies on file: {', '.join(patient.allergies[:3])}")

        if vital_signs and vital_signs.is_critical():
            recommendations.append("Vital signs indicate immediate attention needed")

        return recommendations
