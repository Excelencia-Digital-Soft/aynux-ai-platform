"""
Shared utilities module

This module provides common utilities used across the entire application.
All utilities are domain-agnostic and reusable.
"""

# JSON utilities
from .json_extractor import (
    extract_json_from_text,
    extract_json_objects,
    safe_json_parse,
)

# Language detection
from .language_detector import (
    LanguageDetector,
    detect_language,
    detect_language_batch,
)

# Phone number normalization
from .phone_normalizer import (
    PhoneNormalizer,
    normalize_phone,
    validate_phone,
)

# Rate limiting
from .rate_limiter import (
    RateLimiter,
    rate_limit,
    check_rate_limit,
)

__all__ = [
    # JSON utilities
    "extract_json_from_text",
    "extract_json_objects",
    "safe_json_parse",
    # Language detection
    "LanguageDetector",
    "detect_language",
    "detect_language_batch",
    # Phone normalization
    "PhoneNormalizer",
    "normalize_phone",
    "validate_phone",
    # Rate limiting
    "RateLimiter",
    "rate_limit",
    "check_rate_limit",
]
