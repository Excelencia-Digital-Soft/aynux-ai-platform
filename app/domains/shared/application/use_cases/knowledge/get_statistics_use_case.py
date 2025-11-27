"""
Get Knowledge Statistics Use Case.

Retrieves comprehensive statistics about the knowledge base.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge_repository import KnowledgeRepository

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
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    async def execute(self) -> dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            Dictionary with various statistics

        Example:
            use_case = GetKnowledgeStatisticsUseCase(db)
            stats = await use_case.execute()
            # Returns:
            # {
            #     "database": {
            #         "total_active": 50,
            #         "total_inactive": 5,
            #         "missing_embeddings": 2,
            #         "embedding_coverage": 96.0
            #     },
            #     "embedding_model": "nomic-embed-text"
            # }
        """
        try:
            # Get counts from repository
            total_active = await self.repository.count_documents(active_only=True)
            total_all = await self.repository.count_documents(active_only=False)
            total_inactive = total_all - total_active
            docs_without_embeddings = len(
                await self.repository.get_documents_without_embeddings()
            )

            # Calculate embedding coverage
            embedding_coverage = (
                ((total_active - docs_without_embeddings) / total_active * 100)
                if total_active > 0
                else 0.0
            )

            stats = {
                "database": {
                    "total_active": total_active,
                    "total_inactive": total_inactive,
                    "missing_embeddings": docs_without_embeddings,
                    "embedding_coverage": round(embedding_coverage, 2),
                },
                "embedding_model": self.embedding_service.embedding_model,
            }

            logger.info(f"Retrieved stats: {total_active} active documents")
            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise
