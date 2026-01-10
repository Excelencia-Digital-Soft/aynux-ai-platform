# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Data Transfer Objects exports.
# ============================================================================
"""Application DTOs for Medical Appointments domain."""

from .appointment_dtos import (
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

__all__ = [
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
]
