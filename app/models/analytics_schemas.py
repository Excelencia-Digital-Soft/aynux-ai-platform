"""
Analytics Schemas for Embedding Statistics and Management.

These schemas define the response models for the analytics endpoints
that provide embedding coverage metrics and missing document lists.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SourceStats(BaseModel):
    """Statistics for a single knowledge source (company or agent)."""

    total: int = Field(..., description="Total number of documents")
    with_embedding: int = Field(..., description="Documents with embeddings generated")
    without_embedding: int = Field(..., description="Documents missing embeddings")


class AgentKnowledgeStats(BaseModel):
    """Statistics for agent knowledge, including per-agent breakdown."""

    total: int = Field(..., description="Total agent knowledge documents")
    with_embedding: int = Field(..., description="Agent docs with embeddings")
    without_embedding: int = Field(..., description="Agent docs missing embeddings")
    by_agent: dict[str, SourceStats] = Field(
        default_factory=dict,
        description="Breakdown by agent_key",
    )


class EmbeddingStatsResponse(BaseModel):
    """
    Complete embedding statistics response.

    Matches the frontend EmbeddingStats interface in document.types.ts
    """

    total_documents: int = Field(..., description="Total documents across all sources")
    with_embedding: int = Field(..., description="Total documents with embeddings")
    without_embedding: int = Field(..., description="Total documents without embeddings")
    embedding_models: dict[str, int] = Field(
        default_factory=dict,
        description="Count of documents per embedding model",
    )
    avg_embedding_size: float = Field(
        default=768.0,
        description="Average embedding vector size (768 for nomic-embed-text)",
    )
    last_sync_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last embedding synchronization",
    )
    # Breakdown by source
    company_knowledge: Optional[SourceStats] = Field(
        None,
        description="Statistics for company knowledge base",
    )
    agent_knowledge: Optional[AgentKnowledgeStats] = Field(
        None,
        description="Statistics for agent knowledge bases",
    )


class MissingEmbeddingDocument(BaseModel):
    """A document that is missing its embedding."""

    id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Document title")
    document_type: str = Field(..., description="Type of document")
    source: str = Field(
        ...,
        description="Source table: 'company_knowledge' or 'agent_knowledge'",
    )
    agent_key: Optional[str] = Field(
        None,
        description="Agent key (only for agent_knowledge documents)",
    )


class MissingEmbeddingsResponse(BaseModel):
    """
    Paginated response for documents missing embeddings.

    Matches the frontend getDocumentsWithoutEmbedding response.
    """

    documents: list[MissingEmbeddingDocument] = Field(
        default_factory=list,
        description="List of documents without embeddings",
    )
    total: int = Field(..., description="Total count of documents without embeddings")
