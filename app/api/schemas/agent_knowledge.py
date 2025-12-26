"""
Agent Knowledge API Schemas

Pydantic models for agent knowledge API requests and responses.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EmbeddingStatus(str, Enum):
    """Embedding freshness status."""

    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"


class AgentKnowledgeCreate(BaseModel):
    """Schema for creating an agent knowledge document from text."""

    title: str = Field(..., min_length=3, max_length=500, description="Document title")
    content: str = Field(..., min_length=50, description="Document content (minimum 50 chars)")
    document_type: str = Field(default="general", description="Type of document")
    category: str | None = Field(default=None, description="Optional category")
    tags: list[str] = Field(default_factory=list, description="Optional tags")

    model_config = {"json_schema_extra": {"example": {"title": "Guía de uso del módulo X", "content": "Este documento explica cómo usar el módulo X. Para comenzar, debes...", "document_type": "guide", "category": "módulos", "tags": ["módulo-x", "tutorial"]}}}


class AgentKnowledgeUpdate(BaseModel):
    """Schema for updating an agent knowledge document."""

    title: str | None = Field(default=None, min_length=3, max_length=500)
    content: str | None = Field(default=None, min_length=50)
    document_type: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    active: bool | None = None


class AgentKnowledgeUpload(BaseModel):
    """Schema for file upload metadata."""

    title: str | None = Field(default=None, max_length=500, description="Optional title (defaults to filename)")
    document_type: str = Field(default="uploaded_file", description="Type of document")
    category: str | None = Field(default=None, description="Optional category")
    tags: str | None = Field(default=None, description="Comma-separated tags")


class AgentKnowledgeResponse(BaseModel):
    """Schema for agent knowledge document response."""

    id: str
    agent_key: str
    title: str
    content_preview: str = Field(description="First 200 characters of content")
    document_type: str
    category: str | None
    tags: list[str]
    has_embedding: bool
    embedding_status: EmbeddingStatus = Field(description="Embedding freshness: fresh, stale, or missing")
    embedding_updated_at: datetime | None = Field(
        default=None, description="When embedding was last generated"
    )
    active: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class AgentKnowledgeDetail(BaseModel):
    """Schema for detailed agent knowledge document response."""

    id: str
    agent_key: str
    title: str
    content: str
    document_type: str
    category: str | None
    tags: list[str]
    meta_data: dict
    has_embedding: bool
    embedding_status: EmbeddingStatus = Field(description="Embedding freshness: fresh, stale, or missing")
    embedding_updated_at: datetime | None = Field(
        default=None, description="When embedding was last generated"
    )
    active: bool
    sort_order: int
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class AgentKnowledgeSearchResult(BaseModel):
    """Schema for search result item."""

    id: str
    title: str
    content: str
    similarity_score: float = Field(description="Similarity score (0-1)")
    document_type: str
    category: str | None


class AgentKnowledgeSearchResponse(BaseModel):
    """Schema for search response."""

    query: str
    agent_key: str
    results: list[AgentKnowledgeSearchResult]
    total_results: int


class AgentKnowledgeStats(BaseModel):
    """Schema for agent knowledge statistics."""

    agent_key: str
    total_documents: int
    active_documents: int
    with_embedding: int
    embedding_coverage: float = Field(description="Percentage of documents with embeddings")


class AgentKnowledgeSearchRequest(BaseModel):
    """Schema for search request."""

    query: str = Field(..., min_length=2, description="Search query")
    max_results: int = Field(default=5, ge=1, le=20, description="Max results to return")
    min_similarity: float = Field(default=0.5, ge=0, le=1, description="Minimum similarity threshold")


class AvailableAgentsResponse(BaseModel):
    """Schema for list of available agents."""

    agents: list[str]
    total: int
