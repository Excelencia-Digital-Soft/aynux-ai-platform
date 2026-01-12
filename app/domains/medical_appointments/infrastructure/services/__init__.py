# ============================================================================
# SCOPE: DOMAIN-SPECIFIC (Medical Appointments)
# Description: Infrastructure services for medical appointments domain.
# ============================================================================
"""
Medical Appointments Infrastructure Services.

Contains domain-specific services that use global infrastructure components.

Components:
- AppointmentNotificationService: Main notification service (implements INotificationService)
- InteractiveSelectionService: Interactive selection messages for booking flow
"""

from .appointment_notification_service import AppointmentNotificationService
from .notification import InteractiveSelectionService

__all__ = [
    "AppointmentNotificationService",
    "InteractiveSelectionService",
]
