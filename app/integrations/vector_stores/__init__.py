"""
Vector Store integrations

Integrations para diferentes backends de vector stores:
- pgvector: PostgreSQL with pgvector extension (ÚNICO vector store)
- Knowledge embeddings: Knowledge base vector search
- Metrics: pgvector performance monitoring
"""

from app.integrations.vector_stores.knowledge_embedding_service import (
    KnowledgeEmbeddingService,
)
from app.integrations.vector_stores.pgvector import PgVectorStore, PgVectorIntegration
from app.integrations.vector_stores.pgvector_metrics_service import (
    PgVectorMetricsService,
)


def create_pgvector_store(
    collection_name: str = "products",
    embedding_dimension: int = 768,
) -> PgVectorStore:
    """
    Factory function to create a PgVectorStore instance.

    Args:
        collection_name: Name of the collection/table
        embedding_dimension: Dimension of embeddings (default 768 for nomic-embed-text)

    Returns:
        Configured PgVectorStore instance
    """
    return PgVectorStore(
        collection_name=collection_name,
        embedding_dimension=embedding_dimension,
    )


__all__ = [
    "KnowledgeEmbeddingService",
    "PgVectorMetricsService",
    "PgVectorStore",
    "PgVectorIntegration",
    "create_pgvector_store",
]
