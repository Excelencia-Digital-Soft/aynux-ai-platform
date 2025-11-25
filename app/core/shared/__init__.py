"""
Shared utilities module

This module provides common utilities used across the entire application.
All utilities are domain-agnostic and reusable.
"""

# JSON utilities
from .json_extractor import (
    extract_json_from_text,
    extract_json_safely,
)

# Language detection
from .language_detector import (
    LanguageDetector,
    detect_language,
    get_language_detector,
)

# Phone number normalization
from .phone_normalizer import (
    PhoneNumberNormalizer,
    normalize_whatsapp_number,
)

# Rate limiting
from .rate_limiter import (
    BatchRateLimiter,
    DuxApiRateLimiter,
    RateLimiter,
    retry_with_rate_limit,
)

__all__ = [
    # JSON utilities
    "extract_json_from_text",
    "extract_json_safely",
    # Language detection
    "LanguageDetector",
    "detect_language",
    "get_language_detector",
    # Phone normalization
    "PhoneNumberNormalizer",
    "normalize_whatsapp_number",
    # Rate limiting
    "RateLimiter",
    "DuxApiRateLimiter",
    "BatchRateLimiter",
    "retry_with_rate_limit",
]
