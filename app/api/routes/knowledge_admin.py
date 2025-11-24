"""
✅ CLEAN ARCHITECTURE - Knowledge Base Administration API Endpoints

RESTful API for managing the company knowledge base with full CRUD operations,
search capabilities, and embedding management.

MIGRATION STATUS:
  ✅ Uses Knowledge Use Cases via DependencyContainer
  ✅ Follows Clean Architecture and SOLID principles
  ✅ Proper dependency injection
  ✅ Maintains API contract compatibility

All endpoints require proper authentication and authorization (to be added).
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.core.container import DependencyContainer
from app.database.async_db import get_async_db
from app.models.knowledge_schemas import (
    ErrorResponse,
    KnowledgeCreate,
    KnowledgeListResponse,
    KnowledgeResponse,
    KnowledgeSearch,
    KnowledgeSearchResponse,
    KnowledgeStats,
    KnowledgeUpdate,
    MessageResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Create router
router = APIRouter(
    prefix="/api/v1/admin/knowledge",
    tags=["Knowledge Base Administration"],
    responses={
        404: {"model": ErrorResponse, "description": "Resource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


# ============================================================================
# CRUD Endpoints
# ============================================================================


@router.post(
    "",
    response_model=KnowledgeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create knowledge document",
    description="Create a new knowledge base document with automatic embedding generation",
)
async def create_knowledge(
    knowledge: KnowledgeCreate,
    auto_embed: bool = Query(True, description="Automatically generate embeddings"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Create a new knowledge document.

    - **title**: Document title (required)
    - **content**: Document content, minimum 50 characters (required)
    - **document_type**: Type of document (required)
    - **category**: Optional secondary category
    - **tags**: List of tags for categorization
    - **metadata**: Custom metadata dictionary
    - **active**: Whether document is active (default: true)
    - **auto_embed**: Generate embeddings automatically (default: true)

    Returns the created document with its UUID.
    """
    try:
        container = DependencyContainer()
        use_case = container.create_create_knowledge_use_case(db)
        result = await use_case.execute(
            knowledge_data=knowledge.model_dump(),
            auto_embed=auto_embed,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error creating knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge document",
        ) from e


