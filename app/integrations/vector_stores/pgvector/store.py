"""
PostgreSQL pgvector implementation of IVectorStore interface.

Single Responsibility: CRUD operations and search orchestration for vector documents.
Uses composition for search and metrics.
"""

import logging
import time
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interfaces.vector_store import (
    Document,
    IHybridSearch,
    IVectorStore,
    VectorSearchResult,
    VectorStoreError,
    VectorStoreQueryError,
    VectorStoreType,
)
from app.database.async_db import get_async_db_context
from app.integrations.vector_stores.pgvector.metrics import PgVectorMetrics
from app.integrations.vector_stores.pgvector.search_engine import PgVectorSearchEngine
from app.integrations.vector_stores.pgvector.vector_helpers import (
    format_vector_for_query,
    vector_from_string,
)
from app.models.db import Product

logger = logging.getLogger(__name__)


class PgVectorStore(IVectorStore, IHybridSearch):
    """
    PostgreSQL pgvector implementation of IVectorStore.

    Uses composition:
    - PgVectorSearchEngine for search operations
    - PgVectorMetrics for metrics collection
    - vector_helpers for vector formatting
    """

    def __init__(
        self,
        collection_name: str = "products",
        embedding_dimension: int = 768,
        embedding_model: Any | None = None,
        db_session: AsyncSession | None = None,
    ):
        """
        Initialize pgvector store.

        Args:
            collection_name: Name of the collection/table
            embedding_dimension: Dimension of embeddings (768 for nomic-embed-text)
            embedding_model: Model for generating embeddings (optional)
            db_session: AsyncSession for database operations (optional)
        """
        self._collection_name = collection_name
        self._embedding_dimension = embedding_dimension
        self._embedding_model = embedding_model
        self._db_session = db_session

        # Compose dependencies
        self._search_engine = PgVectorSearchEngine(collection_name)
        self._metrics = PgVectorMetrics(collection_name, embedding_dimension)

        logger.info(
            f"Initialized PgVectorStore: collection={collection_name}, "
            f"dimension={embedding_dimension}"
        )

    @property
    def store_type(self) -> VectorStoreType:
        """Returns pgvector store type."""
        return VectorStoreType.PGVECTOR

    @property
    def collection_name(self) -> str:
        """Returns current collection name."""
        return self._collection_name

    @property
    def metrics(self) -> PgVectorMetrics:
        """Returns metrics instance."""
        return self._metrics

    async def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using embedding model."""
        if self._embedding_model is None:
            raise VectorStoreError("No embedding model configured")

        try:
            if hasattr(self._embedding_model, "embed_text"):
                return await self._embedding_model.embed_text(text)
            elif hasattr(self._embedding_model, "generate_embedding"):
                return await self._embedding_model.generate_embedding(text)
            else:
                raise VectorStoreError(
                    f"Embedding model {type(self._embedding_model)} "
                    "does not have embed_text or generate_embedding method"
                )
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise VectorStoreError(f"Failed to generate embedding: {e}") from e

    async def add_documents(
        self,
        documents: list[Document],
        generate_embeddings: bool = True,
    ) -> list[str]:
        """Add documents to pgvector store."""
        if not documents:
            return []

        added_ids = []

        try:
            async with get_async_db_context() as db:
                for doc in documents:
                    embedding = doc.embedding
                    if generate_embeddings and embedding is None:
                        embedding = await self._get_embedding(doc.content)

                    if self._collection_name == "products":
                        try:
                            product_id = int(doc.id)
                            embedding_str = format_vector_for_query(embedding)

                            stmt = text("""
                                UPDATE products
                                SET embedding = :embedding::vector,
                                    updated_at = NOW()
                                WHERE id = :product_id
                            """)

                            await db.execute(
                                stmt,
                                {"embedding": embedding_str, "product_id": product_id},
                            )
                            added_ids.append(doc.id)

                        except ValueError:
                            logger.warning(f"Invalid product ID: {doc.id}")
                            continue

                await db.commit()

            logger.info(f"Added {len(added_ids)} documents to {self._collection_name}")
            return added_ids

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}") from e

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Semantic search using vector similarity."""
        start_time = time.perf_counter()

        try:
            query_embedding = await self._get_embedding(query)
            results = await self._search_engine.search_by_vector(
                embedding=query_embedding,
                top_k=top_k,
                filter_metadata=filter_metadata,
            )

            filtered_results = [r for r in results if r.score >= min_score]

            query_time = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"pgvector search: query='{query}', found={len(filtered_results)}, "
                f"time={query_time:.2f}ms"
            )

            return filtered_results

        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise VectorStoreQueryError(f"Search failed: {e}") from e

    async def search_by_vector(
        self,
        embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Search using embedding vector directly (delegated to search engine)."""
        return await self._search_engine.search_by_vector(
            embedding, top_k, filter_metadata
        )

    async def get_by_id(self, document_id: str) -> Document | None:
        """Get document by ID."""
        try:
            async with get_async_db_context() as db:
                product_id = int(document_id)
                stmt = select(Product).where(Product.id == product_id)
                result = await db.execute(stmt)
                product = result.scalar_one_or_none()

                if product:
                    embedding = None
                    if product.embedding:
                        embedding = vector_from_string(str(product.embedding))

                    return Document(
                        id=str(product.id),
                        content=f"{product.name} - {product.description or ''}",
                        embedding=embedding,
                        metadata={
                            "name": product.name,
                            "price": float(product.price) if product.price else 0.0,
                            "category_id": product.category_id,
                            "brand_id": product.brand_id,
                            "stock": product.stock or 0,
                            "sku": product.sku,
                        },
                    )

                return None

        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None

    async def delete(self, document_ids: list[str]) -> int:
        """Delete documents by IDs (sets embedding to NULL)."""
        try:
            async with get_async_db_context() as db:
                product_ids = [int(id) for id in document_ids if id.isdigit()]

                stmt = text("""
                    UPDATE products
                    SET embedding = NULL, updated_at = NOW()
                    WHERE id = ANY(:product_ids)
                """)

                result = await db.execute(stmt, {"product_ids": product_ids})
                await db.commit()

                deleted_count = result.rowcount
                logger.info(f"Cleared embeddings for {deleted_count} products")
                return deleted_count

        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise VectorStoreError(f"Failed to delete documents: {e}") from e

    async def update_document(
        self,
        document_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        regenerate_embedding: bool = True,
    ) -> bool:
        """Update an existing document."""
        try:
            if regenerate_embedding and content:
                embedding = await self._get_embedding(content)
                embedding_str = format_vector_for_query(embedding)

                async with get_async_db_context() as db:
                    product_id = int(document_id)
                    stmt = text("""
                        UPDATE products
                        SET embedding = :embedding::vector, updated_at = NOW()
                        WHERE id = :product_id
                    """)

                    await db.execute(
                        stmt,
                        {"embedding": embedding_str, "product_id": product_id},
                    )
                    await db.commit()

                return True

            return False

        except Exception as e:
            logger.error(f"Error updating document {document_id}: {e}")
            return False

    async def create_collection(
        self,
        collection_name: str,
        embedding_dimension: int = 1024,
    ) -> bool:
        """Create a new collection (products table already exists)."""
        if collection_name == "products":
            logger.info("Products table already exists")
            return True

        logger.warning(f"Collection creation not implemented for: {collection_name}")
        return False

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection (clears all embeddings for products)."""
        try:
            if collection_name == "products":
                async with get_async_db_context() as db:
                    stmt = text("UPDATE products SET embedding = NULL")
                    await db.execute(stmt)
                    await db.commit()
                    logger.info(f"Cleared all embeddings from {collection_name}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False

    async def count_documents(
        self,
        filter_metadata: dict[str, Any] | None = None,
    ) -> int:
        """Count documents in collection."""
        try:
            async with get_async_db_context() as db:
                stmt = select(func.count(Product.id)).where(
                    Product.active,
                    Product.embedding.isnot(None),
                )

                if filter_metadata:
                    if "category_id" in filter_metadata:
                        stmt = stmt.where(
                            Product.category_id == filter_metadata["category_id"]
                        )
                    if "brand_id" in filter_metadata:
                        stmt = stmt.where(
                            Product.brand_id == filter_metadata["brand_id"]
                        )

                result = await db.execute(stmt)
                count = result.scalar()
                return count or 0

        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0

    # IHybridSearch implementation
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Hybrid search (currently uses vector only, TODO: add ts_vector)."""
        logger.info(f"Hybrid search (using vector only for now): {query}")
        return await self.search(query, top_k, filter_metadata)

    # Metrics delegation
    async def get_index_stats(self) -> dict[str, Any]:
        """Get index statistics (delegated to PgVectorMetrics)."""
        return await self._metrics.get_index_stats()

    async def get_search_performance(
        self,
        query: str,
        top_k: int = 5,
    ) -> tuple[list[VectorSearchResult], float]:
        """Execute search and measure performance."""
        return await self._metrics.get_search_performance(
            query, top_k, search_func=self.search
        )
