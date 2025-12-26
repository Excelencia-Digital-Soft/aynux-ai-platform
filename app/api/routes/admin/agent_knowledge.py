"""
Agent Knowledge Admin API Routes

Endpoints for managing agent-specific knowledge bases.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.agent_knowledge import (
    AgentKnowledgeCreate,
    AgentKnowledgeDetail,
    AgentKnowledgeResponse,
    AgentKnowledgeSearchRequest,
    AgentKnowledgeSearchResponse,
    AgentKnowledgeSearchResult,
    AgentKnowledgeStats,
    AgentKnowledgeUpdate,
    AvailableAgentsResponse,
)
from app.config.settings import get_settings
from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases.agent_knowledge_use_cases import (
    CreateAgentKnowledgeUseCase,
    DeleteAgentKnowledgeUseCase,
    GetAgentKnowledgeStatsUseCase,
    ListAgentKnowledgeUseCase,
    RegenerateAgentKnowledgeEmbeddingUseCase,
    SearchAgentKnowledgeUseCase,
    UploadAgentDocumentUseCase,
)
from app.domains.shared.infrastructure.repositories.agent_knowledge_repository import (
    AgentKnowledgeRepository,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/agents", tags=["Agent Knowledge"])


@router.get("/available", response_model=AvailableAgentsResponse)
async def get_available_agents() -> AvailableAgentsResponse:
    """
    Get list of available agents from ENABLED_AGENTS setting.
    """
    enabled = settings.ENABLED_AGENTS or []
    return AvailableAgentsResponse(agents=enabled, total=len(enabled))


@router.get("/{agent_key}/knowledge", response_model=list[AgentKnowledgeResponse])
async def list_agent_knowledge(
    agent_key: str,
    active_only: bool = Query(True, description="Only return active documents"),
    limit: int | None = Query(None, ge=1, le=100, description="Max documents to return"),
    db: AsyncSession = Depends(get_async_db),
) -> list[AgentKnowledgeResponse]:
    """
    List all knowledge documents for an agent.
    """
    use_case = ListAgentKnowledgeUseCase(db)
    docs = await use_case.execute(agent_key=agent_key, active_only=active_only, limit=limit)

    return [
        AgentKnowledgeResponse(
            id=doc["id"],
            agent_key=doc["agent_key"],
            title=doc["title"],
            content_preview=doc.get("content_preview", doc.get("content", "")[:200]),
            document_type=doc["document_type"],
            category=doc.get("category"),
            tags=doc.get("tags", []),
            has_embedding=doc.get("has_embedding", False),
            embedding_status=doc.get("embedding_status", "missing"),
            embedding_updated_at=doc.get("embedding_updated_at"),
            active=doc.get("active", True),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
        )
        for doc in docs
    ]


@router.get("/{agent_key}/knowledge/stats", response_model=AgentKnowledgeStats)
async def get_agent_knowledge_stats(
    agent_key: str,
    db: AsyncSession = Depends(get_async_db),
) -> AgentKnowledgeStats:
    """
    Get statistics for an agent's knowledge base.
    """
    use_case = GetAgentKnowledgeStatsUseCase(db)
    stats = await use_case.execute(agent_key)

    return AgentKnowledgeStats(**stats)


@router.post("/{agent_key}/knowledge", response_model=AgentKnowledgeDetail)
async def create_agent_knowledge(
    agent_key: str,
    data: AgentKnowledgeCreate,
    db: AsyncSession = Depends(get_async_db),
) -> AgentKnowledgeDetail:
    """
    Create a new knowledge document from text.
    """
    use_case = CreateAgentKnowledgeUseCase(db)

    try:
        result = await use_case.execute(
            agent_key=agent_key,
            title=data.title,
            content=data.content,
            document_type=data.document_type,
            category=data.category,
            tags=data.tags,
            auto_embed=True,
        )

        return AgentKnowledgeDetail(
            id=result["id"],
            agent_key=result["agent_key"],
            title=result["title"],
            content=result["content"],
            document_type=result["document_type"],
            category=result.get("category"),
            tags=result.get("tags", []),
            meta_data=result.get("meta_data", {}),
            has_embedding=result.get("has_embedding", False),
            embedding_status=result.get("embedding_status", "missing"),
            embedding_updated_at=result.get("embedding_updated_at"),
            active=result.get("active", True),
            sort_order=result.get("sort_order", 0),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{agent_key}/knowledge/upload", response_model=AgentKnowledgeDetail)
async def upload_agent_document(
    agent_key: str,
    file: UploadFile = File(..., description="Document file (PDF, DOCX, TXT, MD)"),
    title: str | None = Form(None, description="Optional document title"),
    document_type: str = Form("uploaded_file", description="Document type"),
    category: str | None = Form(None, description="Optional category"),
    tags: str | None = Form(None, description="Comma-separated tags"),
    db: AsyncSession = Depends(get_async_db),
) -> AgentKnowledgeDetail:
    """
    Upload a document file to the agent's knowledge base.

    Supports: PDF, DOCX, TXT, MD
    """
    # Validate file type
    filename = file.filename or "unknown"
    allowed_extensions = {".pdf", ".docx", ".txt", ".md"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(allowed_extensions)}",
        )

    # Read file content
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}") from e

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Upload document
    use_case = UploadAgentDocumentUseCase(db)

    try:
        result = await use_case.execute(
            agent_key=agent_key,
            file_bytes=file_bytes,
            filename=filename,
            title=title,
            document_type=document_type,
            category=category,
            tags=tag_list,
        )

        return AgentKnowledgeDetail(
            id=result["id"],
            agent_key=result["agent_key"],
            title=result["title"],
            content=result["content"],
            document_type=result["document_type"],
            category=result.get("category"),
            tags=result.get("tags", []),
            meta_data=result.get("meta_data", {}),
            has_embedding=result.get("has_embedding", False),
            embedding_status=result.get("embedding_status", "missing"),
            embedding_updated_at=result.get("embedding_updated_at"),
            active=result.get("active", True),
            sort_order=result.get("sort_order", 0),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{agent_key}/knowledge/{doc_id}", response_model=AgentKnowledgeDetail)
async def get_agent_knowledge_document(
    agent_key: str,
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> AgentKnowledgeDetail:
    """
    Get a specific knowledge document by ID.
    """
    try:
        doc_uuid = UUID(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid document ID format") from e

    repo = AgentKnowledgeRepository(db)
    doc = await repo.get_by_id(doc_uuid)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc["agent_key"] != agent_key:
        raise HTTPException(status_code=404, detail="Document not found for this agent")

    return AgentKnowledgeDetail(
        id=doc["id"],
        agent_key=doc["agent_key"],
        title=doc["title"],
        content=doc["content"],
        document_type=doc["document_type"],
        category=doc.get("category"),
        tags=doc.get("tags", []),
        meta_data=doc.get("meta_data", {}),
        has_embedding=doc.get("has_embedding", False),
        embedding_status=doc.get("embedding_status", "missing"),
        embedding_updated_at=doc.get("embedding_updated_at"),
        active=doc.get("active", True),
        sort_order=doc.get("sort_order", 0),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.put("/{agent_key}/knowledge/{doc_id}", response_model=AgentKnowledgeDetail)
async def update_agent_knowledge_document(
    agent_key: str,
    doc_id: str,
    data: AgentKnowledgeUpdate,
    db: AsyncSession = Depends(get_async_db),
) -> AgentKnowledgeDetail:
    """
    Update an existing knowledge document.
    """
    try:
        doc_uuid = UUID(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid document ID format") from e

    repo = AgentKnowledgeRepository(db)

    # Verify document exists and belongs to agent
    existing = await repo.get_by_id(doc_uuid)
    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    if existing["agent_key"] != agent_key:
        raise HTTPException(status_code=404, detail="Document not found for this agent")

    # Update document
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await repo.update(doc_uuid, **update_data)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to update document")

    return AgentKnowledgeDetail(
        id=result["id"],
        agent_key=result["agent_key"],
        title=result["title"],
        content=result["content"],
        document_type=result["document_type"],
        category=result.get("category"),
        tags=result.get("tags", []),
        meta_data=result.get("meta_data", {}),
        has_embedding=result.get("has_embedding", False),
        embedding_status=result.get("embedding_status", "missing"),
        embedding_updated_at=result.get("embedding_updated_at"),
        active=result.get("active", True),
        sort_order=result.get("sort_order", 0),
        created_at=result.get("created_at"),
        updated_at=result.get("updated_at"),
    )


@router.delete("/{agent_key}/knowledge/{doc_id}")
async def delete_agent_knowledge_document(
    agent_key: str,
    doc_id: str,
    hard_delete: bool = Query(False, description="Permanently delete (vs soft delete)"),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Delete a knowledge document.

    By default performs a soft delete (sets active=False).
    Use hard_delete=True to permanently remove.
    """
    try:
        doc_uuid = UUID(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid document ID format") from e

    # Verify document belongs to agent
    repo = AgentKnowledgeRepository(db)
    existing = await repo.get_by_id(doc_uuid)

    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    if existing["agent_key"] != agent_key:
        raise HTTPException(status_code=404, detail="Document not found for this agent")

    use_case = DeleteAgentKnowledgeUseCase(db)
    deleted = await use_case.execute(doc_id, hard_delete=hard_delete)

    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete document")

    return {
        "success": True,
        "message": "Document deleted" if hard_delete else "Document deactivated",
        "document_id": doc_id,
    }


@router.post("/{agent_key}/knowledge/search", response_model=AgentKnowledgeSearchResponse)
async def search_agent_knowledge(
    agent_key: str,
    request: AgentKnowledgeSearchRequest,
    db: AsyncSession = Depends(get_async_db),
) -> AgentKnowledgeSearchResponse:
    """
    Search agent knowledge base semantically.
    """
    use_case = SearchAgentKnowledgeUseCase(db)

    results = await use_case.execute(
        agent_key=agent_key,
        query=request.query,
        max_results=request.max_results,
        min_similarity=request.min_similarity,
    )

    return AgentKnowledgeSearchResponse(
        query=request.query,
        agent_key=agent_key,
        results=[
            AgentKnowledgeSearchResult(
                id=r["id"],
                title=r["title"],
                content=r["content"],
                similarity_score=r.get("similarity_score", 0),
                document_type=r["document_type"],
                category=r.get("category"),
            )
            for r in results
        ],
        total_results=len(results),
    )


@router.post("/{agent_key}/knowledge/{doc_id}/embedding")
async def regenerate_document_embedding(
    agent_key: str,
    doc_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Regenerate embedding for a specific document.
    """
    try:
        doc_uuid = UUID(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid document ID format") from e

    # Verify document belongs to agent
    repo = AgentKnowledgeRepository(db)
    existing = await repo.get_by_id(doc_uuid)

    if not existing:
        raise HTTPException(status_code=404, detail="Document not found")

    if existing["agent_key"] != agent_key:
        raise HTTPException(status_code=404, detail="Document not found for this agent")

    use_case = RegenerateAgentKnowledgeEmbeddingUseCase(db)
    success = await use_case.execute(doc_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to regenerate embedding")

    return {
        "success": True,
        "message": "Embedding regenerated successfully",
        "document_id": doc_id,
    }
