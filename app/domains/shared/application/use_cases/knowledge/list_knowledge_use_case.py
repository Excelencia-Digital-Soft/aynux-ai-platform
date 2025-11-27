"""
List Knowledge Use Case.

Lists knowledge documents with filtering and pagination.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.application.use_cases.knowledge._common import knowledge_to_dict
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)


class ListKnowledgeUseCase:
    """
    Use Case: List Knowledge Documents

    Lists knowledge documents with filtering and pagination.

    Responsibilities:
    - Filter by document_type, category, tags
    - Paginate results
    - Return formatted results with pagination metadata

    Follows SRP: Single responsibility for document listing
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
    ):
        """
        Initialize list use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)

    async def execute(
        self,
        document_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        List knowledge documents with pagination.

        Args:
            document_type: Filter by document type
            category: Filter by category
            tags: Filter by tags
            active_only: Only return active documents
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Dictionary with paginated results and metadata

        Example:
            use_case = ListKnowledgeUseCase(db)
            result = await use_case.execute(
                document_type="tutorial",
                page=1,
                page_size=10
            )
            # Returns: {"documents": [...], "pagination": {...}}
        """
        try:
            # Validate pagination parameters
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 20

            # Calculate skip
            skip = (page - 1) * page_size

            # Get documents
            documents = await self.repository.get_all(
                document_type=document_type,
                category=category,
                tags=tags,
                active_only=active_only,
                skip=skip,
                limit=page_size,
            )

            # Get total count
            total = await self.repository.count_documents(
                document_type=document_type,
                active_only=active_only,
            )

            # Calculate pagination metadata
            total_pages = (total + page_size - 1) // page_size  # Ceiling division

            result = {
                "documents": [knowledge_to_dict(doc) for doc in documents],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_documents": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }

            logger.info(
                f"Listed {len(documents)} documents (page {page}/{total_pages})"
            )
            return result

        except Exception as e:
            logger.error(f"Error listing knowledge: {e}")
            raise
