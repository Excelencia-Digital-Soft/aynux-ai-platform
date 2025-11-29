"""
PgVector Metrics.

Single Responsibility: Collect and report vector store performance metrics.
Implements IVectorStoreMetrics interface.
"""

import logging
import time
from typing import Any

from sqlalchemy import func, select

from app.core.interfaces.vector_store import (
    IVectorStoreMetrics,
    VectorSearchResult,
)
from app.database.async_db import get_async_db_context
from app.models.db import Product

logger = logging.getLogger(__name__)


class PgVectorMetrics(IVectorStoreMetrics):
    """
    Metrics collector for pgvector operations.

    Single Responsibility: Collect and report vector store metrics.
    """

    def __init__(
        self,
        collection_name: str = "products",
        embedding_dimension: int = 768,
    ):
        """
        Initialize metrics collector.

        Args:
            collection_name: Name of the collection
            embedding_dimension: Dimension of embeddings
        """
        self._collection_name = collection_name
        self._embedding_dimension = embedding_dimension

    async def get_index_stats(self) -> dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dictionary with index statistics
        """
        try:
            async with get_async_db_context() as db:
                # Get count of documents with embeddings
                count_stmt = select(func.count(Product.id)).where(
                    Product.embedding.isnot(None)
                )
                count_result = await db.execute(count_stmt)
                count = count_result.scalar() or 0

                return {
                    "collection": self._collection_name,
                    "document_count": count,
                    "embedding_dimension": self._embedding_dimension,
                    "store_type": "pgvector",
                    "index_type": "HNSW",
                }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}

    async def get_search_performance(
        self,
        query: str,
        top_k: int = 5,
        search_func=None,
    ) -> tuple[list[VectorSearchResult], float]:
        """
        Execute search and measure performance.

        Args:
            query: Search query
            top_k: Number of results
            search_func: Search function to use

        Returns:
            Tuple of (results, elapsed_ms)
        """
        if search_func is None:
            logger.warning("No search function provided for performance test")
            return [], 0.0

        start_time = time.perf_counter()
        results = await search_func(query, top_k)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return results, elapsed_ms
