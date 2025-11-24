"""
Knowledge Use Cases

Use cases for knowledge base management following Clean Architecture.

Available Use Cases:
- SearchKnowledgeUseCase: Search knowledge base with hybrid approach
- CreateKnowledgeUseCase: Create new knowledge documents
- GetKnowledgeUseCase: Get document by ID
- UpdateKnowledgeUseCase: Update existing documents
- DeleteKnowledgeUseCase: Delete documents (soft/hard)
- ListKnowledgeUseCase: List documents with pagination
- GetKnowledgeStatisticsUseCase: Get knowledge base statistics
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
        max_results: int = 10,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search_strategy: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base with configurable search strategy.

        Args:
            query: Search query text
            max_results: Maximum number of results
            document_type: Optional filter by document type
            category: Optional filter by category
            tags: Optional filter by tags
            search_strategy: Search strategy - "pgvector_primary", "chroma_primary", or "hybrid" (default)

        Returns:
            List of knowledge documents with relevance scores

        Example:
            use_case = SearchKnowledgeUseCase(db)
            results = await use_case.execute(
                "How to configure payment gateway?",
                max_results=5,
                document_type="tutorial",
                search_strategy="hybrid"
            )
        """
        try:
            # Validate parameters
            if not query or len(query.strip()) < 3:
                logger.warning("Search query too short")
                return []

            if max_results < 1 or max_results > 100:
                max_results = 10  # Default limit

            # Determine search strategy (default to hybrid)
            strategy = search_strategy or settings.KNOWLEDGE_SEARCH_STRATEGY or "hybrid"

            results = []

            # Execute search based on strategy
            if strategy in ["hybrid", "chroma_primary"]:
                # Vector similarity search (semantic) using ChromaDB
                try:
                    vector_results = await self.embedding_service.search_knowledge(
                        query=query,
                        k=max_results,
                        filter_type=document_type,
                    )
                    results.extend(vector_results)
                    logger.info(f"ChromaDB search returned {len(vector_results)} results")
                except Exception as e:
                    logger.error(f"ChromaDB search failed: {e}")
                    # Continue to try other strategies

            if strategy in ["hybrid", "pgvector_primary"]:
                # SQL search with pgvector (if not enough results from ChromaDB)
                if strategy == "hybrid" and len(results) >= max_results:
                    # Already have enough results from ChromaDB
                    pass
                else:
                    try:
                        sql_results = await self.repository.search_by_keywords(
                            query=query,
                            limit=max_results,
                            document_type=document_type,
                        )
                        results.extend(sql_results)
                        logger.info(f"SQL/pgvector search returned {len(sql_results)} results")
                    except Exception as e:
                        logger.error(f"SQL search failed: {e}")

            # Fallback to SQL search if no results from vector search
            if not results:
                try:
                    sql_results = await self.repository.search_by_keywords(
                        query=query,
                        limit=max_results,
                        document_type=document_type,
                    )
                    results.extend(sql_results)
                    logger.info(f"Fallback SQL search returned {len(sql_results)} results")
                except Exception as e:
                    logger.error(f"Fallback search failed: {e}")

            # Remove duplicates and limit results
            seen_ids = set()
            unique_results = []
            for result in results:
                doc_id = result.get("id")
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    unique_results.append(result)
                    if len(unique_results) >= max_results:
                        break

            logger.info(f"Search completed: {len(unique_results)} unique results (strategy: {strategy})")
            return unique_results

        except Exception as e:
            logger.error(f"Error in SearchKnowledgeUseCase: {e}")
            return []


class CreateKnowledgeUseCase:
    """
    Use Case: Create Knowledge Document

    Creates a new knowledge document with automatic embedding generation.

    Responsibilities:
    - Validate input data (title, content, document_type required)
    - Create document in database
    - Generate vector embeddings (pgvector + ChromaDB)
    - Handle errors and rollback on failure

    Follows SRP: Single responsibility for knowledge creation logic
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
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
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    async def execute(self, knowledge_data: Dict[str, Any], auto_embed: bool = True) -> Dict[str, Any]:
        """
        Create a new knowledge document.

        Args:
            knowledge_data: Dictionary with document data (title, content, document_type, etc.)
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
                "category": "setup",
                "tags": ["payment", "integration"]
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
                    logger.info(f"Generated embeddings for knowledge ID: {knowledge.id}")
                except Exception as e:
                    logger.error(f"Error generating embeddings for new knowledge: {e}")
                    # Don't fail the creation, just log the error

            result = self._knowledge_to_dict(knowledge)
            logger.info(f"Created knowledge document: {knowledge.id}")
            return result

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating knowledge: {e}")
            raise

    def _knowledge_to_dict(self, knowledge) -> Dict[str, Any]:
        """Convert CompanyKnowledge model to dictionary."""
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

    def __init__(self, db: AsyncSession, repository: Optional[KnowledgeRepository] = None):
        """
        Initialize get use case with dependencies.

        Args:
            db: Async database session
            repository: Knowledge repository (injected for testability)
        """
        self.db = db
        self.repository = repository or KnowledgeRepository(db)

    async def execute(self, knowledge_id: UUID) -> Optional[Dict[str, Any]]:
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

            return self._knowledge_to_dict(knowledge)

        except Exception as e:
            logger.error(f"Error getting knowledge: {e}")
            raise

    def _knowledge_to_dict(self, knowledge) -> Dict[str, Any]:
        """Convert CompanyKnowledge model to dictionary."""
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
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
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
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    async def execute(
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

        Example:
            use_case = UpdateKnowledgeUseCase(db)
            updated = await use_case.execute(
                UUID("123..."),
                {"title": "New Title", "content": "Updated content..."},
                regenerate_embedding=True
            )
        """
        try:
            # Update in database
            knowledge = await self.repository.update(knowledge_id, update_data)
            if not knowledge:
                logger.warning(f"Knowledge document not found for update: {knowledge_id}")
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
                    logger.info(f"Regenerated embeddings for knowledge ID: {knowledge_id}")
                except Exception as e:
                    logger.error(f"Error regenerating embeddings: {e}")
                    # Don't fail the update, just log the error

            result = self._knowledge_to_dict(knowledge)
            logger.info(f"Updated knowledge document: {knowledge_id}")
            return result

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating knowledge: {e}")
            raise

    def _knowledge_to_dict(self, knowledge) -> Dict[str, Any]:
        """Convert CompanyKnowledge model to dictionary."""
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
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
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
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    async def execute(self, knowledge_id: UUID, soft_delete: bool = True) -> bool:
        """
        Delete a knowledge document.

        Args:
            knowledge_id: UUID of the document to delete
            soft_delete: If True, just set active=False. If False, hard delete.

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
                    logger.info(f"Soft deleted knowledge document: {knowledge_id}")
            else:
                success = await self.repository.delete(knowledge_id)
                # Also delete from ChromaDB for hard delete
                if success:
                    try:
                        await self.embedding_service.delete_knowledge_embeddings(str(knowledge_id))
                        logger.info(f"Hard deleted knowledge document and embeddings: {knowledge_id}")
                    except Exception as e:
                        logger.error(f"Error deleting embeddings: {e}")
                        # Don't fail the delete, just log

            if success:
                await self.db.commit()
            else:
                logger.warning(f"Knowledge document not found for deletion: {knowledge_id}")

            return success

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting knowledge: {e}")
            raise


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

    def __init__(self, db: AsyncSession, repository: Optional[KnowledgeRepository] = None):
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

            logger.info(f"Listed {len(documents)} knowledge documents " f"(page {page}/{total_pages}, total: {total})")
            return result

        except Exception as e:
            logger.error(f"Error listing knowledge: {e}")
            raise

    def _knowledge_to_dict(self, knowledge) -> Dict[str, Any]:
        """Convert CompanyKnowledge model to dictionary."""
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


class GetKnowledgeStatisticsUseCase:
    """
    Use Case: Get Knowledge Base Statistics

    Retrieves comprehensive statistics about the knowledge base.

    Responsibilities:
    - Count total documents (active/inactive)
    - Count documents without embeddings
    - Calculate embedding coverage percentage
    - Get ChromaDB collection stats
    - Return formatted statistics

    Follows SRP: Single responsibility for statistics collection
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
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

    async def execute(self) -> Dict[str, Any]:
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
            #     "chromadb_collections": {...},
            #     "embedding_model": "nomic-embed-text"
            # }
        """
        try:
            # Get counts from repository
            total_active = await self.repository.count_documents(active_only=True)
            total_inactive = await self.repository.count_documents(active_only=False) - total_active
            docs_without_embeddings = len(await self.repository.get_documents_without_embeddings())

            # Get ChromaDB stats
            chroma_stats = self.embedding_service.get_chroma_collection_stats()

            # Calculate embedding coverage
            embedding_coverage = (
                ((total_active - docs_without_embeddings) / total_active * 100) if total_active > 0 else 0.0
            )

            stats = {
                "database": {
                    "total_active": total_active,
                    "total_inactive": total_inactive,
                    "missing_embeddings": docs_without_embeddings,
                    "embedding_coverage": round(embedding_coverage, 2),
                },
                "chromadb_collections": chroma_stats,
                "embedding_model": self.embedding_service.embedding_model,
            }

            logger.info(f"Retrieved knowledge base statistics: {total_active} active documents")
            return stats

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise


class RegenerateKnowledgeEmbeddingsUseCase:
    """
    Use Case: Regenerate embeddings for knowledge documents.

    This Use Case handles regenerating vector embeddings for one or all knowledge documents.
    Used when changing embedding models, fixing corrupted embeddings, or re-syncing after
    manual content edits.

    Follows Clean Architecture:
    - Single Responsibility: Handles only embedding regeneration logic
    - Dependency Injection: Repository and EmbeddingService injected
    - Framework Independent: No framework-specific code
    """

    def __init__(
        self,
        db: AsyncSession,
        repository: Optional[KnowledgeRepository] = None,
        embedding_service: Optional[KnowledgeEmbeddingService] = None,
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
        self.embedding_service = embedding_service or KnowledgeEmbeddingService(
            embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
            ollama_base_url=settings.OLLAMA_API_URL,
        )

    async def execute(
        self,
        knowledge_id: Optional[UUID] = None,
        update_pgvector: bool = True,
        update_chroma: bool = True,
    ) -> int:
        """
        Regenerate embeddings for one or all knowledge documents.

        Args:
            knowledge_id: UUID of document to regenerate (None = all documents)
            update_pgvector: Whether to update pgvector embeddings
            update_chroma: Whether to update ChromaDB embeddings

        Returns:
            Number of documents processed

        Raises:
            ValueError: If document not found (when knowledge_id provided)
            Exception: For other errors
        """
        try:
            if knowledge_id is not None:
                # Regenerate single document
                logger.info(f"Regenerating embeddings for document: {knowledge_id}")

                # Verify document exists
                knowledge = await self.repository.get_by_id(knowledge_id)
                if not knowledge:
                    raise ValueError(f"Knowledge document {knowledge_id} not found")

                # Regenerate embeddings
                await self.embedding_service.update_knowledge_embeddings(
                    knowledge_id=knowledge_id,
                    title=knowledge.title,
                    content=knowledge.content,
                    metadata={
                        "document_type": knowledge.document_type,
                        "category": knowledge.category or "",
                        "tags": knowledge.tags or [],
                    },
                    update_pgvector=update_pgvector,
                    update_chroma=update_chroma,
                )

                logger.info(f"Successfully regenerated embeddings for document: {knowledge_id}")
                return 1

            else:
                # Regenerate all documents
                logger.info("Regenerating embeddings for ALL knowledge documents")

                # Get all active documents
                all_knowledge = await self.repository.get_all()
                processed_count = 0

                for knowledge in all_knowledge:
                    try:
                        await self.embedding_service.update_knowledge_embeddings(
                            knowledge_id=knowledge.id,
                            title=knowledge.title,
                            content=knowledge.content,
                            metadata={
                                "document_type": knowledge.document_type,
                                "category": knowledge.category or "",
                                "tags": knowledge.tags or [],
                            },
                            update_pgvector=update_pgvector,
                            update_chroma=update_chroma,
                        )
                        processed_count += 1

                    except Exception as e:
                        logger.error(f"Error regenerating embeddings for {knowledge.id}: {e}")
                        # Continue with next document

                logger.info(f"Successfully regenerated embeddings for {processed_count} documents")
                return processed_count

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error regenerating embeddings: {e}")
            raise
