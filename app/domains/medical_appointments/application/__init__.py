# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Application layer exports.
# ============================================================================
"""Application Layer - Medical Appointments.

Contains use cases, ports (interfaces), and DTOs for the medical
appointments domain.
"""

from .dto import (
    AppointmentDTO,
    AvailableDateDTO,
    AvailableSlotDTO,
    BookAppointmentRequest,
    BookAppointmentResult,
    CancelAppointmentRequest,
    ConfirmAppointmentRequest,
    GetAvailableSlotsRequest,
    GetAvailableSlotsResult,
    GetPatientAppointmentsRequest,
    GetPatientAppointmentsResult,
    PatientDTO,
    ProviderDTO,
    RegisterPatientRequest,
    RescheduleAppointmentRequest,
    SendReminderRequest,
    SendReminderResult,
    SpecialtyDTO,
    UseCaseResult,
)
from .ports.external_medical_system import ExternalResponse, IMedicalSystemClient
from .use_cases import (
    BookAppointmentUseCase,
    CancelAppointmentUseCase,
    ConfirmAppointmentUseCase,
    GetAvailableSlotsUseCase,
    GetPatientAppointmentsUseCase,
    RegisterPatientUseCase,
    RescheduleAppointmentUseCase,
    SendReminderUseCase,
)
from .utils import ExternalFieldMapper, FieldMapping, ResponseExtractor

__all__ = [
    # Ports
    "ExternalResponse",
    "IMedicalSystemClient",
    # Utils
    "ResponseExtractor",
    "ExternalFieldMapper",
    "FieldMapping",
    # Request DTOs
    "BookAppointmentRequest",
    "CancelAppointmentRequest",
    "ConfirmAppointmentRequest",
    "RescheduleAppointmentRequest",
    "RegisterPatientRequest",
    "GetAvailableSlotsRequest",
    "GetPatientAppointmentsRequest",
    "SendReminderRequest",
    # Response/Data DTOs
    "AppointmentDTO",
    "PatientDTO",
    "ProviderDTO",
    "SpecialtyDTO",
    "AvailableSlotDTO",
    "AvailableDateDTO",
    # Result DTOs
    "UseCaseResult",
    "BookAppointmentResult",
    "GetAvailableSlotsResult",
    "GetPatientAppointmentsResult",
    "SendReminderResult",
    # Use Cases
    "BookAppointmentUseCase",
    "CancelAppointmentUseCase",
    "ConfirmAppointmentUseCase",
    "GetAvailableSlotsUseCase",
    "GetPatientAppointmentsUseCase",
    "RegisterPatientUseCase",
    "RescheduleAppointmentUseCase",
    "SendReminderUseCase",
]
