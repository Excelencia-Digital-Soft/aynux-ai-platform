"""
Pydantic schemas for Knowledge Base API.

These schemas define the contract for API requests and responses,
providing automatic validation and documentation.

Following Pydantic best practices:
- Use BaseModel for all schemas
- Separate Create, Update, and Response schemas
- Use Optional for nullable fields
- Add descriptive field documentation
- Provide example values for OpenAPI docs
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Request Schemas (Input)
# ============================================================================


class KnowledgeCreate(BaseModel):
    """Schema for creating a new knowledge document."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Document title",
        examples=["Misión y Visión de Excelencia ERP"],
    )

    content: str = Field(
        ...,
        min_length=50,
        description="Document content in markdown or plain text (minimum 50 characters)",
        examples=[
            "# Misión\nNuestra misión es proporcionar soluciones tecnológicas...\n\n# Visión\nSer líderes en..."
        ],
    )

    document_type: str = Field(
        ...,
        description="Type of document",
        examples=["mission_vision"],
    )

    category: Optional[str] = Field(
        None,
        max_length=200,
        description="Secondary category for finer classification",
        examples=["valores_corporativos"],
    )

    tags: List[str] = Field(
        default_factory=list,
        description="Tags for flexible categorization",
        examples=[["misión", "visión", "valores", "corporativo"]],
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata (author, version, source, etc.)",
        examples=[{"author": "Admin", "version": "1.0", "language": "es"}],
    )

    active: bool = Field(
        default=True,
        description="Whether this document is active and searchable",
    )

    sort_order: int = Field(
        default=0,
        description="Display order (lower values appear first)",
        examples=[0],
    )

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        """Validate document_type against allowed values."""
        allowed_types = [
            "mission_vision",
            "contact_info",
            "software_catalog",
            "faq",
            "clients",
            "success_stories",
            "general",
        ]
        if v not in allowed_types:
            raise ValueError(
                f"document_type must be one of: {', '.join(allowed_types)}"
            )
        return v

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: str) -> str:
        """Validate content has minimum length for meaningful search."""
        if len(v.strip()) < 50:
            raise ValueError("Content must be at least 50 characters")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Misión y Visión de Excelencia ERP",
                "content": "# Misión\nProveer soluciones tecnológicas...\n\n# Visión\nSer líderes...",
                "document_type": "mission_vision",
                "category": "valores_corporativos",
                "tags": ["misión", "visión", "valores"],
                "metadata": {"author": "Admin", "version": "1.0"},
                "active": True,
                "sort_order": 0,
            }
        }


class KnowledgeUpdate(BaseModel):
    """Schema for updating an existing knowledge document."""

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=500,
        description="Updated title",
    )

    content: Optional[str] = Field(
        None,
        min_length=50,
        description="Updated content",
    )

    category: Optional[str] = Field(
        None,
        max_length=200,
        description="Updated category",
    )

    tags: Optional[List[str]] = Field(
        None,
        description="Updated tags (replaces existing tags)",
    )

    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated metadata (merges with existing)",
    )

    active: Optional[bool] = Field(
        None,
        description="Updated active status",
    )

    sort_order: Optional[int] = Field(
        None,
        description="Updated sort order",
    )

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate content length if provided."""
        if v is not None and len(v.strip()) < 50:
            raise ValueError("Content must be at least 50 characters")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Misión, Visión y Valores Corporativos",
                "content": "# Misión Actualizada\n...",
                "tags": ["misión", "visión", "valores", "2025"],
                "active": True,
            }
        }


class KnowledgeSearch(BaseModel):
    """Schema for knowledge search requests."""

    query: str = Field(
        ...,
        min_length=2,
        description="Search query text",
        examples=["¿Cuál es la misión de Excelencia?"],
    )

    max_results: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of results to return",
    )

    document_type: Optional[str] = Field(
        None,
        description="Filter by document type",
        examples=["mission_vision"],
    )

    category: Optional[str] = Field(
        None,
        description="Filter by category",
    )

    tags: Optional[List[str]] = Field(
        None,
        description="Filter by tags (documents with ANY of these tags)",
    )

    search_strategy: Optional[str] = Field(
        None,
        description="Search strategy: pgvector_primary, chroma_primary, or hybrid",
        examples=["hybrid"],
    )

    @field_validator("search_strategy")
    @classmethod
    def validate_search_strategy(cls, v: Optional[str]) -> Optional[str]:
        """Validate search strategy if provided."""
        if v is not None and v not in ["pgvector_primary", "chroma_primary", "hybrid"]:
            raise ValueError("search_strategy must be pgvector_primary, chroma_primary, or hybrid")
        return v


# ============================================================================
# Response Schemas (Output)
# ============================================================================


class KnowledgeResponse(BaseModel):
    """Schema for knowledge document responses."""

    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    document_type: str = Field(..., description="Document type")
    category: Optional[str] = Field(None, description="Category")
    tags: List[str] = Field(default_factory=list, description="Tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    active: bool = Field(..., description="Active status")
    sort_order: int = Field(..., description="Sort order")
    has_embedding: bool = Field(..., description="Whether document has vector embedding")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Misión y Visión de Excelencia",
                "content": "# Misión\n...",
                "document_type": "mission_vision",
                "category": "valores_corporativos",
                "tags": ["misión", "visión"],
                "metadata": {"author": "Admin"},
                "active": True,
                "sort_order": 0,
                "has_embedding": True,
                "created_at": "2025-01-20T10:00:00",
                "updated_at": "2025-01-20T10:00:00",
            }
        }


class KnowledgeSearchResult(BaseModel):
    """Schema for individual search result."""

    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Document content")
    document_type: str = Field(..., description="Document type")
    category: Optional[str] = Field(None, description="Category")
    tags: List[str] = Field(default_factory=list, description="Tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata")

    # Search-specific fields
    similarity_score: Optional[float] = Field(None, description="Vector similarity score (0.0-1.0)")
    text_rank: Optional[float] = Field(None, description="Full-text search rank")
    combined_score: Optional[float] = Field(None, description="Combined search score (hybrid)")

    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class KnowledgeSearchResponse(BaseModel):
    """Schema for search response."""

    query: str = Field(..., description="Original search query")
    results: List[KnowledgeSearchResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Number of results returned")
    search_strategy: str = Field(..., description="Search strategy used")


class KnowledgeListResponse(BaseModel):
    """Schema for paginated list response."""

    documents: List[KnowledgeResponse] = Field(..., description="List of documents")
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata",
        examples=[
            {
                "page": 1,
                "page_size": 20,
                "total_documents": 45,
                "total_pages": 3,
                "has_next": True,
                "has_prev": False,
            }
        ],
    )


class KnowledgeStats(BaseModel):
    """Schema for knowledge base statistics."""

    database: Dict[str, Any] = Field(
        ...,
        description="Database statistics",
        examples=[
            {
                "total_active": 50,
                "total_inactive": 5,
                "missing_embeddings": 2,
                "embedding_coverage": 96.0,
            }
        ],
    )
    chromadb_collections: Dict[str, int] = Field(
        ...,
        description="ChromaDB collection statistics",
        examples=[{"all_knowledge": 50, "mission_vision": 5, "faq": 20}],
    )
    embedding_model: str = Field(..., description="Embedding model name", examples=["nomic-embed-text"])


class MessageResponse(BaseModel):
    """Generic message response schema."""

    message: str = Field(..., description="Response message")
    success: bool = Field(default=True, description="Operation success status")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class ErrorResponse(BaseModel):
    """Error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    code: Optional[str] = Field(None, description="Error code")
