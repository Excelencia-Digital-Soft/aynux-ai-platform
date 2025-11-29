"""
Product SQL Generator - Backwards compatibility module.

This module re-exports from the refactored product_sql package.
All new code should import directly from app.domains.ecommerce.agents.tools.product_sql
"""

from app.domains.ecommerce.agents.tools.product_sql import (
    ProductSQLGenerator,
    ProductSQLResult,
)

__all__ = ["ProductSQLGenerator", "ProductSQLResult"]
