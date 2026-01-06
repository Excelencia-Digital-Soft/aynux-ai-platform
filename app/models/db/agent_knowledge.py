# ============================================================================
# SCOPE: GLOBAL
# Description: Knowledge base per agent. Stores documents (PDF, DOCX, TXT, MD)
#              with vector embeddings for RAG-based agent responses.
# Tenant-Aware: No - Global scope (one knowledge base per agent_key)
# ============================================================================
"""
Agent Knowledge Base models for storing per-agent documents with vector embeddings.

This module contains models for storing agent-specific knowledge that is used
for RAG (Retrieval-Augmented Generation) during agent message processing.
Supports semantic search using pgvector.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA

# Document types for agent knowledge
AGENT_KNOWLEDGE_TYPES = [
    "faq",  # Frequently asked questions
    "guide",  # User guides and tutorials
    "manual",  # Technical manuals
    "policy",  # Policies and procedures
    "product_info",  # Product information
    "training",  # Training materials
    "support",  # Support documentation
    "general",  # General information
]


class AgentKnowledge(Base, TimestampMixin):
    """
    Per-agent knowledge base with vector embeddings for semantic search.

    Stores documents uploaded for specific agents to enhance their responses
    through RAG (Retrieval-Augmented Generation). Each document is associated
    with an agent_key and can be searched semantically.

    Attributes:
        id: Unique identifier
        agent_key: Agent this knowledge belongs to (e.g., "support_agent")
        title: Document title
        content: Full document content
        document_type: Type of document (faq, guide, manual, etc.)
        category: Optional secondary category
        tags: Array of tags for filtering
        meta_data: Flexible metadata (source_filename, page_count, etc.)
        embedding: 768-dimensional vector for semantic search
        search_vector: PostgreSQL TSVECTOR for full-text search
        active: Whether document is searchable
        sort_order: Display order
    """

    __tablename__ = "agent_knowledge"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique document identifier",
    )

    # Agent association (global scope - no organization_id)
    agent_key = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Agent this knowledge belongs to (e.g., 'support_agent', 'excelencia_agent')",
    )

    # Document content
    title = Column(
        String(500),
        nullable=False,
        comment="Document title",
    )

    content = Column(
        Text,
        nullable=False,
        comment="Full document content in markdown/plain text",
    )

    # Categorization
    document_type = Column(
        String(50),
        nullable=False,
        default="general",
        index=True,
        comment="Type of document (faq, guide, manual, etc.)",
    )

    category = Column(
        String(200),
        nullable=True,
        index=True,
        comment="Secondary category for finer classification",
    )

    tags = Column(
        ARRAY(String),
        default=list,
        comment="Tags for flexible categorization and filtering",
    )

    # Metadata
    meta_data = Column(
        JSONB,
        default=dict,
        comment="Flexible metadata (source_filename, page_count, author, etc.)",
    )

    # Status
    active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this document is active and searchable",
    )

    # Vector embeddings for semantic search (1024 dimensions for BAAI/bge-m3 via Infinity)
    embedding = Column(
        Vector(1024),
        nullable=True,
        comment="Vector embedding for semantic similarity search",
    )

    # Embedding timestamp for staleness detection
    embedding_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when embedding was last generated/updated",
    )

    # Full-text search
    search_vector = Column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search vector (auto-generated from title + content)",
    )

    # Sort order for display
    sort_order = Column(
        Integer,
        default=0,
        comment="Order for displaying documents (lower = first)",
    )

    def __repr__(self) -> str:
        """String representation of the agent knowledge document."""
        title_preview = self.title[:50] if self.title else "Untitled"
        return f"<AgentKnowledge(agent='{self.agent_key}', title='{title_preview}...')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "agent_key": self.agent_key,
            "title": self.title,
            "content": self.content,
            "content_preview": self.content[:200] if self.content else "",
            "document_type": self.document_type,
            "category": self.category,
            "tags": self.tags or [],
            "meta_data": self.meta_data or {},
            "active": self.active,
            "has_embedding": self.embedding is not None,
            "embedding_status": self.embedding_status,
            "embedding_updated_at": (
                self.embedding_updated_at.isoformat() if self.embedding_updated_at else None
            ),
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def has_embedding(self) -> bool:
        """Check if document has vector embedding."""
        return self.embedding is not None

    @property
    def embedding_status(self) -> str:
        """
        Determine embedding freshness status.

        Returns:
            'fresh': Embedding exists and is up-to-date
            'stale': Embedding exists but content has been updated since
            'missing': No embedding exists
        """
        if self.embedding is None:
            return "missing"
        if self.embedding_updated_at is None:
            # Legacy: embedding exists but no timestamp (treat as stale)
            return "stale"
        if self.updated_at:
            # Handle timezone-naive vs timezone-aware comparison
            updated = self.updated_at
            emb_updated = self.embedding_updated_at
            # Make both timezone-naive for comparison if one is naive
            if updated.tzinfo is None and emb_updated.tzinfo is not None:
                emb_updated = emb_updated.replace(tzinfo=None)
            elif updated.tzinfo is not None and emb_updated.tzinfo is None:
                updated = updated.replace(tzinfo=None)
            if updated > emb_updated:
                return "stale"
        return "fresh"

    @classmethod
    def create_from_upload(
        cls,
        agent_key: str,
        title: str,
        content: str,
        document_type: str = "general",
        source_filename: str | None = None,
        page_count: int | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> "AgentKnowledge":
        """Factory method to create knowledge from file upload."""
        meta_data = {}
        if source_filename:
            meta_data["source_filename"] = source_filename
        if page_count:
            meta_data["page_count"] = page_count

        return cls(
            agent_key=agent_key,
            title=title,
            content=content,
            document_type=document_type,
            category=category,
            tags=tags or [],
            meta_data=meta_data,
            active=True,
        )

    # Table-level configuration
    __table_args__ = (
        # Primary index for agent queries
        Index("idx_agent_knowledge_agent_key", agent_key),
        # Composite index for common query patterns
        Index("idx_agent_knowledge_agent_active", agent_key, active),
        Index("idx_agent_knowledge_agent_type", agent_key, document_type),
        Index("idx_agent_knowledge_type_active", document_type, active),
        # HNSW index for fast vector similarity search (requires pgvector)
        Index(
            "idx_agent_knowledge_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # GIN index for full-text search
        Index("idx_agent_knowledge_search_vector", search_vector, postgresql_using="gin"),
        # GIN index for tags array
        Index("idx_agent_knowledge_tags", tags, postgresql_using="gin"),
        {"schema": CORE_SCHEMA},
    )
