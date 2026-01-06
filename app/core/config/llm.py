"""
LLM Configuration

Provides LLM configuration for vLLM and other AI providers.
"""

from dataclasses import dataclass

from app.config.settings import get_settings


@dataclass
class LLMConfig:
    """LLM configuration settings."""

    model: str
    model_fast: str
    embedding_model: str
    api_url: str

    @property
    def llm_base_url(self) -> str:
        """Get LLM API base URL."""
        return self.api_url

    @property
    def generate_endpoint(self) -> str:
        """Get generate endpoint."""
        return f"{self.api_url}/api/generate"

    @property
    def embeddings_endpoint(self) -> str:
        """Get embeddings endpoint."""
        return f"{self.api_url}/api/embeddings"

    @property
    def chat_endpoint(self) -> str:
        """Get chat endpoint."""
        return f"{self.api_url}/api/chat"


@dataclass
class VectorSearchConfig:
    """Vector search configuration settings."""

    similarity_threshold: float
    knowledge_enabled: bool
    embedding_model: str


def get_llm_config() -> LLMConfig:
    """Get LLM configuration from settings."""
    settings = get_settings()
    return LLMConfig(
        model=settings.VLLM_MODEL,
        model_fast=settings.VLLM_MODEL,
        embedding_model=settings.TEI_MODEL,
        api_url=settings.VLLM_BASE_URL,
    )


def get_vector_search_config() -> VectorSearchConfig:
    """Get vector search configuration from settings."""
    settings = get_settings()
    return VectorSearchConfig(
        similarity_threshold=settings.PGVECTOR_SIMILARITY_THRESHOLD,
        knowledge_enabled=settings.KNOWLEDGE_BASE_ENABLED,
        embedding_model=settings.TEI_MODEL,
    )


__all__ = [
    "LLMConfig",
    "VectorSearchConfig",
    "get_llm_config",
    "get_vector_search_config",
]
