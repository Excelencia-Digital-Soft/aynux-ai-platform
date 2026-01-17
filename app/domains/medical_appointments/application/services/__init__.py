# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Application services for medical appointments domain.
# ============================================================================
"""Application Services.

Contains services that coordinate domain operations and interact with
repositories for workflow configuration.
"""

from .workflow_service import WorkflowService

__all__ = [
    "WorkflowService",
]
