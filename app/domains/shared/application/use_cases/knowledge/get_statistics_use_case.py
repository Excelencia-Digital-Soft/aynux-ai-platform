"""
Get Knowledge Statistics Use Case.

Retrieves comprehensive statistics about the knowledge base.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class GetKnowledgeStatisticsUseCase:
    """
    Use Case: Get Knowledge Base Statistics

    Retrieves comprehensive statistics about the knowledge base.

    Responsibilities:
    - Count total documents (active/inactive)
    - Count documents without embeddings
    - Calculate embedding coverage percentage
    - Get pgvector embedding stats
    - Return formatted statistics

    Follows SRP: Single responsibility for statistics collection
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize statistics use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
            embedding_service: Embedding service for collection stats
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(self) -> dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            Dictionary with flat structure for frontend compatibility:
            {
                "total_documents": 50,
                "total_active": 45,
                "total_inactive": 5,
                "documents_by_type": {"faq": 20, "software_catalog": 15},
                "documents_with_embedding": 43,
                "documents_without_embedding": 2,
                "embedding_model": "nomic-embed-text"
            }
        """
        try:
            # Get counts from repository
            total_active = await self.repository.count_documents(active_only=True)
            total_all = await self.repository.count_documents(active_only=False)
            total_inactive = total_all - total_active

            docs_without_embeddings = len(
                await self.repository.get_documents_without_embeddings()
            )
            docs_with_embeddings = total_active - docs_without_embeddings

            # Get documents grouped by type
            documents_by_type = await self.repository.count_by_document_type()

            stats = {
                "total_documents": total_all,
                "total_active": total_active,
                "total_inactive": total_inactive,
                "documents_by_type": documents_by_type,
                "documents_with_embedding": docs_with_embeddings,
                "documents_without_embedding": docs_without_embeddings,
                "embedding_model": self.embedding_service.embedding_model,
            }

            logger.info(f"Retrieved stats: {total_all} total documents")
            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise
