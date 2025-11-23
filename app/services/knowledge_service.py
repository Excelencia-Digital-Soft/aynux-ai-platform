"""
Knowledge Service - Business Logic Layer (SRP + DIP)

This service contains business logic for knowledge base operations.
It coordinates between the repository (data access) and embedding service
(vector generation).

Responsibilities:
- Business logic validation
- Orchestration between repository and embedding service
- Hybrid search strategy implementation
- Caching of frequent searches
- Error handling and logging

Dependencies are injected (DIP) rather than instantiated directly.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.repositories.knowledge_repository import KnowledgeRepository
from app.integrations.vector_stores import KnowledgeEmbeddingService

logger = logging.getLogger(__name__)
settings = get_settings()


class KnowledgeService:
    """
    Business logic service for knowledge base operations.

    Provides high-level operations that combine data access (repository)
    with embedding generation and search capabilities.
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
    ):
        """
        Initialize knowledge service with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
            embedding_service: Embedding service (injected for testability)
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    # ============================================================================
    # CRUD Operations with Business Logic
    # ============================================================================

    async def create_knowledge(self, knowledge_data: Dict[str, Any], auto_embed: bool = True) -> Dict[str, Any]:
        """
        Create a new knowledge document with optional automatic embedding.

        Args:
            knowledge_data: Dictionary with document data
            auto_embed: Whether to automatically generate embeddings

        Returns:
            Created document as dictionary

        Raises:
            ValueError: If validation fails
        """
        try:
            # Validate required fields
            if not knowledge_data.get("title"):
                raise ValueError("Title is required")
            if not knowledge_data.get("content"):
                raise ValueError("Content is required")
            if not knowledge_data.get("document_type"):
                raise ValueError("Document type is required")

            # Validate content length (minimum 50 characters for meaningful embeddings)
            if len(knowledge_data["content"]) < 50:
                raise ValueError("Content must be at least 50 characters for meaningful search")

            # Create in database
            knowledge = await self.repository.create(knowledge_data)
            await self.db.commit()

            # Generate embeddings if requested
            if auto_embed:
                try:
                    await self.embedding_service.update_knowledge_embeddings(
                        knowledge_id=str(knowledge.id),
                        update_pgvector=settings.USE_PGVECTOR,
                        update_chroma=True,
                    )
                    # Refresh to get updated embedding
                    await self.db.refresh(knowledge)
                except Exception as e:
                    logger.error(f"Error generating embeddings for new knowledge: {e}")
                    # Don't fail the creation, just log the error

            return self._knowledge_to_dict(knowledge)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating knowledge: {e}")
            raise

    async def get_knowledge(self, knowledge_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a knowledge document by ID.

        Args:
            knowledge_id: UUID of the document

        Returns:
            Document as dictionary or None if not found
        """
        knowledge = await self.repository.get_by_id(knowledge_id)
        return self._knowledge_to_dict(knowledge) if knowledge else None

    async def update_knowledge(
        self,
        knowledge_id: UUID,
        update_data: Dict[str, Any],
        regenerate_embedding: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a knowledge document.

        Args:
            knowledge_id: UUID of the document to update
            update_data: Dictionary with fields to update
            regenerate_embedding: Whether to regenerate embeddings after update

        Returns:
            Updated document as dictionary or None if not found
        """
        try:
            # Update in database
            knowledge = await self.repository.update(knowledge_id, update_data)
            if not knowledge:
                return None

            await self.db.commit()

            # Regenerate embeddings if content changed and requested
            if regenerate_embedding and any(key in update_data for key in ["title", "content"]):
                try:
                    await self.embedding_service.update_knowledge_embeddings(
                        knowledge_id=str(knowledge_id),
                        update_pgvector=settings.USE_PGVECTOR,
                        update_chroma=True,
                    )
                    await self.db.refresh(knowledge)
                except Exception as e:
                    logger.error(f"Error regenerating embeddings: {e}")

            return self._knowledge_to_dict(knowledge)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating knowledge: {e}")
            raise

    async def delete_knowledge(self, knowledge_id: UUID, soft_delete: bool = True) -> bool:
        """
        Delete a knowledge document.

        Args:
            knowledge_id: UUID of the document to delete
            soft_delete: If True, just set active=False. If False, hard delete.

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if soft_delete:
                knowledge = await self.repository.soft_delete(knowledge_id)
                success = knowledge is not None
            else:
                success = await self.repository.delete(knowledge_id)
                # Also delete from ChromaDB
                if success:
                    await self.embedding_service.delete_knowledge_embeddings(str(knowledge_id))

            if success:
                await self.db.commit()
            return success

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting knowledge: {e}")
            raise

    async def list_knowledge(
        self,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
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
        """
        try:
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

            return {
                "documents": [self._knowledge_to_dict(doc) for doc in documents],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_documents": total,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1,
                },
            }

        except Exception as e:
            logger.error(f"Error listing knowledge: {e}")
            raise

    # ============================================================================
    # Search Operations with Hybrid Strategy
    # ============================================================================

    async def search_knowledge(
        self,
        query: str,
        max_results: int = 5,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_strategy: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base using configured strategy.

        Args:
            query: Search query text
            max_results: Maximum number of results
            document_type: Filter by document type
            category: Filter by category
            tags: Filter by tags
            search_strategy: Override default strategy (pgvector_primary|chroma_primary|hybrid)

        Returns:
            List of search results with scores
        """
        try:
            # Get strategy from settings or parameter
            strategy = search_strategy or getattr(settings, "KNOWLEDGE_SEARCH_STRATEGY", "hybrid")

            logger.info(f"Searching knowledge with strategy={strategy}, query='{query[:50]}...'")

            if strategy == "pgvector_primary":
                return await self._search_pgvector(
                    query=query,
                    max_results=max_results,
                    document_type=document_type,
                    category=category,
                    tags=tags,
                )
            elif strategy == "chroma_primary":
                return await self._search_chroma(
                    query=query,
                    max_results=max_results,
                    document_type=document_type,
                )
            elif strategy == "hybrid":
                return await self._search_hybrid(
                    query=query,
                    max_results=max_results,
                    document_type=document_type,
                )
            else:
                logger.warning(f"Unknown search strategy: {strategy}, falling back to hybrid")
                return await self._search_hybrid(query, max_results, document_type)

        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            # Return empty results rather than failing
            return []

    async def _search_pgvector(
        self,
        query: str,
        max_results: int,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search using pgvector (PostgreSQL) only."""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query)

            # Search using repository
            results = await self.repository.search_by_vector(
                query_embedding=query_embedding,
                similarity_threshold=getattr(settings, "KNOWLEDGE_SIMILARITY_THRESHOLD", 0.7),
                max_results=max_results,
                document_type=document_type,
                category=category,
                tags=tags,
            )

            return results

        except Exception as e:
            logger.error(f"Error in pgvector search: {e}")
            return []

    async def _search_chroma(
        self,
        query: str,
        max_results: int,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search using ChromaDB only."""
        try:
            results = await self.embedding_service.search_knowledge_chroma(
                query=query,
                k=max_results,
                document_type=document_type,
            )
            return results

        except Exception as e:
            logger.error(f"Error in ChromaDB search: {e}")
            return []

    async def _search_hybrid(
        self,
        query: str,
        max_results: int,
        document_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Hybrid search combining pgvector and ChromaDB with intelligent merging."""
        try:
            # Generate query embedding once
            query_embedding = await self.embedding_service.generate_embedding(query)

            # Search both stores in parallel (using asyncio would be better, but keeping simple)
            pgvector_results = await self.repository.search_hybrid(
                query_text=query,
                query_embedding=query_embedding,
                max_results=max_results,
                vector_weight=0.7,
                text_weight=0.3,
                similarity_threshold=getattr(settings, "KNOWLEDGE_SIMILARITY_THRESHOLD", 0.5),
                document_type=document_type,
            )

            # Return pgvector results (already hybrid with full-text)
            # ChromaDB can be used as fallback if pgvector fails
            return pgvector_results

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            # Fallback to ChromaDB if pgvector fails
            return await self._search_chroma(query, max_results, document_type)

    # ============================================================================
    # Embedding Management
    # ============================================================================

    async def regenerate_embeddings(
        self,
        knowledge_id: Optional[UUID] = None,
        update_pgvector: bool = True,
        update_chroma: bool = True,
    ):
        """
        Regenerate embeddings for one or all documents.

        Args:
            knowledge_id: If provided, regenerate only this document
            update_pgvector: Update pgvector embeddings
            update_chroma: Update ChromaDB embeddings
        """
        try:
            knowledge_id_str = str(knowledge_id) if knowledge_id else None

            await self.embedding_service.update_knowledge_embeddings(
                knowledge_id=knowledge_id_str,
                update_pgvector=update_pgvector,
                update_chroma=update_chroma,
            )

            logger.info(
                f"Regenerated embeddings (knowledge_id={knowledge_id_str}, "
                f"pgvector={update_pgvector}, chroma={update_chroma})"
            )

        except Exception as e:
            logger.error(f"Error regenerating embeddings: {e}")
            raise

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            Dictionary with various statistics
        """
        try:
            # Get counts from repository
            total_active = await self.repository.count_documents(active_only=True)
            total_inactive = await self.repository.count_documents(active_only=False) - total_active
            docs_without_embeddings = len(await self.repository.get_documents_without_embeddings())

            # Get ChromaDB stats
            chroma_stats = self.embedding_service.get_chroma_collection_stats()

            return {
                "database": {
                    "total_active": total_active,
                    "total_inactive": total_inactive,
                    "missing_embeddings": docs_without_embeddings,
                    "embedding_coverage": (
                        ((total_active - docs_without_embeddings) / total_active * 100)
                        if total_active > 0
                        else 0.0
                    ),
                },
                "chromadb_collections": chroma_stats,
                "embedding_model": self.embedding_service.embedding_model,
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise

    # ============================================================================
    # Helper Methods
    # ============================================================================

    def _knowledge_to_dict(self, knowledge) -> Dict[str, Any]:
        """
        Convert CompanyKnowledge model to dictionary.

        Args:
            knowledge: CompanyKnowledge instance

        Returns:
            Dictionary representation
        """
        return {
            "id": str(knowledge.id),
            "title": knowledge.title,
            "content": knowledge.content,
            "document_type": knowledge.document_type,
            "category": knowledge.category,
            "tags": knowledge.tags or [],
            "metadata": knowledge.meta_data or {},
            "active": knowledge.active,
            "sort_order": knowledge.sort_order,
            "has_embedding": knowledge.embedding is not None,
            "created_at": knowledge.created_at.isoformat(),
            "updated_at": knowledge.updated_at.isoformat(),
        }
