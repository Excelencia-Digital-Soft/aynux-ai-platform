"""
Create Knowledge Use Case.

Creates new knowledge documents with automatic embedding generation.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domains.shared.application.use_cases.knowledge._common import knowledge_to_dict
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class CreateKnowledgeUseCase:
    """
    Use Case: Create Knowledge Document

    Creates a new knowledge document with automatic embedding generation.

    Responsibilities:
    - Validate input data (title, content, document_type required)
    - Create document in database
    - Generate vector embeddings (pgvector)
    - Handle errors and rollback on failure

    Follows SRP: Single responsibility for knowledge creation logic
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize create use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
            embedding_service: Embedding service for vector generation
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        knowledge_data: dict[str, Any],
        auto_embed: bool = True,
    ) -> dict[str, Any]:
        """
        Create a new knowledge document.

        Args:
            knowledge_data: Dictionary with document data
            auto_embed: Whether to automatically generate embeddings

        Returns:
            Created document as dictionary

        Raises:
            ValueError: If validation fails

        Example:
            use_case = CreateKnowledgeUseCase(db)
            result = await use_case.execute({
                "title": "Payment Gateway Setup",
                "content": "To configure the payment gateway...",
                "document_type": "tutorial",
            })
        """
        try:
            # Validate required fields
            if not knowledge_data.get("title"):
                raise ValueError("Title is required")
            if not knowledge_data.get("content"):
                raise ValueError("Content is required")
            if not knowledge_data.get("document_type"):
                raise ValueError("Document type is required")

            # Validate content length
            if len(knowledge_data["content"]) < 50:
                raise ValueError("Content must be at least 50 characters")

            # Create in database
            knowledge = await self.repository.create(knowledge_data)
            await self.db.commit()

            # Generate embeddings if requested
            if auto_embed:
                try:
                    await self.embedding_service.update_knowledge_embeddings(
                        knowledge_id=str(knowledge.id),
                    )
                    await self.db.refresh(knowledge)
                    logger.info(f"Generated embeddings for knowledge ID: {knowledge.id}")
                except Exception as e:
                    logger.error(f"Error generating embeddings: {e}")
                    # Don't fail the creation, just log the error

            result = knowledge_to_dict(knowledge)
            logger.info(f"Created knowledge document: {knowledge.id}")
            return result

        except ValueError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating knowledge: {e}")
            raise
