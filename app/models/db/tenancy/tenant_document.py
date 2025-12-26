# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Documentos de Knowledge Base aislados por organización.
#              Embeddings pgvector 768-dim + búsqueda full-text TSVECTOR.
# Tenant-Aware: Yes - organization_id es FK indexada para filtrado eficiente.
# ============================================================================
"""
TenantDocument model - Per-tenant knowledge base documents with vector embeddings.

Stores documents for each tenant's RAG system with:
- Vector embeddings for semantic search (pgvector)
- Full-text search support (TSVECTOR)
- Flexible metadata and categorization
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship

from ..base import Base, TimestampMixin
from ..schemas import CORE_SCHEMA


class TenantDocument(Base, TimestampMixin):
    """
    Knowledge base document for a tenant.

    Each tenant has isolated documents for their RAG system.
    Supports semantic search via pgvector and full-text search via TSVECTOR.

    Attributes:
        id: Unique identifier
        organization_id: FK to organizations
        title: Document title
        content: Full document content
        document_type: Type classification (faq, guide, policy, etc.)
        category: Secondary category
        tags: Flexible tags for filtering
        metadata: Additional metadata (author, source, version)
        embedding: Vector embedding (768 dimensions for nomic-embed-text)
        search_vector: Full-text search vector
        active: Whether document is active
        sort_order: Display order
    """

    __tablename__ = "tenant_documents"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique document identifier",
    )

    # Foreign key
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey(f"{CORE_SCHEMA}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Organization this document belongs to",
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
        String(100),
        nullable=False,
        index=True,
        comment="Type classification (faq, guide, policy, product_info, etc.)",
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
        nullable=False,
        comment="Flexible tags for filtering and categorization",
    )

    # Metadata
    meta_data = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Additional metadata (author, source, version, language, etc.)",
    )

    # Vector embedding for semantic search (768 dimensions for nomic-embed-text)
    embedding = Column(
        Vector(768),
        nullable=True,
        comment="Vector embedding for semantic similarity search",
    )

    # Full-text search
    search_vector = Column(
        TSVECTOR,
        nullable=True,
        comment="Full-text search vector (auto-generated from title + content)",
    )

    # Status
    active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this document is active and searchable",
    )

    # Display order
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Order for displaying documents (lower = first)",
    )

    # Relationships
    organization = relationship(
        "Organization",
        back_populates="documents",
    )

    # Table configuration
    __table_args__ = (
        # Composite indexes for common query patterns
        Index("idx_tenant_docs_org_id", organization_id),
        Index("idx_tenant_docs_org_active", organization_id, active),
        Index("idx_tenant_docs_org_type", organization_id, document_type),
        Index("idx_tenant_docs_category", category),
        # GIN index for full-text search
        Index("idx_tenant_docs_search_vector", search_vector, postgresql_using="gin"),
        # GIN index for tags array
        Index("idx_tenant_docs_tags", tags, postgresql_using="gin"),
        # Note: HNSW index for embeddings will be created per-tenant
        # via TenantIndexManager for better performance isolation
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        title_str = str(self.title)[:50] if self.title else ""
        return f"<TenantDocument(org_id='{self.organization_id}', type='{self.document_type}', title='{title_str}...')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "title": self.title,
            "content": self.content,
            "document_type": self.document_type,
            "category": self.category,
            "tags": self.tags or [],
            "meta_data": self.meta_data,
            "has_embedding": self.embedding is not None,
            "active": self.active,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_dict_with_content(self) -> dict:
        """Convert to dictionary including full content (for internal use)."""
        result = self.to_dict()
        result["content"] = self.content
        return result

    @property
    def has_embedding(self) -> bool:
        """Check if document has a vector embedding."""
        return self.embedding is not None

    @property
    def content_preview(self) -> str:
        """Get first 200 characters of content."""
        content_str = str(self.content)
        return content_str[:200] + "..." if len(content_str) > 200 else content_str

    @classmethod
    def create_from_text(
        cls,
        organization_id: uuid.UUID,
        title: str,
        content: str,
        document_type: str,
        category: str | None = None,
        tags: list[str] | None = None,
        meta_data: dict | None = None,
    ) -> "TenantDocument":
        """Factory method to create a document from text."""
        return cls(
            organization_id=organization_id,
            title=title,
            content=content,
            document_type=document_type,
            category=category,
            tags=tags or [],
            meta_data=meta_data or {},
            active=True,
        )

    @classmethod
    def create_from_pdf(
        cls,
        organization_id: uuid.UUID,
        title: str,
        content: str,
        source_filename: str,
        document_type: str = "uploaded_pdf",
        tags: list[str] | None = None,
    ) -> "TenantDocument":
        """Factory method to create a document from PDF extraction."""
        return cls(
            organization_id=organization_id,
            title=title,
            content=content,
            document_type=document_type,
            tags=tags or [],
            meta_data={
                "source": "pdf_upload",
                "source_filename": source_filename,
            },
            active=True,
        )
