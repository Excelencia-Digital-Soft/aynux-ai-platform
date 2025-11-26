"""
Healthcare API Routes

FastAPI router for healthcare endpoints.
"""

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
from app.domains.healthcare.domain.value_objects import DoctorSpecialty

router = APIRouter(prefix="/healthcare", tags=["Healthcare"])


@router.post("/appointments", response_model=AppointmentResponse)
async def book_appointment(
    request: AppointmentRequest,
    use_case: BookAppointmentUseCase = Depends(get_book_appointment_use_case),
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

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return AppointmentResponse(
        id=result.appointment.id,
        patient_id=result.appointment.patient_id,
        doctor_id=result.appointment.doctor_id,
        appointment_date=result.appointment.date,
        start_time=result.appointment.start_time,
        end_time=result.appointment.end_time,
        specialty=result.appointment.specialty.value,
        status=result.appointment.status.value,
        is_telemedicine=result.appointment.is_telemedicine,
    )


@router.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient_records(
    patient_id: int,
    use_case: GetPatientRecordsUseCase = Depends(get_patient_records_use_case),
):
    """Get patient records."""
    result = await use_case.execute(patient_id=patient_id)

    if result.patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    return PatientResponse(
        id=result.patient.id,
        first_name=result.patient.first_name,
        last_name=result.patient.last_name,
        date_of_birth=result.patient.date_of_birth,
        phone=result.patient.phone,
        email=result.patient.email,
        medical_record_number=result.patient.medical_record_number,
    )


@router.post("/triage", response_model=TriageResponse)
async def triage_patient(
    request: TriageRequest,
    use_case: TriagePatientUseCase = Depends(get_triage_patient_use_case),
):
    """Perform triage assessment."""
    result = await use_case.execute(
        patient_id=request.patient_id,
        symptoms=request.symptoms,
        pain_level=request.pain_level,
    )

    return TriageResponse(
        patient_id=request.patient_id,
        priority=result.assessment.priority.value,
        wait_time_minutes=result.assessment.wait_time_minutes,
        recommendations=result.assessment.recommendations,
        requires_immediate_attention=result.assessment.requires_immediate_attention,
        confidence_score=result.assessment.confidence_score,
    )


__all__ = ["router"]
