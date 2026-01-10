"""
Person Resolution Node - Entry Point for Pharmacy Flow.

BACKWARD COMPATIBILITY LAYER:
This file re-exports from the refactored person_resolution package.
All imports from this file will work as before.

For new code, prefer importing directly from the package:
    from app.domains.pharmacy.agents.nodes.person_resolution import PersonResolutionNode
"""

from __future__ import annotations

# Re-export everything from the refactored package
from app.domains.pharmacy.agents.nodes.person_resolution import (
    MAX_IDENTIFICATION_RETRIES,
    NAME_MATCH_THRESHOLD,
    OTHER_INDICATORS,
    OWN_INDICATORS,
    STEP_AWAITING_IDENTIFIER,
    STEP_AWAITING_WELCOME,
    STEP_NAME,
    WELCOME_OPTIONS,
    PersonResolutionFactory,
    PersonResolutionNode,
)

__all__ = [
    "PersonResolutionNode",
    "PersonResolutionFactory",
    "STEP_AWAITING_WELCOME",
    "STEP_AWAITING_IDENTIFIER",
    "STEP_NAME",
    "MAX_IDENTIFICATION_RETRIES",
    "NAME_MATCH_THRESHOLD",
    "WELCOME_OPTIONS",
    "OWN_INDICATORS",
    "OTHER_INDICATORS",
]
