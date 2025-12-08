# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Vector store con aislamiento por tenant. Filtra documentos por
#              organization_id automáticamente para búsquedas RAG aisladas.
# Tenant-Aware: Yes - todas las operaciones filtran por org_id.
# ============================================================================
"""
TenantVectorStore - Multi-tenant aware vector store wrapper.

Wraps the base PgVectorStore to provide tenant isolation for RAG operations.
Each tenant has their own documents stored in tenant_documents table.

Features:
- Automatic tenant filtering based on TenantContext
- Support for both shared products and tenant-specific documents
- Configurable similarity threshold per tenant
- Index management per tenant (partial HNSW indexes)

Usage:
    tenant_store = TenantVectorStore(organization_id=org_id)
    results = await tenant_store.search("query", top_k=5)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any

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
from app.models.db.tenancy import TenantDocument

from .context import TenantContext, get_tenant_context

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TenantVectorStore(IVectorStore, IHybridSearch):
    """
    Multi-tenant vector store for tenant-isolated RAG operations.

    Stores and retrieves documents from the tenant_documents table,
    automatically filtering by organization_id based on TenantContext.

    Supports:
    - Semantic search using pgvector embeddings
    - Full-text search using TSVECTOR
    - Hybrid search combining both methods
    - Tenant-specific similarity thresholds

    Example:
        >>> ctx = get_tenant_context()
        >>> store = TenantVectorStore(organization_id=ctx.organization_id)
        >>> results = await store.search("how to return a product")
    """

    def __init__(
        self,
        organization_id: uuid.UUID | None = None,
        embedding_dimension: int = 768,
        embedding_model: Any | None = None,
        db_session: AsyncSession | None = None,
        similarity_threshold: float | None = None,
        max_results: int | None = None,
    ):
        """
        Initialize tenant-aware vector store.

        Args:
            organization_id: Organization UUID (uses TenantContext if None).
            embedding_dimension: Dimension of embeddings (768 for nomic-embed-text).
            embedding_model: Model for generating embeddings.
            db_session: AsyncSession for database operations.
            similarity_threshold: Minimum similarity score (uses tenant config if None).
            max_results: Maximum results to return (uses tenant config if None).
        """
        self._organization_id = organization_id
        self._embedding_dimension = embedding_dimension
        self._embedding_model = embedding_model
        self._db_session = db_session
        self._custom_similarity_threshold = similarity_threshold
        self._custom_max_results = max_results

        logger.info(
            f"Initialized TenantVectorStore: org_id={organization_id}, "
            f"dimension={embedding_dimension}"
        )

    @property
    def organization_id(self) -> uuid.UUID:
        """Get organization ID from context or explicit setting."""
        if self._organization_id:
            return self._organization_id

        ctx = get_tenant_context()
        if ctx:
            return ctx.organization_id

        raise VectorStoreError(
            "No organization ID available. Set organization_id or ensure TenantContext is set."
        )

    @property
    def store_type(self) -> VectorStoreType:
        """Returns pgvector store type."""
        return VectorStoreType.PGVECTOR

    @property
    def collection_name(self) -> str:
        """Returns tenant-specific collection name."""
        return f"tenant_documents_{self.organization_id}"

    @property
    def similarity_threshold(self) -> float:
        """Get similarity threshold from tenant config or explicit setting."""
        if self._custom_similarity_threshold is not None:
            return self._custom_similarity_threshold

        ctx = get_tenant_context()
        if ctx:
            return ctx.rag_similarity_threshold

        return 0.7  # Default

    @property
    def max_results(self) -> int:
        """Get max results from tenant config or explicit setting."""
        if self._custom_max_results is not None:
            return self._custom_max_results

        ctx = get_tenant_context()
        if ctx:
            return ctx.rag_max_results

        return 5  # Default

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
        """
        Add documents to tenant's knowledge base.

        Args:
            documents: List of documents to add.
            generate_embeddings: Whether to generate embeddings.

        Returns:
            List of added document IDs.
        """
        if not documents:
            return []

        added_ids = []
        org_id = self.organization_id

        try:
            async with get_async_db_context() as db:
                for doc in documents:
                    embedding = doc.embedding
                    if generate_embeddings and embedding is None:
                        embedding = await self._get_embedding(doc.content)

                    # Create TenantDocument
                    tenant_doc = TenantDocument(
                        organization_id=org_id,
                        title=doc.metadata.get("title", doc.id) if doc.metadata else doc.id,
                        content=doc.content,
                        document_type=doc.metadata.get("document_type", "general") if doc.metadata else "general",
                        category=doc.metadata.get("category") if doc.metadata else None,
                        tags=doc.metadata.get("tags", []) if doc.metadata else [],
                        meta_data=doc.metadata or {},
                        embedding=embedding,
                        active=True,
                        sort_order=0,
                    )

                    db.add(tenant_doc)
                    await db.flush()
                    added_ids.append(str(tenant_doc.id))

                await db.commit()

            logger.info(f"Added {len(added_ids)} documents to tenant {org_id}")
            return added_ids

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise VectorStoreError(f"Failed to add documents: {e}") from e

    async def search(
        self,
        query: str,
        top_k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[VectorSearchResult]:
        """
        Semantic search in tenant's knowledge base.

        Args:
            query: Search query text.
            top_k: Maximum results (uses tenant config if None).
            filter_metadata: Additional filters (document_type, category, tags).
            min_score: Minimum similarity score (uses tenant config if None).

        Returns:
            List of search results with scores.
        """
        start_time = time.perf_counter()
        top_k = top_k or self.max_results
        min_score = min_score if min_score is not None else self.similarity_threshold

        try:
            query_embedding = await self._get_embedding(query)
            results = await self.search_by_vector(
                embedding=query_embedding,
                top_k=top_k,
                filter_metadata=filter_metadata,
            )

            # Filter by minimum score
            filtered_results = [r for r in results if r.score >= min_score]

            query_time = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"Tenant vector search: org={self.organization_id}, "
                f"query='{query[:50]}...', found={len(filtered_results)}, "
                f"time={query_time:.2f}ms"
            )

            return filtered_results

        except Exception as e:
            logger.error(f"Error in tenant vector search: {e}")
            raise VectorStoreQueryError(f"Search failed: {e}") from e

    async def search_by_vector(
        self,
        embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """
        Search using embedding vector directly.

        Args:
            embedding: Query embedding vector.
            top_k: Maximum results.
            filter_metadata: Additional filters.

        Returns:
            List of search results.
        """
        org_id = self.organization_id
        filter_metadata = filter_metadata or {}

        try:
            async with get_async_db_context() as db:
                # Build vector string for pgvector
                vector_str = "[" + ",".join(str(x) for x in embedding) + "]"

                # Base query with tenant filter
                base_query = """
                    SELECT
                        id,
                        title,
                        content,
                        document_type,
                        category,
                        tags,
                        meta_data,
                        1 - (embedding <=> :query_vector::vector) as similarity
                    FROM tenant_documents
                    WHERE organization_id = :org_id
                      AND active = true
                      AND embedding IS NOT NULL
                """

                params: dict[str, Any] = {
                    "query_vector": vector_str,
                    "org_id": str(org_id),
                }

                # Add filters
                if "document_type" in filter_metadata:
                    base_query += " AND document_type = :doc_type"
                    params["doc_type"] = filter_metadata["document_type"]

                if "category" in filter_metadata:
                    base_query += " AND category = :category"
                    params["category"] = filter_metadata["category"]

                if "tags" in filter_metadata:
                    # Array overlap check
                    base_query += " AND tags && :tags"
                    params["tags"] = filter_metadata["tags"]

                # Order and limit
                base_query += """
                    ORDER BY similarity DESC
                    LIMIT :limit
                """
                params["limit"] = top_k

                result = await db.execute(text(base_query), params)
                rows = result.fetchall()

                results = []
                for row in rows:
                    results.append(
                        VectorSearchResult(
                            id=str(row.id),
                            content=row.content,
                            score=float(row.similarity),
                            metadata={
                                "title": row.title,
                                "document_type": row.document_type,
                                "category": row.category,
                                "tags": row.tags or [],
                                **(row.meta_data or {}),
                            },
                        )
                    )

                return results

        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise VectorStoreQueryError(f"Vector search failed: {e}") from e

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """
        Hybrid search combining vector similarity and full-text search.

        Args:
            query: Search query text.
            top_k: Maximum results.
            vector_weight: Weight for vector similarity (0-1).
            keyword_weight: Weight for keyword matching (0-1).
            filter_metadata: Additional filters.

        Returns:
            List of search results with combined scores.
        """
        org_id = self.organization_id
        filter_metadata = filter_metadata or {}

        try:
            query_embedding = await self._get_embedding(query)
            vector_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            async with get_async_db_context() as db:
                # Hybrid query combining vector and text search
                hybrid_query = """
                    WITH vector_results AS (
                        SELECT
                            id,
                            title,
                            content,
                            document_type,
                            category,
                            tags,
                            meta_data,
                            1 - (embedding <=> :query_vector::vector) as vector_score
                        FROM tenant_documents
                        WHERE organization_id = :org_id
                          AND active = true
                          AND embedding IS NOT NULL
                    ),
                    text_results AS (
                        SELECT
                            id,
                            ts_rank(search_vector, plainto_tsquery('spanish', :query)) as text_score
                        FROM tenant_documents
                        WHERE organization_id = :org_id
                          AND active = true
                          AND search_vector @@ plainto_tsquery('spanish', :query)
                    )
                    SELECT
                        v.id,
                        v.title,
                        v.content,
                        v.document_type,
                        v.category,
                        v.tags,
                        v.meta_data,
                        (v.vector_score * :vector_weight +
                         COALESCE(t.text_score, 0) * :keyword_weight) as combined_score
                    FROM vector_results v
                    LEFT JOIN text_results t ON v.id = t.id
                    ORDER BY combined_score DESC
                    LIMIT :limit
                """

                params = {
                    "query_vector": vector_str,
                    "org_id": str(org_id),
                    "query": query,
                    "vector_weight": vector_weight,
                    "keyword_weight": keyword_weight,
                    "limit": top_k,
                }

                result = await db.execute(text(hybrid_query), params)
                rows = result.fetchall()

                results = []
                for row in rows:
                    results.append(
                        VectorSearchResult(
                            id=str(row.id),
                            content=row.content,
                            score=float(row.combined_score),
                            metadata={
                                "title": row.title,
                                "document_type": row.document_type,
                                "category": row.category,
                                "tags": row.tags or [],
                                **(row.meta_data or {}),
                            },
                        )
                    )

                logger.info(
                    f"Tenant hybrid search: org={org_id}, query='{query[:30]}...', "
                    f"found={len(results)}"
                )

                return results

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            # Fall back to vector-only search
            return await self.search(query, top_k, filter_metadata)

    async def get_by_id(self, document_id: str) -> Document | None:
        """Get document by ID (tenant-scoped)."""
        org_id = self.organization_id

        try:
            doc_uuid = uuid.UUID(document_id)
            async with get_async_db_context() as db:
                stmt = select(TenantDocument).where(
                    TenantDocument.id == doc_uuid,
                    TenantDocument.organization_id == org_id,
                )
                result = await db.execute(stmt)
                tenant_doc = result.scalar_one_or_none()

                if tenant_doc:
                    return Document(
                        id=str(tenant_doc.id),
                        content=tenant_doc.content,
                        embedding=list(tenant_doc.embedding) if tenant_doc.embedding else None,
                        metadata={
                            "title": tenant_doc.title,
                            "document_type": tenant_doc.document_type,
                            "category": tenant_doc.category,
                            "tags": tenant_doc.tags or [],
                            **(tenant_doc.meta_data or {}),
                        },
                    )

                return None

        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None

    async def delete(self, document_ids: list[str]) -> int:
        """Delete documents by IDs (tenant-scoped)."""
        org_id = self.organization_id

        try:
            async with get_async_db_context() as db:
                doc_uuids = [uuid.UUID(id) for id in document_ids]

                stmt = text("""
                    DELETE FROM tenant_documents
                    WHERE id = ANY(:doc_ids)
                      AND organization_id = :org_id
                """)

                result = await db.execute(
                    stmt,
                    {"doc_ids": [str(u) for u in doc_uuids], "org_id": str(org_id)},
                )
                await db.commit()

                deleted_count = result.rowcount
                logger.info(f"Deleted {deleted_count} documents from tenant {org_id}")
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
        """Update an existing document (tenant-scoped)."""
        org_id = self.organization_id

        try:
            doc_uuid = uuid.UUID(document_id)
            async with get_async_db_context() as db:
                stmt = select(TenantDocument).where(
                    TenantDocument.id == doc_uuid,
                    TenantDocument.organization_id == org_id,
                )
                result = await db.execute(stmt)
                tenant_doc = result.scalar_one_or_none()

                if not tenant_doc:
                    return False

                if content:
                    tenant_doc.content = content
                    if regenerate_embedding:
                        tenant_doc.embedding = await self._get_embedding(content)

                if metadata:
                    if "title" in metadata:
                        tenant_doc.title = metadata["title"]
                    if "document_type" in metadata:
                        tenant_doc.document_type = metadata["document_type"]
                    if "category" in metadata:
                        tenant_doc.category = metadata["category"]
                    if "tags" in metadata:
                        tenant_doc.tags = metadata["tags"]
                    # Merge remaining metadata
                    tenant_doc.meta_data = {**(tenant_doc.meta_data or {}), **metadata}

                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Error updating document {document_id}: {e}")
            return False

    async def create_collection(
        self,
        collection_name: str,
        embedding_dimension: int = 768,
    ) -> bool:
        """
        Create partial HNSW index for this tenant.

        Creates a partial index on tenant_documents for this organization
        to improve search performance.
        """
        org_id = self.organization_id

        try:
            async with get_async_db_context() as db:
                # Create partial HNSW index for this tenant
                index_name = f"idx_tenant_docs_hnsw_{org_id.hex[:8]}"

                index_query = text(f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON tenant_documents
                    USING hnsw (embedding vector_cosine_ops)
                    WHERE organization_id = :org_id
                """)

                await db.execute(index_query, {"org_id": str(org_id)})
                await db.commit()

                logger.info(f"Created HNSW index {index_name} for tenant {org_id}")
                return True

        except Exception as e:
            logger.error(f"Error creating tenant index: {e}")
            return False

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete all documents for this tenant."""
        org_id = self.organization_id

        try:
            async with get_async_db_context() as db:
                stmt = text("""
                    DELETE FROM tenant_documents
                    WHERE organization_id = :org_id
                """)
                await db.execute(stmt, {"org_id": str(org_id)})
                await db.commit()

                logger.info(f"Deleted all documents for tenant {org_id}")
                return True

        except Exception as e:
            logger.error(f"Error deleting tenant collection: {e}")
            return False

    async def count_documents(
        self,
        filter_metadata: dict[str, Any] | None = None,
    ) -> int:
        """Count documents for this tenant."""
        org_id = self.organization_id

        try:
            async with get_async_db_context() as db:
                stmt = select(func.count(TenantDocument.id)).where(
                    TenantDocument.organization_id == org_id,
                    TenantDocument.active == True,  # noqa: E712
                )

                if filter_metadata:
                    if "document_type" in filter_metadata:
                        stmt = stmt.where(
                            TenantDocument.document_type == filter_metadata["document_type"]
                        )
                    if "category" in filter_metadata:
                        stmt = stmt.where(
                            TenantDocument.category == filter_metadata["category"]
                        )

                result = await db.execute(stmt)
                count = result.scalar()
                return count or 0

        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0

    async def get_index_stats(self) -> dict[str, Any]:
        """Get index statistics for this tenant."""
        org_id = self.organization_id

        try:
            async with get_async_db_context() as db:
                stats_query = text("""
                    SELECT
                        COUNT(*) as total_documents,
                        COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embedding,
                        COUNT(CASE WHEN search_vector IS NOT NULL THEN 1 END) as with_search_vector,
                        COUNT(DISTINCT document_type) as document_types,
                        COUNT(DISTINCT category) as categories
                    FROM tenant_documents
                    WHERE organization_id = :org_id
                      AND active = true
                """)

                result = await db.execute(stats_query, {"org_id": str(org_id)})
                row = result.fetchone()

                return {
                    "organization_id": str(org_id),
                    "total_documents": row.total_documents if row else 0,
                    "with_embedding": row.with_embedding if row else 0,
                    "with_search_vector": row.with_search_vector if row else 0,
                    "document_types": row.document_types if row else 0,
                    "categories": row.categories if row else 0,
                    "embedding_dimension": self._embedding_dimension,
                }

        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {"error": str(e)}
