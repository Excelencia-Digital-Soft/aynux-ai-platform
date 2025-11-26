"""
Triage Domain Service

Domain service for emergency triage assessment.
"""

from dataclasses import dataclass
from typing import Any

from app.domains.healthcare.domain.entities.patient import Patient
from app.domains.healthcare.domain.value_objects.appointment_status import (
    TriagePriority,
    VitalSigns,
)


@dataclass
class TriageAssessment:
    """Result of triage assessment."""

    priority: TriagePriority
    wait_time_minutes: int
    recommendations: list[str]
    requires_immediate_attention: bool
    confidence_score: float
    assessment_factors: dict[str, Any]


class TriageService:
    """
    Domain service for emergency triage.

    Assesses patient urgency based on symptoms and vital signs.

    Example:
        ```python
        service = TriageService()

        assessment = service.assess(
            symptoms=["chest pain", "shortness of breath"],
            vital_signs=VitalSigns(heart_rate=120, blood_pressure_systolic=180),
            patient=patient,
        )

        print(f"Priority: {assessment.priority}")
        print(f"Wait time: {assessment.wait_time_minutes} minutes")
        ```
    """

    # Critical symptoms requiring immediate attention
    CRITICAL_SYMPTOMS = {
        "chest pain": 1.0,
        "difficulty breathing": 1.0,
        "severe bleeding": 1.0,
        "unconscious": 1.0,
        "stroke symptoms": 1.0,
        "severe allergic reaction": 1.0,
        "heart attack": 1.0,
        "seizure": 0.9,
        "severe trauma": 0.9,
    }

    # Emergent symptoms requiring quick attention
    EMERGENT_SYMPTOMS = {
        "high fever": 0.7,
        "severe pain": 0.7,
        "broken bone": 0.7,
        "deep cut": 0.7,
        "severe headache": 0.7,
        "vomiting blood": 0.8,
        "severe abdominal pain": 0.7,
    }

    # Urgent symptoms
    URGENT_SYMPTOMS = {
        "moderate pain": 0.5,
        "persistent vomiting": 0.5,
        "high blood pressure": 0.5,
        "moderate fever": 0.4,
        "infection": 0.5,
    }

    def assess(
        self,
        symptoms: list[str],
        vital_signs: VitalSigns | None = None,
        patient: Patient | None = None,
        pain_level: int | None = None,
    ) -> TriageAssessment:
        """
        Assess triage priority.

        Args:
            symptoms: List of patient symptoms
            vital_signs: Vital sign measurements
            patient: Patient record (for risk factors)
            pain_level: Pain level 1-10

        Returns:
            TriageAssessment with priority and recommendations
        """
        assessment_factors: dict[str, Any] = {
            "symptom_scores": {},
            "vitals_critical": False,
            "pain_factor": 0.0,
            "risk_factors": [],
        }

        # Calculate symptom severity score
        symptom_score = 0.0
        symptoms_lower = [s.lower() for s in symptoms]

        for symptom in symptoms_lower:
            # Check critical symptoms
            for critical, weight in self.CRITICAL_SYMPTOMS.items():
                if critical in symptom:
                    symptom_score = max(symptom_score, weight)
                    assessment_factors["symptom_scores"][critical] = weight

            # Check emergent symptoms
            for emergent, weight in self.EMERGENT_SYMPTOMS.items():
                if emergent in symptom:
                    symptom_score = max(symptom_score, weight)
                    assessment_factors["symptom_scores"][emergent] = weight

            # Check urgent symptoms
            for urgent, weight in self.URGENT_SYMPTOMS.items():
                if urgent in symptom:
                    symptom_score = max(symptom_score, weight * 0.7)
                    assessment_factors["symptom_scores"][urgent] = weight

        # Evaluate vital signs
        vitals_score = 0.0
        if vital_signs:
            if vital_signs.is_critical():
                vitals_score = 0.9
                assessment_factors["vitals_critical"] = True

            # Check specific vitals
            if vital_signs.oxygen_saturation and vital_signs.oxygen_saturation < 90:
                vitals_score = max(vitals_score, 0.95)
            if vital_signs.heart_rate and (vital_signs.heart_rate > 150 or vital_signs.heart_rate < 50):
                vitals_score = max(vitals_score, 0.8)
            if vital_signs.blood_pressure_systolic and vital_signs.blood_pressure_systolic > 180:
                vitals_score = max(vitals_score, 0.75)

        # Evaluate pain level
        pain_score = 0.0
        if pain_level is not None:
            assessment_factors["pain_factor"] = pain_level / 10.0
            if pain_level >= 9:
                pain_score = 0.8
            elif pain_level >= 7:
                pain_score = 0.6
            elif pain_level >= 5:
                pain_score = 0.4

        # Evaluate patient risk factors
        risk_score = 0.0
        if patient:
            # Age risk
            if patient.age and (patient.age < 2 or patient.age > 70):
                risk_score += 0.1
                assessment_factors["risk_factors"].append("age")

            # Chronic conditions
            if patient.chronic_conditions:
                risk_score += min(len(patient.chronic_conditions) * 0.05, 0.2)
                assessment_factors["risk_factors"].append("chronic_conditions")

            # Allergies (if relevant to symptoms)
            if patient.allergies:
                assessment_factors["risk_factors"].append("has_allergies")

        # Calculate final score
        final_score = max(symptom_score, vitals_score, pain_score) + risk_score

        # Determine priority
        priority = self._score_to_priority(final_score)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            priority=priority,
            symptoms=symptoms,
            vital_signs=vital_signs,
            patient=patient,
        )

        return TriageAssessment(
            priority=priority,
            wait_time_minutes=priority.get_max_wait_minutes(),
            recommendations=recommendations,
            requires_immediate_attention=priority in [
                TriagePriority.RESUSCITATION,
                TriagePriority.EMERGENT,
            ],
            confidence_score=min(final_score, 1.0),
            assessment_factors=assessment_factors,
        )

    def _score_to_priority(self, score: float) -> TriagePriority:
        """Convert score to triage priority."""
        if score >= 0.9:
            return TriagePriority.RESUSCITATION
        elif score >= 0.7:
            return TriagePriority.EMERGENT
        elif score >= 0.5:
            return TriagePriority.URGENT
        elif score >= 0.3:
            return TriagePriority.LESS_URGENT
        else:
            return TriagePriority.NON_URGENT

    def _generate_recommendations(
        self,
        priority: TriagePriority,
        symptoms: list[str],
        vital_signs: VitalSigns | None,
        patient: Patient | None,
    ) -> list[str]:
        """Generate recommendations based on assessment."""
        recommendations: list[str] = []

        if priority == TriagePriority.RESUSCITATION:
            recommendations.append("Atencion medica inmediata requerida")
            recommendations.append("El paciente sera atendido de inmediato")
            recommendations.append("Llamar al equipo de emergencias")

        elif priority == TriagePriority.EMERGENT:
            recommendations.append(f"Atencion prioritaria - tiempo maximo de espera {priority.get_max_wait_minutes()} minutos")
            recommendations.append("Permanecer en el area de emergencias")
            recommendations.append("Informar inmediatamente si los sintomas empeoran")

        elif priority == TriagePriority.URGENT:
            recommendations.append(f"Atencion urgente - tiempo estimado {priority.get_max_wait_minutes()} minutos")
            recommendations.append("Mantener al paciente en observacion")

        else:
            recommendations.append(f"Tiempo estimado de espera: {priority.get_max_wait_minutes()} minutos")
            recommendations.append("Considerar programar una cita regular si no es urgente")

        # Add patient-specific recommendations
        if patient:
            if patient.allergies:
                recommendations.append(f"Alergias registradas: {', '.join(patient.allergies[:3])}")
            if patient.current_medications:
                recommendations.append("Verificar medicacion actual antes de administrar tratamiento")

        # Add vital sign recommendations
        if vital_signs and vital_signs.is_critical():
            recommendations.append("Signos vitales criticos - monitoreo continuo requerido")

        return recommendations

    def reassess(
        self,
        previous_assessment: TriageAssessment,
        new_symptoms: list[str] | None = None,
        new_vital_signs: VitalSigns | None = None,
    ) -> TriageAssessment:
        """
        Reassess triage based on changes.

        Args:
            previous_assessment: Previous assessment
            new_symptoms: Updated symptoms
            new_vital_signs: Updated vital signs

        Returns:
            New TriageAssessment
        """
        # Combine symptoms if new ones provided
        symptoms = new_symptoms or []
        old_symptoms = list(previous_assessment.assessment_factors.get("symptom_scores", {}).keys())
        all_symptoms = list(set(symptoms + old_symptoms))

        return self.assess(
            symptoms=all_symptoms,
            vital_signs=new_vital_signs,
        )
