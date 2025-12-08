"""
Regenerate Knowledge Embeddings Use Case.

Regenerates vector embeddings for knowledge documents.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class RegenerateKnowledgeEmbeddingsUseCase:
    """
    Use Case: Regenerate embeddings for knowledge documents.

    This Use Case handles regenerating vector embeddings for one or all
    knowledge documents. Used when changing embedding models, fixing
    corrupted embeddings, or re-syncing after manual content edits.

    Follows Clean Architecture:
    - Single Responsibility: Handles only embedding regeneration logic
    - Dependency Injection: Repository and EmbeddingService injected
    - Framework Independent: No framework-specific code
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize the use case with dependencies.

        Args:
            db: Database session
            repository: Knowledge repository (optional, created if not provided)
            embedding_service: Embedding service (optional, created if not provided)
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        knowledge_id: UUID | None = None,
    ) -> int:
        """
        Regenerate embeddings for one or all knowledge documents.

        Args:
            knowledge_id: UUID of document to regenerate (None = all documents)

        Returns:
            Number of documents processed

        Raises:
            ValueError: If document not found (when knowledge_id provided)
            Exception: For other errors
        """
        try:
            if knowledge_id is not None:
                # Regenerate single document
                logger.info(f"Regenerating embeddings for: {knowledge_id}")

                # Verify document exists
                knowledge = await self.repository.get_by_id(knowledge_id)
                if not knowledge:
                    raise ValueError(f"Knowledge document {knowledge_id} not found")

                # Regenerate embeddings
                await self.embedding_service.update_knowledge_embeddings(
                    knowledge_id=str(knowledge_id),
                )

                logger.info(f"Successfully regenerated embeddings: {knowledge_id}")
                return 1

            else:
                # Regenerate all documents
                logger.info("Regenerating embeddings for ALL knowledge documents")

                # Use the service's rebuild method for efficiency
                await self.embedding_service.rebuild_all_embeddings()

                # Get count of processed documents
                all_knowledge = await self.repository.get_all()
                processed_count = len(all_knowledge)

                logger.info(f"Regenerated embeddings for {processed_count} documents")
                return processed_count

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error regenerating embeddings: {e}")
            raise
