"""
Product SQL Generation Module.

Provides SQL generation capabilities for product queries using AI.
"""

from .analyzer import QueryComplexityAnalyzer
from .builder import ProductSQLBuilder
from .executor import SQLExecutor
from .generator import ProductSQLGenerator
from .schemas import (
    ALLOWED_TABLES,
    FORBIDDEN_OPERATIONS,
    PRODUCT_SCHEMA,
    ProductSQLResult,
)
from .validator import SQLValidator

__all__ = [
    # Main generator
    "ProductSQLGenerator",
    "ProductSQLResult",
    # Components
    "QueryComplexityAnalyzer",
    "ProductSQLBuilder",
    "SQLValidator",
    "SQLExecutor",
    # Configuration
    "ALLOWED_TABLES",
    "FORBIDDEN_OPERATIONS",
    "PRODUCT_SCHEMA",
]
