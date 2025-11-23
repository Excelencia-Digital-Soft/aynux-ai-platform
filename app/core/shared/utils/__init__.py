"""
Core Shared Utilities

Utility functions and services used across the application:
- phone_normalizer: Phone number validation and normalization
- data_extraction: Dynamic database schema and data extraction
"""

from app.core.shared.utils.data_extraction import (
    DataExtractionService,
    ExtractedData,
    TableSchema,
)
from app.core.shared.utils.phone_normalizer import (
    PhoneNumberInfo,
    PhoneNumberRequest,
    get_normalized_number_only,
    normalize_phone_number,
)

__all__ = [
    # Phone Normalizer
    "PhoneNumberInfo",
    "PhoneNumberRequest",
    "normalize_phone_number",
    "get_normalized_number_only",
    # Data Extraction
    "DataExtractionService",
    "ExtractedData",
    "TableSchema",
]
