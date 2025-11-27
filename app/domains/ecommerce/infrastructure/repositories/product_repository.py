"""
Product Repository Implementation

Repository implementation for Product entity following Repository Pattern.
Implements ISearchableRepository interface for dependency inversion.
"""

import logging
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.interfaces.repository import ISearchableRepository
from app.database import get_db_context
from app.models.db import Brand, Category, Product, Subcategory

logger = logging.getLogger(__name__)


class ProductRepository(ISearchableRepository[Product, int]):
    """
    Product Repository implementation.

    Single Responsibility: Data access for Product entity only
    Dependency Inversion: Implements ISearchableRepository interface
    """

    def __init__(self, db_session: Session | None = None):
        """
        Initialize repository.

        Args:
            db_session: Optional database session (for testing)
        """
        self.db_session = db_session

    def _get_session(self) -> Session:
        """Get database session (for context manager or injected session)"""
        if self.db_session:
            return self.db_session
        return get_db_context().__enter__()

    async def find_by_id(self, id: int) -> Product | None:
        """
        Find product by ID.

        Args:
            id: Product ID

        Returns:
            Product or None if not found
        """
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(
                        joinedload(Product.category),
                        joinedload(Product.subcategory),
                        joinedload(Product.brand),
                    )
                    .filter(Product.id == id)
                    .first()
                )
        except Exception as e:
            logger.error(f"Error finding product by ID {id}: {e}", exc_info=True)
            return None

    async def find_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        """
        Find all products with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of products
        """
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(
                        joinedload(Product.category),
                        joinedload(Product.subcategory),
                        joinedload(Product.brand),
                    )
                    .filter(Product.active)
                    .order_by(desc(Product.featured), Product.name)
                    .offset(skip)
                    .limit(limit)
                    .all()
                )
        except Exception as e:
            logger.error(f"Error finding all products: {e}", exc_info=True)
            return []

    async def save(self, entity: Product) -> Product:
        """
        Save (create or update) product.

        Args:
            entity: Product to save

        Returns:
            Saved product
        """
        try:
            with get_db_context() as db:
                db.add(entity)
                db.commit()
                db.refresh(entity)
                return entity
        except Exception as e:
            logger.error(f"Error saving product: {e}", exc_info=True)
            raise

    async def delete(self, id: int) -> bool:
        """
        Delete product by ID (soft delete - set active=False).

        Args:
            id: Product ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            with get_db_context() as db:
                product = db.query(Product).filter(Product.id == id).first()
                if product:
                    product.active = False  # type: ignore
                    db.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting product {id}: {e}", exc_info=True)
            return False

    async def exists(self, id: int) -> bool:
        """
        Check if product exists.

        Args:
            id: Product ID

        Returns:
            True if exists, False otherwise
        """
        try:
            with get_db_context() as db:
                return db.query(Product.id).filter(Product.id == id).first() is not None
        except Exception as e:
            logger.error(f"Error checking product exists {id}: {e}", exc_info=True)
            return False

    async def count(self) -> int:
        """
        Count total products.

        Returns:
            Total count of active products
        """
        try:
            with get_db_context() as db:
                return db.query(func.count(Product.id)).filter(Product.active).scalar() or 0
        except Exception as e:
            logger.error(f"Error counting products: {e}", exc_info=True)
            return 0

    # IProductRepository methods (Protocol compliance)

    async def get_by_id(self, product_id: int) -> Product | None:
        """
        Get product by ID (IProductRepository interface).

        Args:
            product_id: Product ID

        Returns:
            Product or None if not found
        """
        return await self.find_by_id(product_id)

    async def get_by_code(self, code: str) -> Product | None:
        """
        Get product by code (IProductRepository interface).

        Args:
            code: Product code/model

        Returns:
            Product or None if not found
        """
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(
                        joinedload(Product.category),
                        joinedload(Product.subcategory),
                        joinedload(Product.brand),
                    )
                    .filter(Product.model == code)
                    .first()
                )
        except Exception as e:
            logger.error(f"Error finding product by code {code}: {e}", exc_info=True)
            return None

    async def get_by_category(
        self, category_id: int, limit: int = 20, offset: int = 0
    ) -> list[Product]:
        """
        Get products by category (IProductRepository interface).

        Args:
            category_id: Category ID
            limit: Maximum results
            offset: Number of records to skip

        Returns:
            List of products in the category
        """
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(
                        joinedload(Product.category),
                        joinedload(Product.subcategory),
                        joinedload(Product.brand),
                    )
                    .filter(Product.category_id == category_id, Product.active)
                    .order_by(desc(Product.featured), Product.name)
                    .offset(offset)
                    .limit(limit)
                    .all()
                )
        except Exception as e:
            logger.error(f"Error finding products by category {category_id}: {e}", exc_info=True)
            return []

    async def get_featured(self, limit: int = 10) -> list[Product]:
        """
        Get featured products (IProductRepository interface).

        Args:
            limit: Maximum results

        Returns:
            List of featured products
        """
        try:
            with get_db_context() as db:
                return (
                    db.query(Product)
                    .options(
                        joinedload(Product.category),
                        joinedload(Product.subcategory),
                        joinedload(Product.brand),
                    )
                    .filter(Product.featured, Product.active)
                    .order_by(Product.name)
                    .limit(limit)
                    .all()
                )
        except Exception as e:
            logger.error(f"Error finding featured products: {e}", exc_info=True)
            return []

    async def count_by_query(self, query: str) -> int:
        """
        Count products matching query (IProductRepository interface).

        Args:
            query: Search query text

        Returns:
            Count of matching products
        """
        try:
            with get_db_context() as db:
                db_query = db.query(func.count(Product.id)).filter(Product.active)

                if query and query.strip():
                    search_filter = or_(
                        Product.name.ilike(f"%{query}%"),
                        Product.specs.ilike(f"%{query}%"),
                        Product.description.ilike(f"%{query}%"),
                    )
                    db_query = db_query.filter(search_filter)

                return db_query.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting products by query: {e}", exc_info=True)
            return 0

    # ISearchableRepository methods

    async def search(self, query: str, limit: int = 10, offset: int = 0) -> list[Product]:
        """
        Search products (interface method).

        Args:
            query: Search query text
            limit: Maximum results
            offset: Number of records to skip

        Returns:
            List of matching products
        """
        return await self.search_advanced(query=query, limit=limit, offset=offset)

    async def search_advanced(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
    ) -> list[Product]:
        """
        Search products with filters.

        Args:
            query: Search query text
            filters: Optional filters dict
            limit: Maximum results
            offset: Number of records to skip
            sort_by: Field to sort by
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            List of matching products
        """
        try:
            with get_db_context() as db:
                # Start query
                db_query = db.query(Product).options(
                    joinedload(Product.category),
                    joinedload(Product.subcategory),
                    joinedload(Product.brand),
                )

                # Apply text search if query is provided
                if query and query.strip():
                    search_filter = or_(
                        Product.name.ilike(f"%{query}%"),
                        Product.specs.ilike(f"%{query}%"),
                        Product.description.ilike(f"%{query}%"),
                    )
                    db_query = db_query.filter(search_filter)

                # Apply filters
                if filters:
                    db_query = self._apply_filters(db_query, filters)

                # Always filter active products
                db_query = db_query.filter(Product.active)

                # Apply sorting
                if sort_by:
                    sort_field = getattr(Product, sort_by, None)
                    if sort_field is not None:
                        if sort_order == "desc":
                            db_query = db_query.order_by(desc(sort_field))
                        else:
                            db_query = db_query.order_by(sort_field)
                else:
                    # Default sort: featured first, then name
                    db_query = db_query.order_by(desc(Product.featured), Product.name)

                return db_query.offset(offset).limit(limit).all()

        except Exception as e:
            logger.error(f"Error searching products: {e}", exc_info=True)
            return []

    async def find_by_criteria(self, criteria: dict[str, Any], limit: int = 100) -> list[Product]:
        """
        Find products by criteria.

        Args:
            criteria: Search criteria
            limit: Maximum results

        Returns:
            List of matching products
        """
        try:
            with get_db_context() as db:
                db_query = db.query(Product).options(
                    joinedload(Product.category),
                    joinedload(Product.subcategory),
                    joinedload(Product.brand),
                )

                db_query = self._apply_filters(db_query, criteria)
                db_query = db_query.filter(Product.active)

                return db_query.limit(limit).all()

        except Exception as e:
            logger.error(f"Error finding by criteria: {e}", exc_info=True)
            return []

    def _apply_filters(self, query: Any, filters: dict[str, Any]) -> Any:
        """
        Apply filters to query.

        Args:
            query: SQLAlchemy query
            filters: Filters to apply

        Returns:
            Modified query
        """
        # Category filter
        if "category" in filters:
            query = query.join(Category).filter(Category.name == filters["category"].lower())

        # Subcategory filter
        if "subcategory" in filters:
            query = query.join(Subcategory).filter(Subcategory.name == filters["subcategory"].lower())

        # Brand filter
        if "brand" in filters:
            query = query.join(Brand).filter(Brand.name.ilike(f"%{filters['brand']}%"))

        # Price range filters
        if "min_price" in filters:
            query = query.filter(Product.price >= filters["min_price"])

        if "max_price" in filters:
            query = query.filter(Product.price <= filters["max_price"])

        # Stock filter
        if "min_stock" in filters:
            query = query.filter(Product.stock >= filters["min_stock"])

        # Active filter
        if "active" in filters:
            query = query.filter(Product.active == filters["active"])

        # Featured filter
        if "featured" in filters:
            query = query.filter(Product.featured == filters["featured"])

        # On sale filter
        if "on_sale" in filters:
            query = query.filter(Product.on_sale == filters["on_sale"])

        return query

    async def filter_by(self, **kwargs: Any) -> list[Product]:
        """
        Filter products by specific criteria (interface method).

        Args:
            **kwargs: Key-value pairs for filtering

        Returns:
            List of products matching the criteria
        """
        return await self.find_by_criteria(criteria=kwargs)
