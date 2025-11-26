"""
Book Appointment Use Case

Use case for booking medical appointments.
Follows Clean Architecture and SOLID principles.
"""

import logging
from dataclasses import dataclass
from datetime import date, time

from app.core.domain import AppointmentConflictException, EntityNotFoundException
from app.domains.healthcare.application.ports.appointment_repository import IAppointmentRepository
from app.domains.healthcare.application.ports.patient_repository import IPatientRepository
from app.domains.healthcare.domain.entities.appointment import Appointment
from app.domains.healthcare.domain.value_objects.appointment_status import DoctorSpecialty

logger = logging.getLogger(__name__)


@dataclass
class BookAppointmentRequest:
    """Request for booking an appointment."""

    patient_id: int
    doctor_id: int
    doctor_name: str
    appointment_date: date
    start_time: time
    specialty: DoctorSpecialty
    reason: str | None = None
    duration_minutes: int = 30
    is_telemedicine: bool = False


@dataclass
class BookAppointmentResponse:
    """Response from booking an appointment."""

    success: bool
    appointment: Appointment | None = None
    error: str | None = None
    conflict_message: str | None = None


class BookAppointmentUseCase:
    """
    Use case for booking appointments.

    Single Responsibility: Only handles appointment booking logic
    Dependency Inversion: Depends on interfaces, not implementations
    """

    def __init__(
        self,
        appointment_repository: IAppointmentRepository,
        patient_repository: IPatientRepository,
    ):
        """
        Initialize use case with dependencies.

        Args:
            appointment_repository: Repository for appointment data access
            patient_repository: Repository for patient data access
        """
        self.appointment_repo = appointment_repository
        self.patient_repo = patient_repository

    async def execute(self, request: BookAppointmentRequest) -> BookAppointmentResponse:
        """
        Execute appointment booking use case.

        Args:
            request: Booking request parameters

        Returns:
            Booking response with appointment or error
        """
        try:
            # 1. Verify patient exists
            patient = await self.patient_repo.find_by_id(request.patient_id)
            if not patient:
                raise EntityNotFoundException(
                    entity_type="Patient",
                    entity_id=request.patient_id,
                )

            # 2. Check patient is active
            if not patient.is_active():
                return BookAppointmentResponse(
                    success=False,
                    error="Patient record is not active",
                )

            # 3. Calculate end time
            from datetime import datetime, timedelta
            start_dt = datetime.combine(request.appointment_date, request.start_time)
            end_dt = start_dt + timedelta(minutes=request.duration_minutes)
            end_time = end_dt.time()

            # 4. Check for conflicts
            has_conflict = await self.appointment_repo.check_conflict(
                doctor_id=request.doctor_id,
                appointment_date=request.appointment_date,
                start_time=request.start_time,
                end_time=end_time,
            )

            if has_conflict:
                return BookAppointmentResponse(
                    success=False,
                    error="Time slot is not available",
                    conflict_message=f"Doctor has another appointment at {request.start_time.strftime('%H:%M')}",
                )

            # 5. Create appointment
            appointment = Appointment.create_consultation(
                patient_id=request.patient_id,
                patient_name=patient.full_name,
                doctor_id=request.doctor_id,
                doctor_name=request.doctor_name,
                appointment_date=request.appointment_date,
                start_time=request.start_time,
                specialty=request.specialty,
                reason=request.reason,
            )

            appointment.duration_minutes = request.duration_minutes
            appointment.end_time = end_time

            if request.is_telemedicine:
                appointment.is_telemedicine = True

            # 6. Save appointment
            saved_appointment = await self.appointment_repo.save(appointment)

            logger.info(
                f"Appointment booked: {saved_appointment.id} for patient {patient.full_name} "
                f"on {request.appointment_date} at {request.start_time}"
            )

            return BookAppointmentResponse(
                success=True,
                appointment=saved_appointment,
            )

        except EntityNotFoundException as e:
            logger.warning(f"Entity not found: {e}")
            return BookAppointmentResponse(
                success=False,
                error=str(e),
            )
        except AppointmentConflictException as e:
            logger.warning(f"Appointment conflict: {e}")
            return BookAppointmentResponse(
                success=False,
                error="Schedule conflict",
                conflict_message=str(e),
            )
        except Exception as e:
            logger.error(f"Error booking appointment: {e}", exc_info=True)
            return BookAppointmentResponse(
                success=False,
                error=f"Failed to book appointment: {str(e)}",
            )
