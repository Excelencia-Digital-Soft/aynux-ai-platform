"""
PgVector Product Search.

Handles vector similarity search for products using pgvector extension.
"""

import logging
import time
from typing import Any

from sqlalchemy import and_, select, text

from app.config.langsmith_config import trace_integration
from app.database.async_db import get_async_db_context
from app.integrations.vector_stores.pgvector_metrics_service import get_metrics_service
from app.models.db import Brand, Category, Product

logger = logging.getLogger(__name__)


class PgVectorProductSearch:
    """
    Vector similarity search for products using pgvector.

    Responsibilities:
    - Execute vector similarity searches
    - Apply metadata filters
    - Format results with relationships
    - Track search metrics
    """

    def __init__(self, metrics_service=None):
        """
        Initialize product search.

        Args:
            metrics_service: Optional metrics service (uses default if None)
        """
        self.metrics = metrics_service or get_metrics_service()
        self.default_similarity_threshold = 0.6
        self.default_k = 10

    def format_vector_for_query(self, vector: list[float]) -> str:
        """
        Convert vector list to pgvector-compatible string format.

        Args:
            vector: List of floats representing the embedding

        Returns:
            String in format '[val1,val2,val3,...]' for pgvector
        """
        return f"[{','.join(str(v) for v in vector)}]"

    @trace_integration("pgvector_search_products")
    async def search_similar_products(
        self,
        query_embedding: list[float],
        k: int = 10,
        metadata_filters: dict[str, Any] | None = None,
        min_similarity: float = 0.7,
        query_text: str | None = None,
    ) -> list[tuple[Product, float]]:
        """
        Search for similar products using vector similarity.

        Args:
            query_embedding: Query vector (768 dimensions)
            k: Number of results to return
            metadata_filters: Optional filters (category_id, brand_id, etc.)
            min_similarity: Minimum similarity threshold (0.0-1.0)
            query_text: Original query text for metrics tracking

        Returns:
            List of (Product, similarity_score) tuples
        """
        start_time = time.perf_counter()
        error = None
        results: list[tuple[Product, float]] = []

        try:
            async with get_async_db_context() as db:
                query_vector_str = self.format_vector_for_query(query_embedding)

                # Build query with vector similarity
                query = (
                    select(
                        Product,
                        Category,
                        Brand,
                        text(f"1 - (embedding <=> '{query_vector_str}'::vector) AS similarity"),
                    )
                    .join(Category, Product.category_id == Category.id, isouter=True)
                    .join(Brand, Product.brand_id == Brand.id, isouter=True)
                    .where(
                        and_(
                            Product.embedding.isnot(None),
                            Product.active.is_(True),
                            text(f"1 - (embedding <=> '{query_vector_str}'::vector) >= {min_similarity}"),
                        )
                    )
                )

                # Apply metadata filters
                if metadata_filters:
                    query = self._apply_metadata_filters(query, metadata_filters)

                query = query.order_by(text("similarity DESC")).limit(k)

                result = await db.execute(query)
                rows = result.all()

                # Format results
                products_with_scores = []
                for row in rows:
                    product = row[0]
                    category = row[1]
                    brand = row[2]
                    similarity = float(row[3])

                    product.category = category
                    product.brand = brand

                    products_with_scores.append((product, similarity))

                results = products_with_scores
                logger.info(f"pgvector search found {len(products_with_scores)} products")

                return products_with_scores

        except Exception as e:
            error = str(e)
            logger.error(f"Error in pgvector search: {e}")
            return []
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.metrics.record_search(
                query=query_text or "unknown",
                duration_ms=duration_ms,
                results=results,
                filters_applied=bool(metadata_filters),
                error=error,
            )

    def _apply_metadata_filters(self, query, filters: dict[str, Any]):
        """
        Apply metadata filters to vector search query.

        Supported filters:
        - category_id: UUID
        - brand_id: UUID
        - price_min/price_max: float
        - stock_required: bool
        - featured_only: bool
        - on_sale_only: bool
        """
        filter_conditions = []

        if filters.get("category_id"):
            filter_conditions.append(Product.category_id == filters["category_id"])

        if filters.get("brand_id"):
            filter_conditions.append(Product.brand_id == filters["brand_id"])

        if filters.get("price_min") is not None:
            filter_conditions.append(Product.price >= filters["price_min"])

        if filters.get("price_max") is not None:
            filter_conditions.append(Product.price <= filters["price_max"])

        if filters.get("stock_required", False):
            filter_conditions.append(Product.stock > 0)

        if filters.get("featured_only", False):
            filter_conditions.append(Product.featured.is_(True))

        if filters.get("on_sale_only", False):
            filter_conditions.append(Product.on_sale.is_(True))

        if filter_conditions:
            query = query.where(and_(*filter_conditions))

        return query

    async def health_check(self) -> bool:
        """
        Check if pgvector is available and working.

        Returns:
            True if pgvector is operational
        """
        try:
            async with get_async_db_context() as db:
                # Check extension
                result = await db.execute(
                    text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
                )
                if result.scalar() == 0:
                    logger.error("pgvector extension not installed")
                    return False

                # Check column
                result = await db.execute(
                    text("""
                        SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = 'products' AND column_name = 'embedding'
                    """)
                )
                if result.scalar() == 0:
                    logger.error("products.embedding column not found")
                    return False

                logger.info("pgvector health check passed")
                return True

        except Exception as e:
            logger.error(f"pgvector health check failed: {e}")
            return False
