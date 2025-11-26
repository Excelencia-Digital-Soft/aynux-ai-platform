"""
Healthcare Domain Services

Domain services that encapsulate complex business logic.
"""

from app.domains.healthcare.domain.services.scheduling_service import (
    AvailableSlot,
    SchedulingResult,
    SchedulingService,
)
from app.domains.healthcare.domain.services.triage_service import (
    TriageAssessment,
    TriageService,
)

__all__ = [
    "SchedulingService",
    "AvailableSlot",
    "SchedulingResult",
    "TriageService",
    "TriageAssessment",
]
