"""
Support use cases for Excelencia domain.

Contains use cases for handling support tickets created via chat.

Use Cases:
- CreateIncidentUseCase: Create incidents in soporte.incidents (conversational flow)
- GetPendingTicketUseCase: Get active pending ticket for conversation
- SavePendingTicketUseCase: Create/update pending tickets
"""

from .create_incident_use_case import CreateIncidentUseCase
from .get_pending_ticket_use_case import GetPendingTicketUseCase
from .save_pending_ticket_use_case import SavePendingTicketUseCase

__all__ = [
    "CreateIncidentUseCase",
    "GetPendingTicketUseCase",
    "SavePendingTicketUseCase",
]
