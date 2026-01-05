# ============================================================================
# SCOPE: MIXED (Dual-mode)
# Description: Unified Knowledge Admin API that automatically handles both
#              company_knowledge and agent_knowledge tables transparently.
# ============================================================================
"""
Unified Knowledge Admin API - Automatically handles both knowledge sources.

This router provides a unified interface for knowledge operations without
requiring the frontend to know which table the document belongs to.

The router automatically:
1. Detects which table contains the document (company_knowledge or agent_knowledge)
2. Executes operations on the correct table
3. Returns metadata indicating the source

Endpoints:
- GET /admin/knowledge-unified/{id} - Get document from either table
- PUT /admin/knowledge-unified/{id} - Update document in correct table
- DELETE /admin/knowledge-unified/{id} - Delete document from correct table
"""

import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases.agent_knowledge_use_cases import (
    RegenerateAgentKnowledgeEmbeddingUseCase,
)
from app.domains.shared.infrastructure.repositories.agent_knowledge_repository import (
    AgentKnowledgeRepository,
)
from app.integrations.vector_stores import KnowledgeEmbeddingService
from app.repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)


# ============================================================================
# Schemas
# ============================================================================


class UnifiedKnowledgeResponse(BaseModel):
    """Response schema for unified knowledge operations."""

    # Source metadata
    source: Literal["company", "agent"] = Field(
        ..., description="Which table this document belongs to"
    )
    agent_key: str | None = Field(
        None, description="Agent key (only for agent knowledge)"
    )

    # Document fields
    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    document_type: str = Field(..., description="Document type")
    category: str | None = Field(None, description="Document category")
    tags: list[str] = Field(default_factory=list, description="Document tags")
    meta_data: dict = Field(default_factory=dict, description="Document metadata")
    active: bool = Field(True, description="Whether document is active")
    has_embedding: bool = Field(False, description="Whether document has embedding")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")


class UnifiedKnowledgeUpdate(BaseModel):
    """Update schema for unified knowledge operations."""

    title: str | None = Field(None, description="Document title")
    content: str | None = Field(None, description="Document content")
    document_type: str | None = Field(None, description="Document type")
    category: str | None = Field(None, description="Document category")
    tags: list[str] | None = Field(None, description="Document tags")
    active: bool | None = Field(None, description="Whether document is active")


class MessageResponse(BaseModel):
    """Simple message response."""

    success: bool
    message: str
    details: dict | None = None


# ============================================================================
# Router
# ============================================================================

router = APIRouter(
    prefix="/admin/knowledge-unified",
    tags=["Unified Knowledge"],
    responses={
        404: {"description": "Document not found in any knowledge table"},
        500: {"description": "Internal server error"},
    },
)


# ============================================================================
# Helper Functions
# ============================================================================


async def find_knowledge_source(
    knowledge_id: UUID, db: AsyncSession
) -> tuple[Literal["company", "agent"] | None, dict | None]:
    """
    Find which table contains the document.

    Args:
        knowledge_id: Document UUID to search for
        db: Database session

    Returns:
        Tuple of (source, document_dict) or (None, None) if not found
    """
    # 1. Search in company_knowledge first
    company_repo = KnowledgeRepository(db)
    company_doc = await company_repo.get_by_id(knowledge_id)
    if company_doc:
        return ("company", _company_doc_to_dict(company_doc))

    # 2. Search in agent_knowledge
    agent_repo = AgentKnowledgeRepository(db)
    agent_doc = await agent_repo.get_by_id(knowledge_id)
    if agent_doc:
        return ("agent", agent_doc)

    return (None, None)


