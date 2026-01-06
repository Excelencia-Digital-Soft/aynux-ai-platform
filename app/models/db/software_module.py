"""
Software Module model for Excelencia domain.

Stores software modules/products catalog with RAG integration support.
Replaces the hardcoded _FALLBACK_MODULES in excelencia_node.py.
"""

import uuid
from enum import Enum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from .base import Base, TimestampMixin
from .schemas import EXCELENCIA_SCHEMA


class ModuleStatus(str, Enum):
    """Software module status."""

    ACTIVE = "active"
    BETA = "beta"
    DEPRECATED = "deprecated"
    COMING_SOON = "coming_soon"


class ModuleCategory(str, Enum):
    """Software module category/vertical."""

    HEALTHCARE = "healthcare"  # Salud
    HOSPITALITY = "hospitality"  # Hoteleria
    FINANCE = "finance"  # Financiero
    GUILDS = "guilds"  # Gremios
    PRODUCTS = "products"  # Productos
    PUBLIC_SERVICES = "public_services"  # Servicios publicos
    GENERAL = "general"  # General


class SoftwareModule(Base, TimestampMixin):
    """
    Software Module entity for Excelencia ERP catalog.

    Stores module information with support for:
    - Full CRUD operations via API
    - RAG integration via embedding vector
    - Multi-tenant support via organization_id
    """

    __tablename__ = "software_modules"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Module identification
    code = Column(String(20), nullable=False, unique=True, index=True)  # HC-001, TM-001
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Categorization
    category = Column(
        String(50),
        nullable=False,
        default=ModuleCategory.GENERAL.value,
        index=True,
    )
    status = Column(
        String(20),
        nullable=False,
        default=ModuleStatus.ACTIVE.value,
        index=True,
    )

    # Features and capabilities
    features = Column(ARRAY(String), default=list)  # ["Feature 1", "Feature 2"]

    # Pricing tier (for future use)
    pricing_tier = Column(String(50), default="standard")

    # Multi-tenant support (optional, for SaaS mode)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # RAG integration - embedding vector for semantic search
    # BAAI/bge-m3 via Infinity generates 1024-dimensional vectors
    embedding = Column(Vector(1024), nullable=True)
    embedding_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Sync status with company_knowledge table
    knowledge_doc_id = Column(UUID(as_uuid=True), nullable=True)
    knowledge_synced_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata for extensibility
    meta_data = Column(JSONB, default=dict)

    # Active flag for soft delete
    active = Column(Boolean, default=True, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index("idx_software_modules_code", code),
        Index("idx_software_modules_category_status", category, status),
        Index("idx_software_modules_active", active),
        Index("idx_software_modules_org", organization_id),
        # HNSW index for vector similarity search
        Index(
            "idx_software_modules_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        {"schema": EXCELENCIA_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<SoftwareModule(code='{self.code}', name='{self.name}', category='{self.category}')>"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format compatible with legacy _FALLBACK_MODULES."""
        return {
            "name": self.name,
            "description": self.description,
            "features": self.features or [],
            "target": self.category,
        }

    def to_rag_content(self) -> str:
        """Generate content string for RAG embedding."""
        raw_features: list[str] | None = self.features  # type: ignore[assignment]
        features_text = ", ".join(raw_features) if raw_features else ""
        return f"""
Módulo: {self.name}
Código: {self.code}
Categoría: {self.category}
Descripción: {self.description}
Características: {features_text}
Estado: {self.status}
""".strip()

    @classmethod
    def from_legacy_format(
        cls,
        module_id: str,
        module_data: dict[str, Any],
        organization_id: uuid.UUID | None = None,
    ) -> "SoftwareModule":
        """
        Create SoftwareModule from legacy _FALLBACK_MODULES format.

        Args:
            module_id: Module code (e.g., "HC-001")
            module_data: Dict with name, description, features, target
            organization_id: Optional organization ID for multi-tenant

        Returns:
            SoftwareModule instance
        """
        return cls(
            code=module_id,
            name=module_data.get("name", ""),
            description=module_data.get("description", ""),
            features=module_data.get("features", []),
            category=module_data.get("target", ModuleCategory.GENERAL.value),
            status=ModuleStatus.ACTIVE.value,
            organization_id=organization_id,
            active=True,
        )
