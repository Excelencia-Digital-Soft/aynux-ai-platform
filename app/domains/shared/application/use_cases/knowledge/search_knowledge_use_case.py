"""
Search Knowledge Use Case.

Handles semantic and hybrid search across the knowledge base.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class SearchKnowledgeUseCase:
    """
    Use Case: Search Knowledge Base

    Handles semantic and hybrid search across the knowledge base.
    Combines vector similarity search with traditional filtering.

    Responsibilities:
    - Validate search parameters
    - Execute hybrid search (vector + SQL)
    - Rank and filter results
    - Return formatted results
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: KnowledgeRepository | None = None,
        embedding_service: KnowledgeEmbeddingService | None = None,
    ):
        """
        Initialize search use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
            embedding_service: Embedding service for vector search
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService()

    async def execute(
        self,
        query: str,
        max_results: int = 10,
        document_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        search_strategy: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge base with configurable search strategy.

        Args:
            query: Search query text
            max_results: Maximum number of results
            document_type: Optional filter by document type
            category: Optional filter by category
            tags: Optional filter by tags
            search_strategy: Search strategy - "pgvector" (default, semantic search)

        Returns:
            List of knowledge documents with relevance scores

        Example:
            use_case = SearchKnowledgeUseCase(db)
            results = await use_case.execute(
                "How to configure payment gateway?",
                max_results=5,
                document_type="tutorial",
            )
        """
        try:
            # Validate parameters
            if not query or len(query.strip()) < 3:
                logger.warning("Search query too short")
                return []

            if max_results < 1 or max_results > 100:
                max_results = 10  # Default limit

            results = []

            # Execute pgvector semantic search (primary strategy)
            try:
                vector_results = await self.embedding_service.search_knowledge(
                    query=query,
                    k=max_results,
                    document_type=document_type,
                )
                results.extend(vector_results)
                logger.info(f"pgvector search returned {len(vector_results)} results")
            except Exception as e:
                logger.error(f"pgvector search failed: {e}")
                # Continue to try SQL fallback

            # Fallback to SQL search if no results from vector search
            if not results:
                try:
                    sql_results = await self.repository.search_by_text(
                        query_text=query,
                        max_results=max_results,
                        document_type=document_type,
                    )
                    results.extend(sql_results)
                    logger.info(f"Fallback SQL search returned {len(sql_results)} results")
                except Exception as e:
                    logger.error(f"Fallback search failed: {e}")

            # Remove duplicates and limit results
            seen_ids: set[str] = set()
            unique_results: list[dict[str, Any]] = []
            for result in results:
                doc_id = result.get("id")
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_results.append(result)
                    if len(unique_results) >= max_results:
                        break

            logger.info(f"Search completed: {len(unique_results)} unique results")
            return unique_results

        except Exception as e:
            logger.error(f"Error in SearchKnowledgeUseCase: {e}")
            return []
