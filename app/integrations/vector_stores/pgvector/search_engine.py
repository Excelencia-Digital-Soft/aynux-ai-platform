"""
PgVector Search Engine.

Single Responsibility: Execute vector similarity searches against pgvector.
"""

import logging
import time
from typing import Any

from sqlalchemy import func, select, text

from app.core.interfaces.vector_store import (
    Document,
    VectorSearchResult,
    VectorStoreQueryError,
)
from app.database.async_db import get_async_db_context
from app.integrations.vector_stores.pgvector.vector_helpers import (
    format_vector_for_query,
)
from app.models.db import Product

logger = logging.getLogger(__name__)


class PgVectorSearchEngine:
    """
    Vector search engine for pgvector.

    Single Responsibility: Execute and format vector similarity searches.
    """

    def __init__(self, collection_name: str = "products"):
        """
        Initialize search engine.

        Args:
            collection_name: Name of the collection to search
        """
        self._collection_name = collection_name

    async def search_by_vector(
        self,
        embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """
        Search using embedding vector directly.

        Args:
            embedding: Query vector
            top_k: Number of results
            filter_metadata: Optional filters

        Returns:
            List of search results
        """
        try:
            async with get_async_db_context() as db:
                embedding_str = format_vector_for_query(embedding)

                stmt = select(
                    Product,
                    func.coalesce(
                        1
                        - (
                            Product.embedding.cosine_distance(
                                text(f"'{embedding_str}'::vector")
                            )
                        ),
                        0,
                    ).label("similarity"),
                ).where(Product.active, Product.embedding.isnot(None))

                # Apply metadata filters
                stmt = self._apply_filters(stmt, filter_metadata)
                stmt = stmt.order_by(text("similarity DESC")).limit(top_k)

                result = await db.execute(stmt)
                rows = result.all()

                return self._format_results(rows)

        except Exception as e:
            logger.error(f"Error in vector search by embedding: {e}")
            raise VectorStoreQueryError(f"Search by vector failed: {e}") from e

    def _apply_filters(self, stmt, filter_metadata: dict[str, Any] | None):
        """Apply metadata filters to query."""
        if not filter_metadata:
            return stmt

        if "category_id" in filter_metadata:
            stmt = stmt.where(Product.category_id == filter_metadata["category_id"])

        if "brand_id" in filter_metadata:
            stmt = stmt.where(Product.brand_id == filter_metadata["brand_id"])

        if "price_max" in filter_metadata:
            stmt = stmt.where(Product.price <= filter_metadata["price_max"])

        if "price_min" in filter_metadata:
            stmt = stmt.where(Product.price >= filter_metadata["price_min"])

        if filter_metadata.get("stock_required", False):
            stmt = stmt.where(Product.stock > 0)

        return stmt

    def _format_results(self, rows: list[tuple]) -> list[VectorSearchResult]:
        """Format database rows to VectorSearchResult."""
        search_results = []
        for product, similarity in rows:
            doc = Document(
                id=str(product.id),
                content=f"{product.name} - {product.description or ''}",
                metadata={
                    "name": product.name,
                    "price": float(product.price) if product.price else 0.0,
                    "category_id": product.category_id,
                    "brand_id": product.brand_id,
                    "stock": product.stock or 0,
                    "sku": product.sku,
                },
                score=similarity,
            )

            search_results.append(
                VectorSearchResult(
                    document=doc,
                    score=float(similarity),
                    distance=1.0 - float(similarity),
                )
            )

        return search_results

    async def search_with_timing(
        self,
        embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> tuple[list[VectorSearchResult], float]:
        """
        Search and return results with timing.

        Args:
            embedding: Query vector
            top_k: Number of results
            filter_metadata: Optional filters

        Returns:
            Tuple of (results, elapsed_ms)
        """
        start_time = time.perf_counter()
        results = await self.search_by_vector(embedding, top_k, filter_metadata)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return results, elapsed_ms
