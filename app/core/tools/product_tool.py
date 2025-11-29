"""
Product Tool - Backwards compatibility module.

This module re-exports from the refactored product package.
All new code should import directly from app.core.tools.product
"""

from app.core.tools.product import ProductTool

__all__ = ["ProductTool"]
