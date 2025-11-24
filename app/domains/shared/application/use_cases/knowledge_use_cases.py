"""
Knowledge Use Cases

Use cases for knowledge base management following Clean Architecture.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.repositories.knowledge_repository import KnowledgeRepository
from app.integrations.vector_stores import KnowledgeEmbeddingService

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
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
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
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    async def execute(
        self,
        query: str,
        limit: int = 10,
        document_type: Optional[str] = None,
        use_vector_search: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base with hybrid approach.

        Args:
            query: Search query text
            limit: Maximum number of results
            document_type: Optional filter by document type
            use_vector_search: Whether to use vector similarity search

        Returns:
            List of knowledge documents with relevance scores

        Example:
            use_case = SearchKnowledgeUseCase(db)
            results = await use_case.execute(
                "How to configure payment gateway?",
                limit=5,
                document_type="tutorial"
            )
        """
        try:
            # Validate parameters
            if not query or len(query.strip()) < 3:
                logger.warning("Search query too short")
                return []

            if limit < 1 or limit > 100:
                limit = 10  # Default limit

            results = []

            if use_vector_search:
                # Vector similarity search (semantic)
                try:
                    vector_results = await self.embedding_service.search_knowledge(
                        query=query,
                        k=limit,
                        filter_type=document_type,
                    )
                    results.extend(vector_results)
                    logger.info(f"Vector search returned {len(vector_results)} results")
                except Exception as e:
                    logger.error(f"Vector search failed: {e}")
                    # Fallback to SQL search if vector fails

            # SQL search (keyword-based) as fallback or complement
            if not results:
                sql_results = await self.repository.search_by_keywords(
                    query=query,
                    limit=limit,
                    document_type=document_type,
                )
                results.extend(sql_results)
                logger.info(f"SQL search returned {len(sql_results)} results")

            # Remove duplicates and limit results
            seen_ids = set()
            unique_results = []
            for result in results:
                doc_id = result.get("id")
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_results.append(result)
                    if len(unique_results) >= limit:
                        break

            logger.info(f"Search completed: {len(unique_results)} unique results")
            return unique_results

        except Exception as e:
            logger.error(f"Error in SearchKnowledgeUseCase: {e}")
            return []
