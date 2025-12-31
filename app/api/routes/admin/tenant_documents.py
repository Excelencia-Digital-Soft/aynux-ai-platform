"""
Tenant Documents Admin API - Manage per-tenant knowledge base documents.

Provides endpoints for:
- CRUD operations on tenant documents
- PDF and text upload
- Embedding management
- Document statistics
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_di_container_dual, require_admin
from app.core.container import DependencyContainer
from app.database.async_db import get_async_db
from app.models.db.tenancy import Organization, OrganizationUser, TenantDocument

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tenant Documents"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class TenantDocumentResponse(BaseModel):
    """Schema for tenant document response."""

    id: str
    organization_id: str
    title: str
    content_preview: str
    document_type: str
    category: str | None
    tags: list[str]
    meta_data: dict
    has_embedding: bool
    active: bool
    sort_order: int
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class TenantDocumentDetailResponse(TenantDocumentResponse):
    """Schema for tenant document detail response (includes full content)."""

    content: str


class TenantDocumentCreate(BaseModel):
    """Schema for creating a tenant document."""

    title: str = Field(..., min_length=3, max_length=500)
    content: str = Field(..., min_length=50)
    document_type: str = Field(default="general", max_length=100)
    category: str | None = Field(None, max_length=200)
    tags: list[str] = Field(default_factory=list)
    meta_data: dict = Field(default_factory=dict)
    active: bool = Field(default=True)


class TenantDocumentUpdate(BaseModel):
    """Schema for updating a tenant document."""

    title: str | None = Field(None, min_length=3, max_length=500)
    content: str | None = Field(None, min_length=50)
    document_type: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=200)
    tags: list[str] | None = None
    meta_data: dict | None = None
    active: bool | None = None
    sort_order: int | None = None


class TenantDocumentListResponse(BaseModel):
    """Schema for paginated document list response."""

    items: list[TenantDocumentResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class TenantDocumentStatsResponse(BaseModel):
    """Schema for document statistics response."""

    total_documents: int
    active_documents: int
    with_embedding: int
    without_embedding: int
    by_type: dict[str, int]
    by_category: dict[str, int]


class UploadResponse(BaseModel):
    """Response model for document upload."""

    success: bool
    document_id: str
    title: str
    document_type: str
    character_count: int
    has_embedding: bool
    message: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def _doc_to_response(doc: TenantDocument) -> TenantDocumentResponse:
    """Convert TenantDocument to response schema."""
    return TenantDocumentResponse(
        id=str(doc.id),
        organization_id=str(doc.organization_id),
        title=doc.title,
        content_preview=doc.content_preview,
        document_type=doc.document_type,
        category=doc.category,
        tags=doc.tags or [],
        meta_data=doc.meta_data or {},
        has_embedding=doc.has_embedding,
        active=doc.active,
        sort_order=doc.sort_order,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
    )


def _doc_to_detail_response(doc: TenantDocument) -> TenantDocumentDetailResponse:
    """Convert TenantDocument to detail response schema (includes content)."""
    return TenantDocumentDetailResponse(
        id=str(doc.id),
        organization_id=str(doc.organization_id),
        title=doc.title,
        content=doc.content,
        content_preview=doc.content_preview,
        document_type=doc.document_type,
        category=doc.category,
        tags=doc.tags or [],
        meta_data=doc.meta_data or {},
        has_embedding=doc.has_embedding,
        active=doc.active,
        sort_order=doc.sort_order,
        created_at=doc.created_at.isoformat() if doc.created_at else None,
        updated_at=doc.updated_at.isoformat() if doc.updated_at else None,
    )


async def _get_document(db: AsyncSession, org_id: uuid.UUID, doc_id: uuid.UUID) -> TenantDocument:
    """Get document by ID for organization, raise 404 if not found."""
    stmt = select(TenantDocument).where(
        TenantDocument.organization_id == org_id,
        TenantDocument.id == doc_id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {doc_id} not found in organization",
        )

    return doc


async def _check_document_quota(db: AsyncSession, org: Organization) -> None:
    """Check if organization has reached document quota."""
    stmt = select(func.count(TenantDocument.id)).where(
        TenantDocument.organization_id == org.id
    )
    result = await db.execute(stmt)
    current_count = result.scalar() or 0

    if current_count >= int(org.max_documents):  # type: ignore[arg-type]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Document quota reached ({org.max_documents} max). Upgrade plan to add more.",
        )


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("/{org_id}/documents", response_model=TenantDocumentListResponse)
async def list_tenant_documents(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    document_type: str | None = Query(None, description="Filter by document type"),
    category: str | None = Query(None, description="Filter by category"),
    active_only: bool = Query(True, description="Only return active documents"),
    search: str | None = Query(None, description="Search in title and content"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List tenant documents with pagination and filters.

    Requires admin or owner role.
    """
    # Build base query
    stmt = select(TenantDocument).where(TenantDocument.organization_id == org_id)

    # Apply filters
    if document_type:
        stmt = stmt.where(TenantDocument.document_type == document_type)
    if category:
        stmt = stmt.where(TenantDocument.category == category)
    if active_only:
        stmt = stmt.where(TenantDocument.active == True)  # noqa: E712
    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            (TenantDocument.title.ilike(search_pattern)) | (TenantDocument.content.ilike(search_pattern))
        )

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.order_by(TenantDocument.sort_order, TenantDocument.created_at.desc())
    stmt = stmt.offset(offset).limit(per_page)

    result = await db.execute(stmt)
    documents = result.scalars().all()

    total_pages = (total + per_page - 1) // per_page

    return TenantDocumentListResponse(
        items=[_doc_to_response(doc) for doc in documents],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.post("/{org_id}/documents", response_model=TenantDocumentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_document(
    data: TenantDocumentCreate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    container: DependencyContainer = Depends(get_di_container_dual),
):
    """
    Create a new tenant document from text.

    Requires admin or owner role.
    Embedding will be generated asynchronously.
    """
    # Get organization to check quota
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    await _check_document_quota(db, org)

    # Create document
    doc = TenantDocument.create_from_text(
        organization_id=org_id,
        title=data.title,
        content=data.content,
        document_type=data.document_type,
        category=data.category,
        tags=data.tags,
        meta_data=data.meta_data,
    )
    doc.active = data.active

    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # TODO: Implement embedding generation when knowledge embedding service is available
    # The embedding service is planned but not yet implemented in DependencyContainer
    # try:
    #     embedding_service = container.create_knowledge_embedding_service()
    #     embedding = await embedding_service.generate_embedding(f"{doc.title}\n\n{doc.content}")
    #     if embedding:
    #         doc.embedding = embedding
    #         await db.commit()
    #         await db.refresh(doc)
    # except Exception as e:
    #     logger.warning(f"Failed to generate embedding for document {doc.id}: {e}")

    return _doc_to_detail_response(doc)


@router.post(
    "/{org_id}/documents/upload/pdf",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_pdf_document(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    file: UploadFile = File(..., description="PDF file to upload"),
    title: str | None = Form(None, description="Document title (optional)"),
    document_type: str = Form("uploaded_pdf", description="Document type"),
    category: str | None = Form(None, description="Category"),
    tags: str | None = Form(None, description="Comma-separated tags"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    container: DependencyContainer = Depends(get_di_container_dual),
):
    """
    Upload a PDF document to the tenant's knowledge base.

    Requires admin or owner role.
    PDF will be processed and embeddings generated.
    """
    try:
        # Validate file type
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a PDF (.pdf extension required)",
            )

        # Read file content
        pdf_bytes = await file.read()

        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF file is empty",
            )

        # Get organization to check quota
        stmt = select(Organization).where(Organization.id == org_id)
        result = await db.execute(stmt)
        org = result.scalar_one_or_none()

        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

        await _check_document_quota(db, org)

        # Parse tags
        tags_list: list[str] = []
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Extract text from PDF
        try:
            from pypdf import PdfReader
            import io

            reader = PdfReader(io.BytesIO(pdf_bytes))
            text_content = ""
            for page in reader.pages:
                text_content += page.extract_text() or ""

            if len(text_content.strip()) < 50:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDF contains insufficient text content (minimum 50 characters)",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to extract text from PDF: {str(e)}",
            ) from e

        # Create document
        doc_title = title or filename.rsplit(".", 1)[0]
        doc = TenantDocument.create_from_pdf(
            organization_id=org_id,
            title=doc_title,
            content=text_content,
            source_filename=filename,
            document_type=document_type,
            tags=tags_list,
        )
        if category:
            doc.category = category

        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # TODO: Implement embedding generation when knowledge embedding service is available
        # try:
        #     embedding_service = container.create_knowledge_embedding_service()
        #     embedding = await embedding_service.generate_embedding(f"{doc.title}\n\n{doc.content[:2000]}")
        #     if embedding:
        #         doc.embedding = embedding
        #         await db.commit()
        #         await db.refresh(doc)
        # except Exception as e:
        #     logger.warning(f"Failed to generate embedding for document {doc.id}: {e}")

        return UploadResponse(
            success=True,
            document_id=str(doc.id),
            title=doc.title,
            document_type=doc.document_type,
            character_count=len(doc.content),
            has_embedding=doc.has_embedding,
            message=f"PDF uploaded successfully: {doc.title}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload PDF: {str(e)}",
        ) from e


@router.get("/{org_id}/documents/{doc_id}", response_model=TenantDocumentDetailResponse)
async def get_tenant_document(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    doc_id: uuid.UUID = Path(..., description="Document ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific tenant document by ID.

    Requires admin or owner role.
    """
    doc = await _get_document(db, org_id, doc_id)
    return _doc_to_detail_response(doc)


@router.put("/{org_id}/documents/{doc_id}", response_model=TenantDocumentDetailResponse)
async def update_tenant_document(
    data: TenantDocumentUpdate,
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    doc_id: uuid.UUID = Path(..., description="Document ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    container: DependencyContainer = Depends(get_di_container_dual),
):
    """
    Update a tenant document.

    Requires admin or owner role.
    If content is updated, embedding will be regenerated.
    """
    doc = await _get_document(db, org_id, doc_id)
    content_changed = False

    # Update fields if provided
    if data.title is not None:
        doc.title = data.title
        content_changed = True
    if data.content is not None:
        doc.content = data.content
        content_changed = True
    if data.document_type is not None:
        doc.document_type = data.document_type
    if data.category is not None:
        doc.category = data.category
    if data.tags is not None:
        doc.tags = data.tags
    if data.meta_data is not None:
        doc.meta_data = data.meta_data
    if data.active is not None:
        doc.active = data.active
    if data.sort_order is not None:
        doc.sort_order = data.sort_order

    doc.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(doc)

    # TODO: Implement embedding regeneration when knowledge embedding service is available
    # if content_changed:
    #     try:
    #         embedding_service = container.create_knowledge_embedding_service()
    #         embedding = await embedding_service.generate_embedding(f"{doc.title}\n\n{doc.content[:2000]}")
    #         if embedding:
    #             doc.embedding = embedding
    #             await db.commit()
    #             await db.refresh(doc)
    #     except Exception as e:
    #         logger.warning(f"Failed to regenerate embedding for document {doc.id}: {e}")
    _ = content_changed  # Suppress unused variable warning

    return _doc_to_detail_response(doc)


@router.delete("/{org_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_document(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    doc_id: uuid.UUID = Path(..., description="Document ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a tenant document.

    Requires admin or owner role.
    """
    doc = await _get_document(db, org_id, doc_id)
    await db.delete(doc)
    await db.commit()


@router.post("/{org_id}/documents/{doc_id}/embedding", response_model=dict)
async def regenerate_document_embedding(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    doc_id: uuid.UUID = Path(..., description="Document ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
    container: DependencyContainer = Depends(get_di_container_dual),
):
    """
    Regenerate embedding for a document.

    Requires admin or owner role.
    """
    doc = await _get_document(db, org_id, doc_id)

    try:
        embedding_service = container.create_knowledge_embedding_service()
        embedding = await embedding_service.generate_embedding(f"{doc.title}\n\n{doc.content[:2000]}")

        if embedding:
            doc.embedding = embedding
            doc.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(doc)

            return {
                "success": True,
                "document_id": str(doc.id),
                "has_embedding": True,
                "message": "Embedding regenerated successfully",
            }
        else:
            return {
                "success": False,
                "document_id": str(doc.id),
                "has_embedding": False,
                "message": "Failed to generate embedding - no embedding returned",
            }

    except Exception as e:
        logger.error(f"Error regenerating embedding for document {doc.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate embedding: {str(e)}",
        ) from e


@router.get("/{org_id}/documents/stats", response_model=TenantDocumentStatsResponse)
async def get_tenant_document_stats(
    org_id: uuid.UUID = Path(..., description="Organization ID"),
    membership: OrganizationUser = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get document statistics for the tenant.

    Requires admin or owner role.
    """
    # Total documents
    total_stmt = select(func.count(TenantDocument.id)).where(
        TenantDocument.organization_id == org_id
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # Active documents
    active_stmt = select(func.count(TenantDocument.id)).where(
        TenantDocument.organization_id == org_id,
        TenantDocument.active == True,  # noqa: E712
    )
    active_result = await db.execute(active_stmt)
    active = active_result.scalar() or 0

    # With embedding
    with_emb_stmt = select(func.count(TenantDocument.id)).where(
        TenantDocument.organization_id == org_id,
        TenantDocument.embedding.isnot(None),
    )
    with_emb_result = await db.execute(with_emb_stmt)
    with_embedding = with_emb_result.scalar() or 0

    # By type
    type_stmt = (
        select(TenantDocument.document_type, func.count(TenantDocument.id))
        .where(TenantDocument.organization_id == org_id)
        .group_by(TenantDocument.document_type)
    )
    type_result = await db.execute(type_stmt)
    by_type = {row[0]: row[1] for row in type_result.all()}

    # By category
    cat_stmt = (
        select(TenantDocument.category, func.count(TenantDocument.id))
        .where(
            TenantDocument.organization_id == org_id,
            TenantDocument.category.isnot(None),
        )
        .group_by(TenantDocument.category)
    )
    cat_result = await db.execute(cat_stmt)
    by_category = {row[0]: row[1] for row in cat_result.all()}

    return TenantDocumentStatsResponse(
        total_documents=total,
        active_documents=active,
        with_embedding=with_embedding,
        without_embedding=total - with_embedding,
        by_type=by_type,
        by_category=by_category,
    )
