# ============================================================================
# SCOPE: APPLICATION LAYER (Medical Appointments)
# Description: Utility classes for response extraction and field mapping
# ============================================================================
"""Application utilities for Medical Appointments domain.

Provides reusable utilities for:
- Response extraction from ExternalResponse objects
- Field mapping from external API responses to internal DTOs
"""

from .field_mapper import ExternalFieldMapper, FieldMapping
from .response_extractor import ResponseExtractor

__all__ = [
    "ResponseExtractor",
    "FieldMapping",
    "ExternalFieldMapper",
]
