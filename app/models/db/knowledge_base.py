"""
Company Knowledge Base models for storing corporate information with vector embeddings.

This module contains models for storing company information such as mission, vision,
software catalog, FAQs, client information, and success stories with semantic search
capabilities using pgvector.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, TSVECTOR, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA

# Enum for document types
DOCUMENT_TYPES = [
    "mission_vision",  # Misión, visión y valores
    "contact_info",  # Información de contacto y redes sociales
    "software_catalog",  # Catálogo de software y módulos
    "faq",  # Preguntas frecuentes
    "clients",  # Información de clientes actuales
    "success_stories",  # Casos de éxito
    "general",  # Información general
    # Support-specific document types (for RAG-based support)
    "support_faq",  # Preguntas frecuentes de soporte
    "support_guide",  # Guías de solución de problemas
    "support_contact",  # Información de contacto y escalación
    "support_training",  # Contenido de capacitación
    "support_module",  # FAQ específico por módulo
]


class CompanyKnowledge(Base, TimestampMixin):
    """
    Corporate knowledge base with vector embeddings for semantic search.

    Stores company information across different categories with support for:
    - Semantic search using pgvector (768-dimensional embeddings via nomic-embed-text)
    - Full-text search using PostgreSQL TSVECTOR
    - Flexible metadata storage
    - Tagging system for categorization
    """

    __tablename__ = "company_knowledge"

    # Primary identification
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Document content
    title = Column(String(500), nullable=False, comment="Document title")
    content = Column(Text, nullable=False, comment="Full document content in markdown/plain text")

    # Categorization
    document_type = Column(
        ENUM(*DOCUMENT_TYPES, name="document_type_enum"),
        nullable=False,
        index=True,
        comment="Type of document for categorization",
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

    # Metadata (renamed to meta_data to avoid SQLAlchemy reserved word)
    meta_data = Column(
        JSONB,
        default=dict,
        comment="Flexible metadata storage (author, source, version, etc.)",
    )

    # Status
    active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether this document is active and searchable",
    )

    # Vector embeddings for semantic search (768 dimensions for nomic-embed-text)
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

    # Sort order for display
    sort_order = Column(
        Integer,
        default=0,
        comment="Order for displaying documents (lower = first)",
    )

    def __repr__(self) -> str:
        """String representation of the knowledge document."""
        return f"<CompanyKnowledge(id={self.id}, type={self.document_type}, title='{self.title[:50]}...')>"

    # Table-level configuration
    __table_args__ = (
        # Composite index for common query patterns
        Index("idx_knowledge_type_active", document_type, active),
        Index("idx_knowledge_category", category),
        # HNSW index for fast vector similarity search (requires pgvector)
        Index(
            "idx_knowledge_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        # GIN index for full-text search
        Index("idx_knowledge_search_vector", search_vector, postgresql_using="gin"),
        # GIN index for tags array
        Index("idx_knowledge_tags", tags, postgresql_using="gin"),
        {"schema": CORE_SCHEMA},
    )