@router.get(
    "/{knowledge_id}",
    response_model=KnowledgeResponse,
    summary="Get knowledge document",
    description="Retrieve a specific knowledge document by ID",
)
async def get_knowledge(
    knowledge_id: UUID,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Get a knowledge document by its UUID.

    Returns the complete document including all metadata and content.
    """
    try:
        container = DependencyContainer()
        use_case = container.create_get_knowledge_use_case(db)
        result = await use_case.execute(knowledge_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge document {knowledge_id} not found",
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting knowledge {knowledge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge document",
        ) from e


@router.get(
    "",
    response_model=KnowledgeListResponse,
    summary="List knowledge documents",
    description="List all knowledge documents with optional filtering and pagination",
)
async def list_knowledge(
    document_type: Optional[str] = Query(None, description="Filter by document type"),  # noqa: B008
    category: Optional[str] = Query(None, description="Filter by category"),  # noqa: B008
    tags: Optional[List[str]] = Query(None, description="Filter by tags (OR logic)"),  # noqa: B008
    active_only: bool = Query(True, description="Only return active documents"),  # noqa: B008
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    List knowledge documents with optional filters and pagination.

    - **document_type**: Filter by document type
    - **category**: Filter by category
    - **tags**: Filter by tags (documents with ANY of these tags)
    - **active_only**: Only show active documents
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)

    Returns paginated list with metadata.
    """
    try:
        container = DependencyContainer()
        use_case = container.create_list_knowledge_use_case(db)
        result = await use_case.execute(
            document_type=document_type,
            category=category,
            tags=tags,
            active_only=active_only,
            page=page,
            page_size=page_size,
        )
        return result
    except Exception as e:
        logger.error(f"Error listing knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list knowledge documents",
        ) from e


@router.put(
    "/{knowledge_id}",
    response_model=KnowledgeResponse,
    summary="Update knowledge document",
    description="Update an existing knowledge document",
)
async def update_knowledge(
    knowledge_id: UUID,
    knowledge: KnowledgeUpdate,
    regenerate_embedding: bool = Query(True, description="Regenerate embeddings if content changed"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Update a knowledge document.

    Only provided fields will be updated. Omitted fields remain unchanged.

    - **regenerate_embedding**: Auto-regenerate embeddings if title/content changed

    Returns the updated document.
    """
    try:
        # Only include fields that were provided
        update_data = knowledge.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        container = DependencyContainer()
        use_case = container.create_update_knowledge_use_case(db)
        result = await use_case.execute(
            knowledge_id=knowledge_id,
            update_data=update_data,
            regenerate_embedding=regenerate_embedding,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge document {knowledge_id} not found",
            )

        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating knowledge {knowledge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update knowledge document",
        ) from e


@router.delete(
    "/{knowledge_id}",
    response_model=MessageResponse,
    summary="Delete knowledge document",
    description="Delete a knowledge document (soft or hard delete)",
)
async def delete_knowledge(
    knowledge_id: UUID,
    hard_delete: bool = Query(False, description="Permanently delete (true) or deactivate (false)"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Delete a knowledge document.

    - **hard_delete=false** (default): Soft delete (set active=false)
    - **hard_delete=true**: Permanently delete from database and ChromaDB

    Soft delete is recommended to preserve history.
    """
    try:
        container = DependencyContainer()
        use_case = container.create_delete_knowledge_use_case(db)
        success = await use_case.execute(
            knowledge_id=knowledge_id,
            soft_delete=not hard_delete,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge document {knowledge_id} not found",
            )

        return MessageResponse(
            message=f"Knowledge document {'deleted' if hard_delete else 'deactivated'} successfully",
            success=True,
            details={"knowledge_id": str(knowledge_id), "hard_delete": hard_delete},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting knowledge {knowledge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge document",
        ) from e


# ============================================================================
# Search Endpoints
# ============================================================================


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    summary="Search knowledge base",
    description="Search the knowledge base using semantic and/or full-text search",
)
async def search_knowledge(
    search: KnowledgeSearch,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Search the knowledge base with various strategies.

    - **query**: Search text (required)
    - **max_results**: Maximum results to return (1-50)
    - **document_type**: Filter by document type
    - **category**: Filter by category
    - **tags**: Filter by tags
    - **search_strategy**: pgvector_primary | chroma_primary | hybrid (default)

    Returns ranked results with similarity scores.
    """
    try:
        container = DependencyContainer()
        use_case = container.create_search_knowledge_use_case(db)
        results = await use_case.execute(
            query=search.query,
            max_results=search.max_results,
            document_type=search.document_type,
            category=search.category,
            tags=search.tags,
            search_strategy=search.search_strategy,
        )

        return KnowledgeSearchResponse(
            query=search.query,
            results=results,
            total_results=len(results),
            search_strategy=search.search_strategy or "hybrid",
        )
    except Exception as e:
        logger.error(f"Error searching knowledge: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search knowledge base",
        ) from e


# ============================================================================
# Embedding Management Endpoints
# ============================================================================


@router.post(
    "/{knowledge_id}/regenerate-embedding",
    response_model=MessageResponse,
    summary="Regenerate embeddings for document",
    description="Force regeneration of vector embeddings for a specific document",
)
async def regenerate_embedding(
    knowledge_id: UUID,
    update_pgvector: bool = Query(True, description="Update pgvector embeddings"),  # noqa: B008
    update_chroma: bool = Query(True, description="Update ChromaDB embeddings"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Regenerate embeddings for a specific document.

    Useful when:
    - Changing embedding models
    - Fixing corrupted embeddings
    - Re-syncing after manual content edits

    - **update_pgvector**: Update PostgreSQL pgvector embeddings
    - **update_chroma**: Update ChromaDB embeddings
    """
    try:
        container = DependencyContainer()
        use_case = container.create_regenerate_knowledge_embeddings_use_case(db)

        # Regenerate embeddings (will verify document exists)
        await use_case.execute(
            knowledge_id=knowledge_id,
            update_pgvector=update_pgvector,
            update_chroma=update_chroma,
        )

        return MessageResponse(
            message=f"Embeddings regenerated successfully for document {knowledge_id}",
            success=True,
            details={
                "knowledge_id": str(knowledge_id),
                "pgvector_updated": update_pgvector,
                "chroma_updated": update_chroma,
            },
        )
    except ValueError as e:
        # Document not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating embeddings for {knowledge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate embeddings",
        ) from e


@router.post(
    "/sync-all",
    response_model=MessageResponse,
    summary="Sync all embeddings",
    description="Regenerate embeddings for ALL documents in the knowledge base",
)
async def sync_all_embeddings(
    update_pgvector: bool = Query(True, description="Update pgvector embeddings"),  # noqa: B008
    update_chroma: bool = Query(True, description="Update ChromaDB embeddings"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Regenerate embeddings for ALL knowledge documents.

    WARNING: This can take several minutes for large knowledge bases.
    Use with caution in production environments.

    - **update_pgvector**: Update PostgreSQL pgvector embeddings
    - **update_chroma**: Update ChromaDB embeddings

    This endpoint is useful for:
    - Initial setup after bulk import
    - Recovering from embedding corruption
    - Migrating to a new embedding model
    """
    try:
        logger.info(f"Starting full embedding sync (pgvector={update_pgvector}, chroma={update_chroma})")

        container = DependencyContainer()
        use_case = container.create_regenerate_knowledge_embeddings_use_case(db)

        # Regenerate all embeddings (knowledge_id=None means all documents)
        processed_count = await use_case.execute(
            knowledge_id=None,
            update_pgvector=update_pgvector,
            update_chroma=update_chroma,
        )

        return MessageResponse(
            message="All embeddings synchronized successfully",
            success=True,
            details={
                "pgvector_updated": update_pgvector,
                "chroma_updated": update_chroma,
                "processed_documents": processed_count,
            },
        )
    except Exception as e:
        logger.error(f"Error syncing all embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync embeddings",
        ) from e


@router.get(
    "/stats",
    response_model=KnowledgeStats,
    summary="Get knowledge base statistics",
    description="Retrieve statistics about the knowledge base",
)
async def get_stats(
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Get comprehensive statistics about the knowledge base.

    Returns:
    - Database statistics (active, inactive, embedding coverage)
    - ChromaDB collection counts
    - Embedding model information
    """
    try:
        container = DependencyContainer()
        use_case = container.create_get_knowledge_statistics_use_case(db)
        stats = await use_case.execute()
        return stats
    except Exception as e:
        logger.error(f"Error getting knowledge base statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics",
        ) from e


# ============================================================================
# Health Check Endpoint
# ============================================================================


@router.get(
    "/health",
    response_model=MessageResponse,
    summary="Health check",
    description="Check if the knowledge base API is operational",
)
async def health_check(
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Simple health check endpoint to verify API is running.

    Returns success message if all systems are operational.
    """
    try:
        container = DependencyContainer()
        use_case = container.create_get_knowledge_statistics_use_case(db)
        # Quick check: count active documents
        stats = await use_case.execute()

        return MessageResponse(
            message="Knowledge Base API is operational",
            success=True,
            details={
                "active_documents": stats["database"]["total_active"],
                "embedding_model": stats["embedding_model"],
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Base API is not operational",
        ) from e
