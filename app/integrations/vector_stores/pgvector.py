"""
PostgreSQL pgvector implementation of IVectorStore interface

Provides semantic search using PostgreSQL pgvector extension.
Implements the IVectorStore interface for maximum flexibility and testability.
"""

import logging
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.interfaces.vector_store import (
    Document,
    IHybridSearch,
    IVectorStore,
    IVectorStoreMetrics,
    VectorSearchResult,
    VectorStoreConnectionError,
    VectorStoreError,
    VectorStoreQueryError,
    VectorStoreType,
)
from app.database.async_db import get_async_db_context
from app.models.db import Brand, Category, Product

logger = logging.getLogger(__name__)


class PgVectorStore(IVectorStore, IHybridSearch, IVectorStoreMetrics):
    """
    PostgreSQL pgvector implementation of IVectorStore.

    Features:
    - Native SQL vector similarity search with pgvector extension
    - HNSW/IVFFlat indexing for sub-100ms query performance
    - Transactional consistency with application data
    - Automatic embedding generation and updates
    - Hybrid search combining vector + keyword matching

    Example:
        ```python
        store = PgVectorStore(collection_name="products", embedding_dimension=768)

        # Add documents
        docs = [
            Document(id="1", content="Laptop gaming HP", metadata={"price": 899}),
            Document(id="2", content="Mouse inalámbrico Logitech")
        ]
        await store.add_documents(docs)

        # Search
        results = await store.search("laptop económica", top_k=5)
        for result in results:
            print(f"{result.document.content} - Score: {result.score}")
        ```
    """

    def __init__(
        self,
        collection_name: str = "products",
        embedding_dimension: int = 768,
        embedding_model: Optional[Any] = None,
        db_session: Optional[AsyncSession] = None,
    ):
        """
        Initialize pgvector store.

        Args:
            collection_name: Name of the collection/table
            embedding_dimension: Dimension of embeddings (default: 768 for nomic-embed-text)
            embedding_model: Model for generating embeddings (optional)
            db_session: AsyncSession for database operations (optional, creates own if not provided)
        """
        self._collection_name = collection_name
        self._embedding_dimension = embedding_dimension
        self._embedding_model = embedding_model
        self._db_session = db_session
        self._default_similarity_threshold = 0.6

        logger.info(f"Initialized PgVectorStore: collection={collection_name}, " f"dimension={embedding_dimension}")

    @property
    def store_type(self) -> VectorStoreType:
        """Returns pgvector store type"""
        return VectorStoreType.PGVECTOR

    @property
    def collection_name(self) -> str:
        """Returns current collection name"""
        return self._collection_name

    def _format_vector_for_query(self, vector: List[float]) -> str:
        """
        Convert vector list to pgvector-compatible string format.

        Args:
            vector: List of floats

        Returns:
            String in format '[val1,val2,...]' for pgvector
        """
        return f"[{','.join(str(v) for v in vector)}]"

    def _vector_from_string(self, vector_str: str) -> List[float]:
        """
        Convert pgvector string format back to list.

        Args:
            vector_str: String like '[0.1,0.2,0.3]'

        Returns:
            List of floats
        """
        # Remove brackets and split
        clean_str = vector_str.strip("[]")
        return [float(v) for v in clean_str.split(",")]

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using embedding model.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            VectorStoreError: If embedding generation fails
        """
        if self._embedding_model is None:
            raise VectorStoreError("No embedding model configured")

        try:
            # Assuming embedding_model has an embed_text method
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
            raise VectorStoreError(f"Failed to generate embedding: {e}")

    async def add_documents(self, documents: List[Document], generate_embeddings: bool = True) -> List[str]:
        """
        Add documents to pgvector store.

        For products, this updates the embedding column in the products table.

        Args:
            documents: List of documents to add
            generate_embeddings: If True, generates embeddings automatically

        Returns:
            List of document IDs that were added

        Raises:
            VectorStoreError: If operation fails
        """
        if not documents:
            return []

        added_ids = []

        try:
            async with get_async_db_context() as db:
                for doc in documents:
                    # Generate embedding if needed
                    embedding = doc.embedding
                    if generate_embeddings and embedding is None:
                        embedding = await self._get_embedding(doc.content)

                    # For products collection, update product table
                    if self._collection_name == "products":
                        try:
                            product_id = int(doc.id)
                            embedding_str = self._format_vector_for_query(embedding)

                            # Update product embedding
                            stmt = text(
                                """
                                UPDATE products
                                SET embedding = :embedding::vector,
                                    updated_at = NOW()
                                WHERE id = :product_id
                            """
                            )

                            await db.execute(stmt, {"embedding": embedding_str, "product_id": product_id})

                            added_ids.append(doc.id)

                        except ValueError:
                            logger.warning(f"Invalid product ID: {doc.id}")
                            continue

                await db.commit()

            logger.info(f"Added {len(added_ids)} documents to {self._collection_name}")
            return added_ids

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}")

    async def search(
        self, query: str, top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None, min_score: float = 0.0
    ) -> List[VectorSearchResult]:
        """
        Semantic search using vector similarity.

        Args:
            query: Text query
            top_k: Number of results
            filter_metadata: Filters (category_id, brand_id, price_max, price_min, stock_required)
            min_score: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of search results ordered by similarity

        Raises:
            VectorStoreQueryError: If search fails
        """
        start_time = time.perf_counter()

        try:
            # Generate query embedding
            query_embedding = await self._get_embedding(query)

            # Use search_by_vector
            results = await self.search_by_vector(
                embedding=query_embedding, top_k=top_k, filter_metadata=filter_metadata
            )

            # Filter by min_score
            filtered_results = [r for r in results if r.score >= min_score]

            query_time = (time.perf_counter() - start_time) * 1000
            logger.info(f"pgvector search: query='{query}', found={len(filtered_results)}, " f"time={query_time:.2f}ms")

            return filtered_results

        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise VectorStoreQueryError(f"Search failed: {e}")

    async def search_by_vector(
        self, embedding: List[float], top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Search using embedding vector directly.

        Args:
            embedding: Query vector
            top_k: Number of results
            filter_metadata: Optional filters

        Returns:
            List of search results

        Raises:
            VectorStoreQueryError: If search fails
        """
        try:
            async with get_async_db_context() as db:
                # Build query
                embedding_str = self._format_vector_for_query(embedding)

                # Base query with vector similarity
                stmt = select(
                    Product,
                    func.coalesce(1 - (Product.embedding.cosine_distance(text(f"'{embedding_str}'::vector"))), 0).label(
                        "similarity"
                    ),
                ).where(Product.active == True, Product.embedding.isnot(None))

                # Apply metadata filters
                if filter_metadata:
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

                # Order by similarity and limit
                stmt = stmt.order_by(text("similarity DESC")).limit(top_k)

                # Execute
                result = await db.execute(stmt)
                rows = result.all()

                # Convert to VectorSearchResult
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
                            distance=1.0 - float(similarity),  # Convert similarity to distance
                        )
                    )

                return search_results

        except Exception as e:
            logger.error(f"Error in vector search by embedding: {e}")
            raise VectorStoreQueryError(f"Search by vector failed: {e}")

    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """
        Get document by ID.

        Args:
            document_id: Document ID

        Returns:
            Document or None
        """
        try:
            async with get_async_db_context() as db:
                product_id = int(document_id)
                stmt = select(Product).where(Product.id == product_id)
                result = await db.execute(stmt)
                product = result.scalar_one_or_none()

                if product:
                    # Convert embedding string to list if exists
                    embedding = None
                    if product.embedding:
                        embedding = self._vector_from_string(str(product.embedding))

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

    async def delete(self, document_ids: List[str]) -> int:
        """
        Delete documents by IDs.

        For products, this sets embedding to NULL rather than deleting the product.

        Args:
            document_ids: List of document IDs

        Returns:
            Number of documents deleted/updated
        """
        try:
            async with get_async_db_context() as db:
                product_ids = [int(id) for id in document_ids if id.isdigit()]

                stmt = text(
                    """
                    UPDATE products
                    SET embedding = NULL,
                        updated_at = NOW()
                    WHERE id = ANY(:product_ids)
                """
                )

                result = await db.execute(stmt, {"product_ids": product_ids})
                await db.commit()

                deleted_count = result.rowcount
                logger.info(f"Cleared embeddings for {deleted_count} products")
                return deleted_count

        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise VectorStoreError(f"Failed to delete documents: {e}")

    async def update_document(
        self,
        document_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        regenerate_embedding: bool = True,
    ) -> bool:
        """
        Update an existing document.

        Args:
            document_id: Document ID
            content: New content (optional)
            metadata: New metadata (optional)
            regenerate_embedding: If True, regenerates embedding

        Returns:
            True if updated successfully
        """
        try:
            # For products, content update means updating product name/description
            # Metadata update means updating other product fields
            # This is a simplified version - in production you'd update Product model directly

            if regenerate_embedding and content:
                embedding = await self._get_embedding(content)
                embedding_str = self._format_vector_for_query(embedding)

                async with get_async_db_context() as db:
                    product_id = int(document_id)
                    stmt = text(
                        """
                        UPDATE products
                        SET embedding = :embedding::vector,
                            updated_at = NOW()
                        WHERE id = :product_id
                    """
                    )

                    await db.execute(stmt, {"embedding": embedding_str, "product_id": product_id})
                    await db.commit()

                return True

            return False

        except Exception as e:
            logger.error(f"Error updating document {document_id}: {e}")
            return False

    async def create_collection(self, collection_name: str, embedding_dimension: int = 1024) -> bool:
        """
        Create a new collection.

        For pgvector, this would create a new table with vector column.
        For products, the table already exists.

        Args:
            collection_name: Collection name
            embedding_dimension: Embedding dimension

        Returns:
            True if created
        """
        # For products collection, table already exists
        if collection_name == "products":
            logger.info("Products table already exists")
            return True

        # For other collections, you'd need to create table
        # This is a placeholder - implement as needed
        logger.warning(f"Collection creation not implemented for: {collection_name}")
        return False

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.

        For products, this clears all embeddings rather than dropping table.

        Args:
            collection_name: Collection to delete

        Returns:
            True if deleted
        """
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

    async def count_documents(self, filter_metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents in collection.

        Args:
            filter_metadata: Optional filters

        Returns:
            Document count
        """
        try:
            async with get_async_db_context() as db:
                stmt = select(func.count(Product.id)).where(Product.active == True, Product.embedding.isnot(None))

                # Apply filters
                if filter_metadata:
                    if "category_id" in filter_metadata:
                        stmt = stmt.where(Product.category_id == filter_metadata["category_id"])
                    if "brand_id" in filter_metadata:
                        stmt = stmt.where(Product.brand_id == filter_metadata["brand_id"])

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
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Hybrid search combining vector similarity and keyword matching.

        Args:
            query: Search query
            top_k: Number of results
            vector_weight: Weight for vector similarity (0.0-1.0)
            keyword_weight: Weight for keyword matching (0.0-1.0)
            filter_metadata: Optional filters

        Returns:
            Combined search results
        """
        # Implementation would combine pgvector similarity with PostgreSQL full-text search
        # For now, returning pure vector search
        # TODO: Implement full hybrid search with ts_vector
        logger.info(f"Hybrid search (using vector only for now): {query}")
        return await self.search(query, top_k, filter_metadata)

    # IVectorStoreMetrics implementation
    async def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        try:
            async with get_async_db_context() as db:
                # Get count
                count_stmt = select(func.count(Product.id)).where(Product.embedding.isnot(None))
                count_result = await db.execute(count_stmt)
                count = count_result.scalar() or 0

                return {
                    "collection": self._collection_name,
                    "document_count": count,
                    "embedding_dimension": self._embedding_dimension,
                    "store_type": "pgvector",
                    "index_type": "HNSW",  # Assuming HNSW index
                }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}

    async def get_search_performance(self, query: str, top_k: int = 5) -> Tuple[List[VectorSearchResult], float]:
        """Execute search and measure performance"""
        start_time = time.perf_counter()
        results = await self.search(query, top_k)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return results, elapsed_ms
