"""
E-commerce Infrastructure Repositories

Repository implementations for data access.
All repositories implement core interfaces from app.core.interfaces.repository
"""

from .product_repository import ProductRepository

__all__ = [
    "ProductRepository",
]
