"""
Modelos de base de datos para el sistema de gestión de prompts.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Dict

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base


class Prompt(Base):
    """
    Modelo para almacenar prompts de AI.

    Soporta tanto prompts estáticos (desde archivos) como dinámicos (editables en runtime).
    """

    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    template = Column(Text, nullable=False)
    version = Column(String(50), nullable=False, default="1.0.0")
    is_active = Column(Boolean, default=True, nullable=False)
    is_dynamic = Column(Boolean, default=False, nullable=False)
    meta_data = Column(JSON, nullable=False, default=dict)

    # Use naive datetime (no timezone) to match TIMESTAMP WITHOUT TIME ZONE column
    # datetime.now(UTC).replace(tzinfo=None) gives UTC time as naive datetime
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        onupdate=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )
    created_by = Column(String(255), nullable=True)

    # Relaciones
    versions = relationship("PromptVersion", back_populates="prompt", cascade="all, delete-orphan")

    # Índices compuestos para búsquedas comunes
    __table_args__ = (
        Index("ix_prompts_key_active", "key", "is_active"),
        Index("ix_prompts_is_dynamic", "is_dynamic"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario."""
        return {
            "id": str(self.id),
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "version": self.version,
            "is_active": self.is_active,
            "is_dynamic": self.is_dynamic,
            "metadata": self.meta_data,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at is not None else None,
            "created_by": self.created_by,
        }

    def __repr__(self) -> str:
        return f"<Prompt(key='{self.key}', version='{self.version}', active={self.is_active})>"


class PromptVersion(Base):
    """
    Modelo para almacenar versiones históricas de prompts.

    Permite versionado, rollback y A/B testing de diferentes versiones de prompts.
    """

    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(50), nullable=False)
    template = Column(Text, nullable=False)
    performance_metrics = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, default=False, nullable=False)

    # Use naive datetime (no timezone) to match TIMESTAMP WITHOUT TIME ZONE column
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False)
    created_by = Column(String(255), nullable=True)

    # Metadata adicional
    notes = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=False, default=dict)

    # Relaciones
    prompt = relationship("Prompt", back_populates="versions")

    # Índices para búsquedas comunes
    __table_args__ = (
        Index("ix_prompt_versions_prompt_id", "prompt_id"),
        Index("ix_prompt_versions_version", "version"),
        Index("ix_prompt_versions_active", "is_active"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a diccionario."""
        return {
            "id": str(self.id),
            "prompt_id": str(self.prompt_id),
            "version": self.version,
            "template": self.template,
            "performance_metrics": self.performance_metrics,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,
            "created_by": self.created_by,
            "notes": self.notes,
            "metadata": self.meta_data,
        }

    def __repr__(self) -> str:
        return f"<PromptVersion(version='{self.version}', prompt_id='{self.prompt_id}', active={self.is_active})>"
