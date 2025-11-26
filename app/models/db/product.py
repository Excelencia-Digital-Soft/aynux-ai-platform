"""
Product Model (Deprecated)

This module is deprecated. Use domain entities instead:
- app.domains.ecommerce.domain.entities.product.Product
"""

# Re-export from domain entities for backwards compatibility
from app.domains.ecommerce.domain.entities.product import Product

__all__ = [
    "Product",
]
