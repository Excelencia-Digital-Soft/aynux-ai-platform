# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Ports (interfaces) for external systems.
# ============================================================================
"""Medical Appointments Application Ports.

Contains interface definitions (ports) following the hexagonal architecture
and Interface Segregation Principle (ISP).

Segregated Interfaces (use when only specific functionality is needed):
- IPatientManager: Patient CRUD operations
- IAppointmentManager: Appointment CRUD operations
- IAvailabilityChecker: Availability queries
- IReminderManager: Reminder operations
- INotificationService: WhatsApp notifications

Combined Interface (use when full access is needed):
- IMedicalSystemClient: All medical system operations
"""

from .appointment_port import IAppointmentManager
from .availability_port import IAvailabilityChecker
from .external_medical_system import IMedicalSystemClient
from .notification_port import INotificationService
from .patient_port import IPatientManager
from .reminder_port import IReminderManager
from .response import ExternalResponse

__all__ = [
    # Response type
    "ExternalResponse",
    # Segregated interfaces (ISP)
    "IPatientManager",
    "IAppointmentManager",
    "IAvailabilityChecker",
    "IReminderManager",
    "INotificationService",
    # Combined interface
    "IMedicalSystemClient",
]
