# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Use Cases exports.
# ============================================================================
"""Application Use Cases for Medical Appointments domain."""

from .book_appointment import BookAppointmentUseCase
from .cancel_appointment import CancelAppointmentUseCase
from .confirm_appointment import ConfirmAppointmentUseCase
from .get_available_slots import GetAvailableSlotsUseCase
from .get_patient_appointments import GetPatientAppointmentsUseCase
from .register_patient import RegisterPatientUseCase
from .reschedule_appointment import RescheduleAppointmentUseCase
from .send_reminder import SendReminderUseCase

__all__ = [
    "BookAppointmentUseCase",
    "CancelAppointmentUseCase",
    "ConfirmAppointmentUseCase",
    "GetAvailableSlotsUseCase",
    "GetPatientAppointmentsUseCase",
    "RegisterPatientUseCase",
    "RescheduleAppointmentUseCase",
    "SendReminderUseCase",
]
