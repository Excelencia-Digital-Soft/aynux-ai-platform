# ============================================================================
# BACKWARD COMPATIBILITY MODULE
# Description: Re-exports from refactored response/ package.
#              Maintains backward compatibility for existing imports.
# ============================================================================
"""
Backward compatibility module for response generation.

This module re-exports all public symbols from the refactored
response/ package to maintain compatibility with existing imports.

DEPRECATED: Import directly from response/ package instead:
    from app.domains.pharmacy.agents.utils.response import (
        PharmacyResponseGenerator,
        GeneratedResponse,
        ResponseType,
        get_response_generator,
    )
"""

from app.domains.pharmacy.agents.utils.response import (
    GeneratedResponse,
    PharmacyResponseGenerator,
    ResponseType,
    get_response_generator,
)

__all__ = [
    "GeneratedResponse",
    "PharmacyResponseGenerator",
    "ResponseType",
    "get_response_generator",
]
