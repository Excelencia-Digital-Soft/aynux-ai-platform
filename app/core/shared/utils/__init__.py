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
    PhoneNumberResponse,
    PydanticPhoneNumberNormalizer,
    get_normalized_number_only,
    normalize_whatsapp_number_pydantic,
)

__all__ = [
    # Phone Normalizer
    "PhoneNumberInfo",
    "PhoneNumberRequest",
    "PhoneNumberResponse",
    "PydanticPhoneNumberNormalizer",
    "normalize_whatsapp_number_pydantic",
    "get_normalized_number_only",
    # Data Extraction
    "DataExtractionService",
    "ExtractedData",
    "TableSchema",
]
