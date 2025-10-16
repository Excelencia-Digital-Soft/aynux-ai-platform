"""
Response Generation Components

Strategy Pattern implementation for response generation.
Enables pluggable response generators without modifying client code.
"""

from .ai_response_generator import AIResponseGenerator
from .base_response_generator import (
    BaseResponseGenerator,
    GeneratedResponse,
    ResponseContext,
)
from .product_formatter import ProductFormatter

__all__ = [
    "BaseResponseGenerator",
    "GeneratedResponse",
    "ResponseContext",
    "AIResponseGenerator",
    "ProductFormatter",
]
