# ============================================================================
# SCOPE: INFRASTRUCTURE LAYER (Medical Appointments)
# Description: Scheduler module for appointment reminders.
# ============================================================================
"""Scheduler module for medical appointment reminders.

Provides two scheduler implementations:
- ReminderScheduler: Legacy scheduler with hardcoded schedules
- ConfigurableReminderScheduler: Database-driven configurable schedules

For new implementations, use ConfigurableReminderScheduler which supports:
- Per-institution reminder configurations
- Dynamic schedule loading from database
- Configurable message templates
- Interactive WhatsApp buttons
"""

from .configurable_reminder_scheduler import (
    ConfigurableReminderScheduler,
    get_configurable_reminder_scheduler,
    shutdown_configurable_scheduler,
)
from .reminder_scheduler import (
    ReminderScheduler,
    get_reminder_scheduler,
    shutdown_scheduler,
)

__all__ = [
    # Legacy scheduler
    "ReminderScheduler",
    "get_reminder_scheduler",
    "shutdown_scheduler",
    # Configurable scheduler
    "ConfigurableReminderScheduler",
    "get_configurable_reminder_scheduler",
    "shutdown_configurable_scheduler",
]