def _company_doc_to_dict(doc) -> dict:
    """Convert CompanyKnowledge model to dict."""
    return {
        "id": str(doc.id),
        "title": doc.title,
        "content": doc.content,
        "document_type": doc.document_type,
        "category": doc.category,
        "tags": doc.tags or [],
        "meta_data": doc.meta_data or {},
        "active": doc.active,
        "has_embedding": doc.embedding is not None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


def _build_unified_response(
    source: Literal["company", "agent"], doc: dict
) -> UnifiedKnowledgeResponse:
    """Build unified response from document dict."""
    return UnifiedKnowledgeResponse(
        source=source,
        agent_key=doc.get("agent_key") if source == "agent" else None,
        id=doc["id"],
        title=doc["title"],
        content=doc["content"],
        document_type=doc["document_type"],
        category=doc.get("category"),
        tags=doc.get("tags", []),
        meta_data=doc.get("meta_data", {}),
        active=doc.get("active", True),
        has_embedding=doc.get("has_embedding", False),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/{knowledge_id}",
    response_model=UnifiedKnowledgeResponse,
    summary="Get knowledge document from any source",
    description="Automatically finds and returns document from company_knowledge or agent_knowledge",
)
async def get_unified_knowledge(
    knowledge_id: UUID,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> UnifiedKnowledgeResponse:
    """
    Get a knowledge document by ID, searching both tables automatically.

    Returns the document with metadata indicating its source (company or agent).
    """
    source, doc = await find_knowledge_source(knowledge_id, db)

    if not source or not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document {knowledge_id} not found in any table",
        )

    return _build_unified_response(source, doc)


@router.put(
    "/{knowledge_id}",
    response_model=UnifiedKnowledgeResponse,
    summary="Update knowledge document in correct table",
    description="Automatically updates document in the correct table (company or agent)",
)
async def update_unified_knowledge(
    knowledge_id: UUID,
    update_data: UnifiedKnowledgeUpdate,
    regenerate_embedding: bool = Query(  # noqa: B008
        True, description="Regenerate embeddings if content changed"
    ),
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> UnifiedKnowledgeResponse:
    """
    Update a knowledge document, automatically detecting and using the correct table.

    The endpoint:
    1. Finds which table contains the document
    2. Updates the document in that table
    3. Optionally regenerates embeddings if content changed
    4. Returns the updated document with source metadata
    """
    # Find source
    source, existing_doc = await find_knowledge_source(knowledge_id, db)

    if not source or not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document {knowledge_id} not found in any table",
        )

    # Prepare update data (exclude None values)
    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    updated_doc: dict | None = None

    try:
        if source == "company":
            # Update in company_knowledge
            company_repo = KnowledgeRepository(db)
            result = await company_repo.update(knowledge_id, update_dict)
            if result:
                await db.commit()
                updated_doc = _company_doc_to_dict(result)
                logger.info(f"Updated company knowledge: {knowledge_id}")

        else:  # source == "agent"
            # Update in agent_knowledge
            agent_repo = AgentKnowledgeRepository(db)
            updated_doc = await agent_repo.update(knowledge_id, **update_dict)
            logger.info(f"Updated agent knowledge: {knowledge_id}")

        if not updated_doc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document",
            )

        # Regenerate embeddings if content changed
        if regenerate_embedding and any(
            key in update_dict for key in ["title", "content"]
        ):
            try:
                if source == "company":
                    embedding_service = KnowledgeEmbeddingService()
                    await embedding_service.update_knowledge_embeddings(
                        knowledge_id=str(knowledge_id)
                    )
                else:
                    # Use the use case for agent knowledge
                    regen_use_case = RegenerateAgentKnowledgeEmbeddingUseCase(db)
                    await regen_use_case.execute(str(knowledge_id))
                logger.info(f"Regenerated embeddings for {source}: {knowledge_id}")
            except Exception as e:
                # Don't fail the update, just log
                logger.warning(f"Failed to regenerate embeddings: {e}")

        return _build_unified_response(source, updated_doc)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating unified knowledge {knowledge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document: {str(e)}",
        ) from e


@router.delete(
    "/{knowledge_id}",
    response_model=MessageResponse,
    summary="Delete knowledge document from correct table",
    description="Automatically deletes document from the correct table (company or agent)",
)
async def delete_unified_knowledge(
    knowledge_id: UUID,
    hard_delete: bool = Query(  # noqa: B008
        False, description="Permanently delete (true) or soft delete (false)"
    ),
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> MessageResponse:
    """
    Delete a knowledge document, automatically detecting the correct table.

    - hard_delete=false (default): Soft delete (sets active=False)
    - hard_delete=true: Permanently removes from database
    """
    # Find source
    source, existing_doc = await find_knowledge_source(knowledge_id, db)

    if not source or not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document {knowledge_id} not found in any table",
        )

    try:
        success = False

        if source == "company":
            company_repo = KnowledgeRepository(db)
            if hard_delete:
                success = await company_repo.delete(knowledge_id)
            else:
                result = await company_repo.soft_delete(knowledge_id)
                success = result is not None
            await db.commit()

        else:  # source == "agent"
            agent_repo = AgentKnowledgeRepository(db)
            success = await agent_repo.delete(knowledge_id, hard=hard_delete)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete document",
            )

        action = "deleted" if hard_delete else "deactivated"
        logger.info(f"{action.capitalize()} {source} knowledge: {knowledge_id}")

        return MessageResponse(
            success=True,
            message=f"Document {action} successfully",
            details={
                "knowledge_id": str(knowledge_id),
                "source": source,
                "agent_key": existing_doc.get("agent_key") if source == "agent" else None,
                "hard_delete": hard_delete,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting unified knowledge {knowledge_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        ) from e
