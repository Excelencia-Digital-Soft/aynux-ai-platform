"""
Document Upload API Endpoints

RESTful API for uploading documents (PDF/text) to the knowledge base.

Follows Clean Architecture:
- Uses Upload Use Cases via dependency injection
- Thin controllers, business logic in Use Cases
- Proper error handling and validation
"""

import logging
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases import (
    BatchUploadDocumentsUseCase,
    UploadPDFUseCase,
    UploadTextUseCase,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/v1/admin/documents",
    tags=["Document Upload"],
)


# ============================================================================
# Request/Response Models
# ============================================================================


class TextUploadRequest(BaseModel):
    """Request model for text upload."""

    content: str = Field(..., min_length=50, description="Text content")
    title: str = Field(..., min_length=3, description="Document title")
    document_type: str = Field(default="general", description="Document type")
    category: Optional[str] = Field(None, description="Document category")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags")
    metadata: Optional[dict] = Field(default_factory=dict, description="Metadata")


class UploadResponse(BaseModel):
    """Response model for document upload."""

    success: bool
    document_id: str
    title: str
    document_type: str
    character_count: int
    has_embedding: bool
    message: str


class BatchUploadResponse(BaseModel):
    """Response model for batch upload."""

    total: int
    successful: int
    failed: int
    results: List[Optional[dict]]
    errors: List[str]


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/upload/pdf",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF document",
    description="Upload a PDF file and extract text to knowledge base",
)
async def upload_pdf(
    file: UploadFile = File(..., description="PDF file to upload"),  # noqa: B008
    title: Optional[str] = Form(None, description="Document title (optional)"),  # noqa: B008
    document_type: str = Form("general", description="Document type"),  # noqa: B008
    category: Optional[str] = Form(None, description="Category"),  # noqa: B008
    tags: Optional[str] = Form(None, description="Comma-separated tags"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Upload a PDF document to the knowledge base.

    The PDF will be:
    1. Validated
    2. Text extracted from all pages
    3. Stored in knowledge base
    4. Embeddings generated for semantic search

    **Parameters:**
    - **file**: PDF file (required)
    - **title**: Document title (optional, extracted from PDF if not provided)
    - **document_type**: Type of document (default: "general")
    - **category**: Optional category
    - **tags**: Comma-separated tags (e.g., "product,manual,tutorial")

    **Returns:**
    - Document ID
    - Title
    - Character count
    - Embedding status
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith(".pdf"):
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

        # Parse tags
        tags_list = None
        if tags:
            tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Execute use case
        use_case = UploadPDFUseCase(db)
        result = await use_case.execute(
            pdf_bytes=pdf_bytes,
            title=title,
            document_type=document_type,
            category=category,
            tags=tags_list,
        )

        return UploadResponse(
            success=True,
            document_id=result["id"],
            title=result["title"],
            document_type=result["document_type"],
            character_count=len(result["content"]),
            has_embedding=result["has_embedding"],
            message=f"PDF uploaded successfully: {result['title']}",
        )

    except ValueError as e:
        logger.error(f"Validation error uploading PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error uploading PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload PDF: {str(e)}",
        ) from e


@router.post(
    "/upload/text",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload text document",
    description="Upload plain text or markdown content to knowledge base",
)
async def upload_text(
    request: TextUploadRequest,
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Upload text content to the knowledge base.

    The text will be:
    1. Validated (minimum 50 characters)
    2. Stored in knowledge base
    3. Embeddings generated for semantic search

    **Parameters:**
    - **content**: Text content (minimum 50 characters)
    - **title**: Document title (required)
    - **document_type**: Type of document (default: "general")
    - **category**: Optional category
    - **tags**: List of tags
    - **metadata**: Optional metadata dictionary

    **Returns:**
    - Document ID
    - Title
    - Character count
    - Embedding status
    """
    try:
        # Execute use case
        use_case = UploadTextUseCase(db)
        result = await use_case.execute(
            content=request.content,
            title=request.title,
            document_type=request.document_type,
            category=request.category,
            tags=request.tags,
            metadata=request.metadata,
        )

        return UploadResponse(
            success=True,
            document_id=result["id"],
            title=result["title"],
            document_type=result["document_type"],
            character_count=len(result["content"]),
            has_embedding=result["has_embedding"],
            message=f"Text uploaded successfully: {result['title']}",
        )

    except ValueError as e:
        logger.error(f"Validation error uploading text: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error uploading text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload text: {str(e)}",
        ) from e


@router.post(
    "/upload/batch",
    response_model=BatchUploadResponse,
    summary="Batch upload documents",
    description="Upload multiple documents (PDFs or text) in a single request",
)
async def batch_upload_documents(
    files: List[UploadFile] = File(..., description="List of files to upload"),  # noqa: B008
    document_type: str = Form("general", description="Document type for all files"),  # noqa: B008
    category: Optional[str] = Form(None, description="Category for all files"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Upload multiple documents in batch.

    Processes multiple files sequentially and returns a summary of results.

    **Parameters:**
    - **files**: List of files (PDFs or text files)
    - **document_type**: Document type for all files
    - **category**: Optional category for all files

    **Returns:**
    - Total files processed
    - Successful uploads
    - Failed uploads
    - Individual results
    - Error messages (if any)
    """
    try:
        documents = []

        for file in files:
            file_bytes = await file.read()

            # Determine file type
            if file.filename.lower().endswith(".pdf"):
                doc_type = "pdf"
            else:
                # Assume text file
                doc_type = "text"
                file_bytes = file_bytes.decode("utf-8")

            documents.append(
                {
                    "type": doc_type,
                    "content": file_bytes,
                    "title": file.filename,
                    "document_type": document_type,
                    "category": category,
                }
            )

        # Execute batch upload
        use_case = BatchUploadDocumentsUseCase(db)
        result = await use_case.execute(documents=documents)

        return BatchUploadResponse(**result)

    except Exception as e:
        logger.error(f"Error in batch upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch upload documents: {str(e)}",
        ) from e


@router.get(
    "/supported-types",
    summary="Get supported document types",
    description="Get list of supported document types for knowledge base",
)
async def get_supported_document_types():
    """
    Get list of supported document types.

    Returns available document types that can be used when uploading documents.
    """
    return {
        "document_types": [
            {
                "id": "mission_vision",
                "name": "Mission & Vision",
                "description": "Company mission, vision, and values",
            },
            {
                "id": "contact_info",
                "name": "Contact Information",
                "description": "Contact details and social networks",
            },
            {
                "id": "software_catalog",
                "name": "Software Catalog",
                "description": "Software catalog and modules",
            },
            {
                "id": "faq",
                "name": "FAQ",
                "description": "Frequently asked questions",
            },
            {
                "id": "clients",
                "name": "Clients",
                "description": "Client information",
            },
            {
                "id": "success_stories",
                "name": "Success Stories",
                "description": "Case studies and success stories",
            },
            {
                "id": "general",
                "name": "General",
                "description": "General information",
            },
        ]
    }
