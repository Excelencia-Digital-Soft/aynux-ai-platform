"""
Person Resolution Node - Entry Point for Pharmacy Flow.

BACKWARD COMPATIBILITY LAYER:
This file re-exports from the refactored person_resolution package.
All imports from this file will work as before.

For new code, prefer importing directly from the package:
    from app.domains.pharmacy.agents.nodes.person_resolution import PersonResolutionNode

For state preservation, use Pydantic models:
    from app.domains.pharmacy.agents.models import StatePreserver, PreservedContext
"""

from __future__ import annotations

# Re-export everything from the refactored package
from app.domains.pharmacy.agents.nodes.person_resolution import (
    MAX_IDENTIFICATION_RETRIES,
    NAME_MATCH_THRESHOLD,
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
    STEP_NAME,
    PersonResolutionFactory,
    PersonResolutionNode,
    PreservedContext,
    StatePreserver,
)

__all__ = [
    "PersonResolutionNode",
    "PersonResolutionFactory",
    "STEP_AWAITING_WELCOME",
    "STEP_AWAITING_IDENTIFIER",
    "STEP_NAME",
    "MAX_IDENTIFICATION_RETRIES",
    "NAME_MATCH_THRESHOLD",
    # Pydantic state models (replaces PRESERVED_STATE_FIELDS)
    "PreservedContext",
    "StatePreserver",
    # NOTE: WELCOME_OPTIONS, OWN_INDICATORS, OTHER_INDICATORS moved to database
]
