"""
Get Knowledge Use Case.

Retrieves a single knowledge document by its UUID.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.application.use_cases.knowledge._common import knowledge_to_dict
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class GetKnowledgeUseCase:
    """
    Use Case: Get Knowledge Document by ID

    Retrieves a single knowledge document by its UUID.

    Responsibilities:
    - Fetch document by ID
    - Return formatted result or None
    - Handle not found gracefully

    Follows SRP: Single responsibility for document retrieval
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
    ):
        """
        Initialize get use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)

    async def execute(self, knowledge_id: UUID) -> dict[str, Any] | None:
        """
        Get a knowledge document by ID.

        Args:
            knowledge_id: UUID of the document

        Returns:
            Document as dictionary or None if not found

        Example:
            use_case = GetKnowledgeUseCase(db)
            doc = await use_case.execute(UUID("123e4567-e89b-12d3-a456-426614174000"))
        """
        try:
            knowledge = await self.repository.get_by_id(knowledge_id)
            if not knowledge:
                logger.warning(f"Knowledge document not found: {knowledge_id}")
                return None

            return knowledge_to_dict(knowledge)

        except Exception as e:
            logger.error(f"Error getting knowledge: {e}")
            raise
