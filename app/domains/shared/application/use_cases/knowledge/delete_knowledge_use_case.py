"""
Delete Knowledge Use Case.

Deletes knowledge documents (soft or hard delete).
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class DeleteKnowledgeUseCase:
    """
    Use Case: Delete Knowledge Document

    Deletes a knowledge document (soft or hard delete).

    Responsibilities:
    - Delete document from database (soft/hard)
    - Delete embeddings from vector stores
    - Handle errors and rollback
    - Return success status

    Follows SRP: Single responsibility for document deletion
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize delete use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
            embedding_service: Embedding service for vector cleanup
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        knowledge_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete a knowledge document.

        Args:
            knowledge_id: UUID of the document to delete
            soft_delete: If True, set active=False. If False, hard delete.

        Returns:
            True if deleted successfully, False otherwise

        Example:
            use_case = DeleteKnowledgeUseCase(db)

            # Soft delete (set active=False)
            success = await use_case.execute(UUID("123..."), soft_delete=True)

            # Hard delete (remove from database)
            success = await use_case.execute(UUID("123..."), soft_delete=False)
        """
        try:
            if soft_delete:
                knowledge = await self.repository.soft_delete(knowledge_id)
                success = knowledge is not None
                if success:
                    logger.info(f"Soft deleted knowledge: {knowledge_id}")
            else:
                success = await self.repository.delete(knowledge_id)
                # Also delete embeddings for hard delete
                if success:
                    try:
                        await self.embedding_service.delete_knowledge_embeddings(
                            str(knowledge_id)
                        )
                        logger.info(f"Hard deleted knowledge and embeddings: {knowledge_id}")
                    except Exception as e:
                        logger.error(f"Error deleting embeddings: {e}")
                        # Don't fail the delete, just log

            if success:
                await self.db.commit()
            else:
                logger.warning(f"Knowledge not found for deletion: {knowledge_id}")

            return success

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting knowledge: {e}")
            raise
