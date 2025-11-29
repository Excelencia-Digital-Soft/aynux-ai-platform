"""
E-commerce Domain Container.

Single Responsibility: Wire all e-commerce domain dependencies.
"""

import logging
from typing import TYPE_CHECKING

from app.domains.ecommerce.application.use_cases import (
    CreateOrderUseCase,
    GetCustomerOrdersUseCase,
    GetFeaturedProductsUseCase,
    GetProductByIdUseCase,
    GetProductsByCategoryUseCase,
    SearchProductsUseCase,
    TrackOrderUseCase,
)
from app.domains.ecommerce.infrastructure.repositories import (
    ProductRepository,
    SQLAlchemyCategoryRepository,
    SQLAlchemyOrderRepository,
    SQLAlchemyPromotionRepository,
)

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class EcommerceContainer:
    """
    E-commerce domain container.

    Single Responsibility: Create e-commerce repositories and use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize e-commerce container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    # ==================== REPOSITORIES ====================

    def create_product_repository(self) -> ProductRepository:
        """Create Product Repository."""
        return ProductRepository()

    def create_order_repository(self, db) -> SQLAlchemyOrderRepository:
        """Create Order Repository."""
        return SQLAlchemyOrderRepository(session=db)

    def create_category_repository(self, db) -> SQLAlchemyCategoryRepository:
        """Create Category Repository."""
        return SQLAlchemyCategoryRepository(session=db)

    def create_promotion_repository(self, db) -> SQLAlchemyPromotionRepository:
        """Create Promotion Repository."""
        return SQLAlchemyPromotionRepository(session=db)

    # ==================== USE CASES ====================

    def create_search_products_use_case(self) -> SearchProductsUseCase:
        """Create SearchProductsUseCase with dependencies."""
        return SearchProductsUseCase(
            product_repository=self.create_product_repository(),
            vector_store=self._base.get_vector_store(),
            llm=self._base.get_llm(),
        )

    def create_get_products_by_category_use_case(self) -> GetProductsByCategoryUseCase:
        """Create GetProductsByCategoryUseCase with dependencies."""
        return GetProductsByCategoryUseCase(product_repository=self.create_product_repository())

    def create_get_featured_products_use_case(self) -> GetFeaturedProductsUseCase:
        """Create GetFeaturedProductsUseCase with dependencies."""
        return GetFeaturedProductsUseCase(product_repository=self.create_product_repository())

    def create_get_product_by_id_use_case(self) -> GetProductByIdUseCase:
        """Create GetProductByIdUseCase with dependencies."""
        return GetProductByIdUseCase(product_repository=self.create_product_repository())

    def create_create_order_use_case(self, db) -> CreateOrderUseCase:
        """Create CreateOrderUseCase with dependencies."""
        return CreateOrderUseCase(
            order_repository=self.create_order_repository(db),
            product_repository=self.create_product_repository(),  # type: ignore[arg-type]
        )

    def create_track_order_use_case(self, db) -> TrackOrderUseCase:
        """Create TrackOrderUseCase with dependencies."""
        return TrackOrderUseCase(order_repository=self.create_order_repository(db))

    def create_get_customer_orders_use_case(self, db) -> GetCustomerOrdersUseCase:
        """Create GetCustomerOrdersUseCase with dependencies."""
        return GetCustomerOrdersUseCase(order_repository=self.create_order_repository(db))
