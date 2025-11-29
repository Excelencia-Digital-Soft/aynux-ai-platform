"""
Healthcare API Routes

FastAPI router for healthcare endpoints.
"""

from datetime import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.domains.healthcare.api.dependencies import (
    get_book_appointment_use_case,
    get_patient_records_use_case,
    get_triage_patient_use_case,
)
from app.domains.healthcare.api.schemas import (
    AppointmentRequest,
    AppointmentResponse,
    PatientResponse,
    TriageRequest,
    TriageResponse,
)
from app.domains.healthcare.application.use_cases import (
    BookAppointmentUseCase,
    GetPatientRecordsUseCase,
    TriagePatientUseCase,
)
from app.domains.healthcare.application.use_cases.get_patient_records import (
    GetPatientRecordsRequest,
)
from app.domains.healthcare.application.use_cases.triage_patient import (
    TriagePatientRequest,
)
from app.domains.healthcare.domain.value_objects import DoctorSpecialty, TriagePriority

router = APIRouter(prefix="/healthcare", tags=["Healthcare"])

# Type aliases for use case dependencies
BookAppointmentUseCaseDep = Annotated[BookAppointmentUseCase, Depends(get_book_appointment_use_case)]
GetPatientRecordsUseCaseDep = Annotated[GetPatientRecordsUseCase, Depends(get_patient_records_use_case)]
TriagePatientUseCaseDep = Annotated[TriagePatientUseCase, Depends(get_triage_patient_use_case)]


@router.post("/appointments", response_model=AppointmentResponse)
async def book_appointment(
    request: AppointmentRequest,
    use_case: BookAppointmentUseCaseDep,
):
    """Book a new appointment."""
    from app.domains.healthcare.application.use_cases.book_appointment import (
        BookAppointmentRequest,
    )

    try:
        specialty = DoctorSpecialty(request.specialty)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid specialty: {request.specialty}") from e

    result = await use_case.execute(
        BookAppointmentRequest(
            patient_id=request.patient_id,
            doctor_id=request.doctor_id,
            doctor_name="",  # Will be fetched from DB
            appointment_date=request.appointment_date,
            start_time=request.start_time,
            specialty=specialty,
            reason=request.reason,
            duration_minutes=request.duration_minutes,
            is_telemedicine=request.is_telemedicine,
        )
    )

    if not result.success or result.appointment is None:
        raise HTTPException(status_code=400, detail=result.error or "Failed to book appointment")

    appointment = result.appointment
    # Ensure required time fields have valid values
    start_time = appointment.start_time or time(0, 0)
    end_time = appointment.end_time or time(0, 0)

    return AppointmentResponse(
        id=appointment.id or 0,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        appointment_date=appointment.appointment_date or request.appointment_date,
        start_time=start_time,
        end_time=end_time,
        specialty=appointment.specialty.value,
        status=appointment.status.value,
        is_telemedicine=appointment.is_telemedicine,
    )


@router.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient_records(
    patient_id: int,
    use_case: GetPatientRecordsUseCaseDep,
):
    """Get patient records."""
    result = await use_case.execute(
        request=GetPatientRecordsRequest(patient_id=patient_id)
    )

    if result.patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient = result.patient
    return PatientResponse(
        id=patient.id or 0,
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=patient.date_of_birth,
        phone=str(patient.phone) if patient.phone else None,
        email=str(patient.email) if patient.email else None,
        medical_record_number=patient.medical_record_number,
    )


@router.post("/triage", response_model=TriageResponse)
async def triage_patient(
    request: TriageRequest,
    use_case: TriagePatientUseCaseDep,
):
    """Perform triage assessment."""
    result = await use_case.execute(
        request=TriagePatientRequest(
            patient_id=request.patient_id,
            symptoms=request.symptoms,
            pain_level=request.pain_level,
        )
    )

    if not result.success or result.priority is None:
        raise HTTPException(status_code=400, detail=result.error or "Triage failed")

    # Check if priority requires immediate attention
    requires_immediate = result.priority in [TriagePriority.RESUSCITATION, TriagePriority.EMERGENT]

    return TriageResponse(
        patient_id=request.patient_id,
        priority=result.priority.value,
        wait_time_minutes=result.wait_time_minutes or 0,
        recommendations=result.recommendations or [],
        requires_immediate_attention=requires_immediate,
        confidence_score=0.0,  # Not available in current response
    )


__all__ = ["router"]
