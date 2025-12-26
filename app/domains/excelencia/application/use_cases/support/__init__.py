"""
Support use cases for Excelencia domain.

Contains use cases for handling support tickets created via chat.

Use Cases:
- CreateSupportTicketUseCase: Legacy use case for core.support_tickets
- CreateIncidentUseCase: New use case for soporte.incidents (conversational flow)
- GetPendingTicketUseCase: Get active pending ticket for conversation
- SavePendingTicketUseCase: Create/update pending tickets
"""

from .create_incident_use_case import CreateIncidentUseCase
from .create_support_ticket_use_case import CreateSupportTicketUseCase
from .get_pending_ticket_use_case import GetPendingTicketUseCase
from .save_pending_ticket_use_case import SavePendingTicketUseCase

__all__ = [
    "CreateSupportTicketUseCase",
    "CreateIncidentUseCase",
    "GetPendingTicketUseCase",
    "SavePendingTicketUseCase",
]
