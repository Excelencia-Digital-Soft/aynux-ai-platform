# ============================================================================
# SCOPE: MIXED (Dual-mode)
# Description: API de administración de Knowledge Base. Soporta modo global
#              y multi-tenant via get_di_container_dual().
# Tenant-Aware: Parcial - usa VectorStore dual-mode (TenantVectorStore si hay ctx).
# ============================================================================
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
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_di_container_dual
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
    KnowledgeSearchResult,
    KnowledgeStats,
    KnowledgeUpdate,
    MessageResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Create router (prefix is relative - api_router adds /api/v1)
router = APIRouter(
    prefix="/admin/knowledge",
    tags=["Knowledge Base Administration"],
    responses={
        404: {"model": ErrorResponse, "description": "Resource not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


# ============================================================================
# Static Path Endpoints (must be before dynamic /{knowledge_id} routes)
# ============================================================================


@router.get(
    "/stats",
    response_model=KnowledgeStats,
    summary="Get knowledge base statistics",
    description="Retrieve statistics about the knowledge base",
)
async def get_stats(
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Get comprehensive statistics about the knowledge base.

    Returns:
    - Database statistics (active, inactive, embedding coverage)
    - pgvector embedding counts
    - Embedding model information
    """
    try:
        use_case = container.create_get_knowledge_statistics_use_case(db)
        stats = await use_case.execute()
        return stats
    except Exception as e:
        logger.error(f"Error getting knowledge base statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics",
        ) from e


@router.get(
    "/health",
    response_model=MessageResponse,
    summary="Health check",
    description="Check if the knowledge base API is operational",
)
async def health_check(
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Simple health check endpoint to verify API is running.

    Returns success message if all systems are operational.
    """
    try:
        use_case = container.create_get_knowledge_statistics_use_case(db)
        # Quick check: count active documents
        stats = await use_case.execute()

        return MessageResponse(
            message="Knowledge Base API is operational",
            success=True,
            details={
                "active_documents": stats["total_active"],
                "embedding_model": stats["embedding_model"],
            },
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge Base API is not operational",
        ) from e


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
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
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
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Get a knowledge document by its UUID.

    Returns the complete document including all metadata and content.
    """
    try:
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
    tags: Optional[list[str]] = Query(None, description="Filter by tags (OR logic)"),  # noqa: B008
    active_only: bool = Query(True, description="Only return active documents"),  # noqa: B008
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),  # noqa: B008
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
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
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
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
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Delete a knowledge document.

    - **hard_delete=false** (default): Soft delete (set active=false)
    - **hard_delete=true**: Permanently delete from database and pgvector

    Soft delete is recommended to preserve history.
    """
    try:
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
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Search the knowledge base using pgvector semantic search.

    - **query**: Search text (required)
    - **max_results**: Maximum results to return (1-50)
    - **document_type**: Filter by document type
    - **category**: Filter by category
    - **tags**: Filter by tags

    Returns ranked results with similarity scores.
    """
    try:
        use_case = container.create_search_knowledge_use_case(db)
        results = await use_case.execute(
            query=search.query,
            max_results=search.max_results,
            document_type=search.document_type,
            category=search.category,
            tags=search.tags,
        )

        # Convert dict results to KnowledgeSearchResult objects
        search_results = [KnowledgeSearchResult(**result) for result in results]

        return KnowledgeSearchResponse(
            query=search.query,
            results=search_results,
            total_results=len(search_results),
            search_strategy="pgvector",
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
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Regenerate pgvector embeddings for a specific document.

    Useful when:
    - Changing embedding models
    - Fixing corrupted embeddings
    - Re-syncing after manual content edits
    """
    try:
        use_case = container.create_regenerate_knowledge_embeddings_use_case(db)

        # Regenerate embeddings (will verify document exists)
        await use_case.execute(knowledge_id=knowledge_id)

        return MessageResponse(
            message=f"Embeddings regenerated successfully for document {knowledge_id}",
            success=True,
            details={
                "knowledge_id": str(knowledge_id),
                "pgvector_updated": True,
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
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
    container: DependencyContainer = Depends(get_di_container_dual),  # noqa: B008
):
    """
    Regenerate pgvector embeddings for ALL knowledge documents.

    WARNING: This can take several minutes for large knowledge bases.
    Use with caution in production environments.

    This endpoint is useful for:
    - Initial setup after bulk import
    - Recovering from embedding corruption
    - Migrating to a new embedding model
    """
    try:
        logger.info("Starting full pgvector embedding sync")

        use_case = container.create_regenerate_knowledge_embeddings_use_case(db)

        # Regenerate all embeddings (knowledge_id=None means all documents)
        processed_count = await use_case.execute(knowledge_id=None)

        return MessageResponse(
            message="All embeddings synchronized successfully",
            success=True,
            details={
                "pgvector_updated": True,
                "processed_documents": processed_count,
            },
        )
    except Exception as e:
        logger.error(f"Error syncing all embeddings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync embeddings",
        ) from e


# ============================================================================
# Batch Operations Endpoints
# ============================================================================


from pydantic import BaseModel, Field
from app.domains.shared.application.use_cases.batch_knowledge_use_cases import (
    BatchUpdateDocumentsUseCase,
    BatchDeleteDocumentsUseCase,
    BatchRegenerateEmbeddingsUseCase,
)


class BatchUpdateRequest(BaseModel):
    """Request schema for batch update operations."""

    doc_ids: list[str] = Field(..., description="List of document UUIDs to update")
    update_data: dict = Field(
        ...,
        description="Fields to update: document_type, category, active, add_tags, remove_tags",
    )


class BatchDeleteRequest(BaseModel):
    """Request schema for batch delete operations."""

    doc_ids: list[str] = Field(..., description="List of document UUIDs to delete")
    hard_delete: bool = Field(
        False, description="Permanently delete (true) or soft delete (false)"
    )


class BatchEmbeddingRequest(BaseModel):
    """Request schema for batch embedding regeneration."""

    doc_ids: list[str] = Field(
        ..., description="List of document UUIDs to regenerate embeddings"
    )


class BatchOperationResponse(BaseModel):
    """Response schema for batch operations."""

    success: bool = Field(..., description="Whether operation completed successfully")
    success_count: int = Field(..., description="Number of successful operations")
    error_count: int = Field(..., description="Number of failed operations")
    errors: list[dict] = Field(
        default_factory=list, description="List of errors with doc_id and message"
    )
    message: str = Field(..., description="Summary message")


@router.put(
    "/batch-update",
    response_model=BatchOperationResponse,
    summary="Batch update documents",
    description="Update multiple knowledge documents at once",
)
async def batch_update_documents(
    request: BatchUpdateRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Batch update multiple knowledge documents.

    Supports updating:
    - **document_type**: Change document type
    - **category**: Change category
    - **active**: Activate or deactivate
    - **add_tags**: Add tags to documents
    - **remove_tags**: Remove tags from documents

    Returns count of successful and failed operations.
    """
    try:
        use_case = BatchUpdateDocumentsUseCase(db)
        result = await use_case.execute(
            doc_ids=request.doc_ids,
            update_data=request.update_data,
            table="company_knowledge",
        )

        return BatchOperationResponse(
            success=result.error_count == 0,
            success_count=result.success_count,
            error_count=result.error_count,
            errors=[{"doc_id": e[0], "error": e[1]} for e in result.errors],
            message=f"Updated {result.success_count} documents, {result.error_count} errors",
        )
    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch update documents",
        ) from e


@router.delete(
    "/batch-delete",
    response_model=BatchOperationResponse,
    summary="Batch delete documents",
    description="Delete multiple knowledge documents at once",
)
async def batch_delete_documents(
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Batch delete multiple knowledge documents.

    - **hard_delete=false** (default): Soft delete (set active=false)
    - **hard_delete=true**: Permanently delete from database

    Returns count of successful and failed operations.
    """
    try:
        use_case = BatchDeleteDocumentsUseCase(db)
        result = await use_case.execute(
            doc_ids=request.doc_ids,
            hard_delete=request.hard_delete,
            table="company_knowledge",
        )

        delete_type = "deleted" if request.hard_delete else "deactivated"
        return BatchOperationResponse(
            success=result.error_count == 0,
            success_count=result.success_count,
            error_count=result.error_count,
            errors=[{"doc_id": e[0], "error": e[1]} for e in result.errors],
            message=f"{result.success_count} documents {delete_type}, {result.error_count} errors",
        )
    except Exception as e:
        logger.error(f"Error in batch delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch delete documents",
        ) from e


@router.post(
    "/batch-regenerate-embeddings",
    response_model=BatchOperationResponse,
    summary="Batch regenerate embeddings",
    description="Regenerate embeddings for multiple documents at once",
)
async def batch_regenerate_embeddings(
    request: BatchEmbeddingRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Batch regenerate embeddings for multiple documents.

    Useful when:
    - Content was manually edited
    - Embedding model changed
    - Fixing corrupted embeddings

    Returns count of successful and failed operations.
    """
    try:
        use_case = BatchRegenerateEmbeddingsUseCase(db)
        result = await use_case.execute(
            doc_ids=request.doc_ids,
            table="company_knowledge",
        )

        return BatchOperationResponse(
            success=result.error_count == 0,
            success_count=result.success_count,
            error_count=result.error_count,
            errors=[{"doc_id": e[0], "error": e[1]} for e in result.errors],
            message=f"Regenerated embeddings for {result.success_count} documents, {result.error_count} errors",
        )
    except Exception as e:
        logger.error(f"Error in batch embedding regeneration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch regenerate embeddings",
        ) from e
