"""
Vector Store integrations

Integrations para diferentes backends de vector stores:
- pgvector: PostgreSQL with pgvector extension
- Embedding services: Update and management of embeddings
- Vector ingestion: Batch ingestion to vector stores
- Knowledge embeddings: Knowledge base vector search
- Metrics: pgvector performance monitoring
"""

from app.integrations.vector_stores.embedding_update_service import (
    EmbeddingUpdateService,
)
from app.integrations.vector_stores.knowledge_embedding_service import (
    KnowledgeEmbeddingService,
)
from app.integrations.vector_stores.pgvector_metrics_service import (
    PgVectorMetricsService,
)
from app.integrations.vector_stores.vector_service import VectorService
from app.integrations.vector_stores.vector_store_ingestion_service import (
    create_vector_ingestion_service,
)

__all__ = [
    "EmbeddingUpdateService",
    "VectorService",
    "create_vector_ingestion_service",
    "KnowledgeEmbeddingService",
    "PgVectorMetricsService",
]
