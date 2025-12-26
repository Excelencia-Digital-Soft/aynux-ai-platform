# ============================================================================
# SCOPE: SUPPORT/INCIDENTS
# Description: Modelos SQLAlchemy para el sistema de soporte e incidencias.
#              Incluye tickets, categorias, historial y configuracion Jira.
# Tenant-Aware: Yes - los modelos tienen FK opcional a organizations.
# ============================================================================
"""
Support/Incidents models for Aynux platform.

This package contains all models related to incident management:
- Incident: Main incident/ticket table
- IncidentCategory: Dynamic categories with Jira mapping
- IncidentComment: Comments on incidents
- IncidentHistory: Change history tracking
- JiraConfig: Multi-Jira configuration per organization
- PendingTicket: Conversational flow state for ticket creation
"""

from .incident import Incident
from .incident_category import IncidentCategory
from .incident_comment import IncidentComment
from .incident_history import IncidentHistory
from .jira_config import JiraConfig
from .pending_ticket import PendingTicket

__all__ = [
    "Incident",
    "IncidentCategory",
    "IncidentComment",
    "IncidentHistory",
    "JiraConfig",
    "PendingTicket",
]
