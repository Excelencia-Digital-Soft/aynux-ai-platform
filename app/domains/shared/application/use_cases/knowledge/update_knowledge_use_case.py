"""
Update Knowledge Use Case.

Updates existing knowledge documents and optionally regenerates embeddings.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domains.shared.application.use_cases.knowledge._common import knowledge_to_dict
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class UpdateKnowledgeUseCase:
    """
    Use Case: Update Knowledge Document

    Updates an existing knowledge document and optionally regenerates embeddings.

    Responsibilities:
    - Update document fields
    - Regenerate embeddings if content changed
    - Handle validation and errors
    - Commit or rollback transaction

    Follows SRP: Single responsibility for document update logic
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize update use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
            embedding_service: Embedding service for vector regeneration
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        knowledge_id: UUID,
        update_data: dict[str, Any],
        regenerate_embedding: bool = True,
    ) -> dict[str, Any] | None:
        """
        Update a knowledge document.

        Args:
            knowledge_id: UUID of the document to update
            update_data: Dictionary with fields to update
            regenerate_embedding: Whether to regenerate embeddings after update

        Returns:
            Updated document as dictionary or None if not found

        Example:
            use_case = UpdateKnowledgeUseCase(db)
            updated = await use_case.execute(
                UUID("123..."),
                {"title": "New Title", "content": "Updated content..."},
            )
        """
        try:
            # Update in database
            knowledge = await self.repository.update(knowledge_id, update_data)
            if not knowledge:
                logger.warning(f"Knowledge document not found: {knowledge_id}")
                return None

            await self.db.commit()

            # Regenerate embeddings if content changed and requested
            if regenerate_embedding and any(
                key in update_data for key in ["title", "content"]
            ):
                try:
                    await self.embedding_service.update_knowledge_embeddings(
                        knowledge_id=str(knowledge_id),
                    )
                    await self.db.refresh(knowledge)
                    logger.info(f"Regenerated embeddings for: {knowledge_id}")
                except Exception as e:
                    logger.error(f"Error regenerating embeddings: {e}")
                    # Don't fail the update, just log the error

            result = knowledge_to_dict(knowledge)
            logger.info(f"Updated knowledge document: {knowledge_id}")
            return result

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating knowledge: {e}")
            raise
