"""
Product Formatter.

Single Responsibility: Format product data into consistent dictionaries.
"""

from collections.abc import Sequence
from typing import Any


class ProductFormatter:
    """Formats product data into consistent dictionaries."""

    def format_product(
        self,
        product: Any,
        category: Any | None = None,
        brand: Any | None = None,
    ) -> dict[str, Any]:
        """Format product data into a consistent dictionary."""
        return {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "model": product.model,
            "price": float(product.price),
            "stock": product.stock,
            "active": product.active,
            "featured": product.featured,
            "on_sale": product.on_sale,
            "category": {
                "id": category.id if category else None,
                "name": category.name if category else None,
                "display_name": category.display_name if category else None,
            },
            "brand": {
                "id": brand.id if brand else None,
                "name": brand.name if brand else None,
            },
            "created_at": (
                product.created_at.isoformat() if product.created_at else None
            ),
            "updated_at": (
                product.updated_at.isoformat() if product.updated_at else None
            ),
        }

    def format_products(self, rows: Sequence[Any]) -> list[dict[str, Any]]:
        """Format multiple product rows into dictionaries.

        Args:
            rows: Sequence of row objects (SQLAlchemy Row or tuple-like).
                  Each row should contain (product, category, brand).
        """
        products = []
        for row in rows:
            product, category, brand = row
            products.append(self.format_product(product, category, brand))
        return products
