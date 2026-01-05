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


# ============================================================================
# RAG Analytics Schemas
# ============================================================================


class RagQueryLogResponse(BaseModel):
    """Single RAG query log entry."""

    id: str = Field(..., description="Query log UUID")
    query: str = Field(..., description="The user query text")
    context_used: list[str] = Field(
        default_factory=list,
        description="Document IDs or titles used as context",
    )
    response: str = Field(..., description="The generated response")
    token_count: int = Field(default=0, description="Number of tokens used")
    latency_ms: int = Field(default=0, description="Response latency in milliseconds")
    relevance_score: Optional[float] = Field(
        None,
        description="Relevance score between 0 and 1",
    )
    user_feedback: Optional[str] = Field(
        None,
        description="User feedback: 'positive' or 'negative'",
    )
    created_at: datetime = Field(..., description="When the query was made")


class RagQueryLogsListResponse(BaseModel):
    """Paginated RAG query logs response."""

    logs: list[RagQueryLogResponse] = Field(
        default_factory=list,
        description="List of query logs",
    )
    total: int = Field(..., description="Total count of logs")


class DocumentTypeCount(BaseModel):
    """Document type with count for analytics."""

    type: str = Field(..., description="Document type name")
    count: int = Field(..., description="Number of occurrences")


class LatencyDistribution(BaseModel):
    """Latency distribution bucket."""

    range: str = Field(..., description="Latency range (e.g., '0-100ms')")
    count: int = Field(..., description="Number of queries in this range")


class RagMetricsResponse(BaseModel):
    """RAG metrics for dashboard."""

    total_queries: int = Field(..., description="Total number of queries")
    avg_latency_ms: float = Field(..., description="Average latency in milliseconds")
    avg_token_count: float = Field(..., description="Average token count per response")
    avg_relevance_score: float = Field(..., description="Average relevance score")
    positive_feedback_rate: float = Field(
        ...,
        description="Rate of positive feedback (0-1)",
    )
    queries_by_day: dict[str, int] = Field(
        default_factory=dict,
        description="Query count by day (YYYY-MM-DD: count)",
    )
    queries_by_hour: dict[str, int] = Field(
        default_factory=dict,
        description="Query count by hour (0-23: count)",
    )
    top_document_types: list[DocumentTypeCount] = Field(
        default_factory=list,
        description="Top document types used as context",
    )
    latency_distribution: list[LatencyDistribution] = Field(
        default_factory=list,
        description="Distribution of latencies by range",
    )


class TimeSeriesPoint(BaseModel):
    """Single time series data point."""

    timestamp: str = Field(..., description="ISO timestamp")
    value: float = Field(..., description="Metric value")
