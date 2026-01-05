# ============================================================================
# SCOPE: GLOBAL
# Description: RAG Query Log for tracking knowledge base search analytics.
#              Stores query history, latency, relevance scores, and user feedback.
# Tenant-Aware: No - Global scope (tracks all RAG queries)
# ============================================================================
"""
RAG Query Log model for persisting RAG search analytics.

This module contains the model for logging RAG queries including:
- Query text and response
- Context documents used
- Performance metrics (latency, token count)
- Quality metrics (relevance score, user feedback)
"""

import uuid

from sqlalchemy import Column, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


# Valid user feedback values
RAG_FEEDBACK_VALUES = ["positive", "negative"]


class RagQueryLog(Base, TimestampMixin):
    """
    Persistent log of RAG queries for analytics and quality tracking.

    Stores each RAG search query with its context, performance metrics,
    and optional user feedback. Used by analytics endpoints to provide
    insights into RAG system usage and quality.

    Attributes:
        id: Unique identifier
        query: User query text
        context_used: List of document titles/IDs used as context
        response: Generated response text (optional)
        token_count: Tokens used in generation
        latency_ms: Search latency in milliseconds
        relevance_score: Average relevance score (0-1)
        user_feedback: User feedback ('positive' or 'negative')
        agent_key: Agent that performed the search
    """

    __tablename__ = "rag_query_logs"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique query log identifier",
    )

    # Query content
    query = Column(
        Text,
        nullable=False,
        comment="User query text that was searched",
    )

    # Context used for response generation
    context_used = Column(
        JSONB,
        default=list,
        comment="Document titles/IDs used as RAG context",
    )

    # Response (optional - may be recorded later)
    response = Column(
        Text,
        nullable=True,
        comment="Generated response text",
    )

    # Performance metrics
    token_count = Column(
        Integer,
        default=0,
        comment="Tokens used in response generation",
    )

    latency_ms = Column(
        Float,
        default=0.0,
        comment="Search latency in milliseconds",
    )

    # Quality metrics
    relevance_score = Column(
        Float,
        nullable=True,
        comment="Average relevance score of retrieved documents (0-1)",
    )

    user_feedback = Column(
        String(20),
        nullable=True,
        comment="User feedback: 'positive' or 'negative'",
    )

    # Agent association
    agent_key = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Agent that performed the search (e.g., 'support_agent')",
    )

    def __repr__(self) -> str:
        """String representation of the RAG query log."""
        query_str = str(self.query) if self.query else "Empty"
        query_preview = query_str[:50] if len(query_str) > 50 else query_str
        return f"<RagQueryLog(agent='{self.agent_key}', query='{query_preview}...')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "query": self.query,
            "context_used": self.context_used or [],
            "response": self.response,
            "token_count": self.token_count,
            "latency_ms": self.latency_ms,
            "relevance_score": self.relevance_score,
            "user_feedback": self.user_feedback,
            "agent_key": self.agent_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def has_feedback(self) -> bool:
        """Check if user has provided feedback."""
        return self.user_feedback is not None

    @property
    def is_positive_feedback(self) -> bool:
        """Check if feedback is positive."""
        return str(self.user_feedback) == "positive"

    # Table-level configuration
    __table_args__ = (
        # Index for time-based queries (analytics dashboards)
        Index("idx_rag_query_logs_created_at", "created_at"),
        # Index for agent-specific analytics
        Index("idx_rag_query_logs_agent_key", agent_key),
        # Index for feedback analysis (only indexed when feedback exists)
        Index(
            "idx_rag_query_logs_feedback",
            user_feedback,
            postgresql_where=user_feedback.isnot(None),
        ),
        # Composite index for agent + time queries
        Index("idx_rag_query_logs_agent_created", agent_key, "created_at"),
        {"schema": CORE_SCHEMA},
    )
