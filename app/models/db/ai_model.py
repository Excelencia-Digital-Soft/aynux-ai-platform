# ============================================================================
# SCOPE: GLOBAL
# Description: Registro global de modelos de IA disponibles. Soporta Ollama
#              (local) y proveedores externos (OpenAI, Anthropic, DeepSeek).
#              Administradores controlan qué modelos están habilitados para usuarios.
# Tenant-Aware: No - modelos disponibles globalmente, visibilidad controlada
#               por is_enabled.
# ============================================================================
"""
AIModel model - AI model registry for dynamic model management.

Stores metadata about available AI models from various providers:
- Ollama (local)
- OpenAI (external)
- Anthropic (external)
- DeepSeek (external)

Models can be synced from Ollama /api/tags or seeded manually.
Administrators control visibility via is_enabled flag.
"""

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .base import Base, TimestampMixin
from .schemas import CORE_SCHEMA


class ModelProvider(str, Enum):
    """Supported AI model providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"
    GROQ = "groq"


class ModelType(str, Enum):
    """Model capability type."""

    LLM = "llm"
    EMBEDDING = "embedding"


class AIModel(Base, TimestampMixin):
    """
    AI Model registry entry.

    Stores information about available AI models from all providers.
    Supports both local (Ollama) and external (OpenAI, Anthropic) models.

    Attributes:
        id: Unique identifier
        model_id: Provider-specific model identifier (e.g., "gpt-4", "llama3.2:3b")
        provider: Model provider (ollama, openai, anthropic, deepseek)
        model_type: Type (llm or embedding)
        display_name: Human-readable name for UI
        description: Model description
        family: Model family (e.g., "llama", "gpt", "claude")
        parameter_size: Model size (e.g., "8B", "70B", "unknown")
        context_window: Maximum context window size
        max_output_tokens: Maximum output tokens
        supports_streaming: Whether model supports streaming
        supports_functions: Whether model supports function calling
        supports_vision: Whether model supports image input
        is_enabled: Whether model is enabled for user selection
        is_default: Whether this is a default model
        sort_order: Display order in UI (lower = first)
        capabilities: Additional capabilities (JSONB)
        sync_source: How this model was added (manual, ollama_sync, seed)
    """

    __tablename__ = "ai_models"

    # Primary identification
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique model identifier",
    )

    # Model identification
    model_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Provider-specific model ID (e.g., 'gpt-4', 'llama3.2:3b')",
    )

    provider = Column(
        String(50),
        nullable=False,
        comment="Model provider: ollama, openai, anthropic, deepseek",
    )

    model_type = Column(
        String(20),
        nullable=False,
        default="llm",
        comment="Model type: llm or embedding",
    )

    # Display information
    display_name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name for UI display",
    )

    description = Column(
        Text,
        nullable=True,
        comment="Model description",
    )

    # Model specifications
    family = Column(
        String(100),
        nullable=True,
        comment="Model family (e.g., 'llama', 'gpt', 'claude')",
    )

    parameter_size = Column(
        String(50),
        nullable=True,
        comment="Model size (e.g., '8B', '70B')",
    )

    quantization_level = Column(
        String(50),
        nullable=True,
        comment="Quantization level (e.g., 'Q4_K_M', 'F16')",
    )

    context_window = Column(
        Integer,
        nullable=True,
        comment="Maximum context window in tokens",
    )

    max_output_tokens = Column(
        Integer,
        nullable=True,
        default=4096,
        comment="Maximum output tokens",
    )

    # Capabilities
    supports_streaming = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether model supports streaming responses",
    )

    supports_functions = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether model supports function/tool calling",
    )

    supports_vision = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether model supports image input",
    )

    # Status and ordering
    is_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether model is enabled for user selection",
    )

    is_default = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is a default model",
    )

    sort_order = Column(
        Integer,
        default=100,
        nullable=False,
        comment="Display order in UI (lower = first)",
    )

    # Flexible capabilities
    capabilities = Column(
        JSONB,
        default=dict,
        nullable=False,
        comment="Additional capabilities and metadata",
    )

    # Sync tracking
    sync_source = Column(
        String(50),
        default="manual",
        nullable=False,
        comment="How model was added: manual, ollama_sync, seed",
    )

    last_synced_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last sync from provider",
    )

    # Table configuration
    __table_args__ = (
        Index("idx_ai_models_provider", provider),
        Index("idx_ai_models_type", model_type),
        Index("idx_ai_models_enabled", is_enabled),
        Index("idx_ai_models_sort", sort_order),
        Index("idx_ai_models_enabled_type", is_enabled, model_type),
        {"schema": CORE_SCHEMA},
    )

    def __repr__(self) -> str:
        return f"<AIModel(model_id='{self.model_id}', provider='{self.provider}', enabled={self.is_enabled})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "model_id": self.model_id,
            "provider": self.provider,
            "model_type": self.model_type,
            "display_name": self.display_name,
            "description": self.description,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "quantization_level": self.quantization_level,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supports_streaming": self.supports_streaming,
            "supports_functions": self.supports_functions,
            "supports_vision": self.supports_vision,
            "is_enabled": self.is_enabled,
            "is_default": self.is_default,
            "sort_order": self.sort_order,
            "capabilities": self.capabilities,
            "sync_source": self.sync_source,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_select_option(self) -> dict:
        """Convert to option format for UI Select components."""
        return {
            "value": self.model_id,
            "label": self.display_name,
            "provider": self.provider,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "supports_functions": self.supports_functions,
            "supports_vision": self.supports_vision,
            "max_tokens": self.max_output_tokens,
            "is_default": self.is_default,
        }

    @classmethod
    def from_ollama_model(cls, ollama_data: dict) -> "AIModel":
        """
        Factory method to create AIModel from Ollama /api/tags response.

        Args:
            ollama_data: Single model entry from Ollama /api/tags response

        Returns:
            New AIModel instance (not saved to DB)
        """
        name = ollama_data.get("name", "")
        details = ollama_data.get("details", {})
        family = details.get("family", "")

        # Classify model type
        model_type = "embedding" if (
            "bert" in family.lower() or "embed" in name.lower()
        ) else "llm"

        # Generate display name: "llama3.2:3b" -> "Llama 3.2 (3B)"
        base_name = name.split(":")[0]
        size = details.get("parameter_size", "")
        display_name = base_name.replace("-", " ").replace(".", " ").title()
        if size:
            display_name += f" ({size})"

        return cls(
            model_id=name,
            provider="ollama",
            model_type=model_type,
            display_name=display_name,
            family=family,
            parameter_size=size,
            quantization_level=details.get("quantization_level"),
            supports_streaming=True,
            is_enabled=False,  # New models disabled by default
            sync_source="ollama_sync",
            last_synced_at=datetime.now(UTC),
            capabilities={
                "families": details.get("families", []),
            },
        )
