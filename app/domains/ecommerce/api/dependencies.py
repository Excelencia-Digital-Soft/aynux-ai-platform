"""
E-commerce API Dependencies

FastAPI dependencies for the e-commerce domain.
"""

from app.core.container import DependencyContainer
from app.domains.ecommerce.application.use_cases import (
    GetFeaturedProductsUseCase,
    GetProductByIdUseCase,
    GetProductsByCategoryUseCase,
    SearchProductsUseCase,
)


def get_container() -> DependencyContainer:
    """Get dependency container instance."""
    return DependencyContainer()


def get_search_products_use_case() -> SearchProductsUseCase:
    """Get SearchProductsUseCase instance."""
    return get_container().create_search_products_use_case()


def get_product_by_id_use_case() -> GetProductByIdUseCase:
    """Get GetProductByIdUseCase instance."""
    return get_container().create_get_product_by_id_use_case()


def get_products_by_category_use_case() -> GetProductsByCategoryUseCase:
    """Get GetProductsByCategoryUseCase instance."""
    return get_container().create_get_products_by_category_use_case()


def get_featured_products_use_case() -> GetFeaturedProductsUseCase:
    """Get GetFeaturedProductsUseCase instance."""
    return get_container().create_get_featured_products_use_case()


__all__ = [
    "get_container",
    "get_search_products_use_case",
    "get_product_by_id_use_case",
    "get_products_by_category_use_case",
    "get_featured_products_use_case",
]
