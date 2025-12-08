"""
LLM Configuration

Provides LLM configuration for Ollama and other AI providers.
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
    def ollama_base_url(self) -> str:
        """Get Ollama API base URL."""
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
    knowledge_similarity_threshold: float
    knowledge_enabled: bool
    embedding_model: str


def get_llm_config() -> LLMConfig:
    """Get LLM configuration from settings."""
    settings = get_settings()
    return LLMConfig(
        model=settings.OLLAMA_API_MODEL_COMPLEX,
        model_fast=settings.OLLAMA_API_MODEL_SIMPLE,
        embedding_model=settings.OLLAMA_API_MODEL_EMBEDDING,
        api_url=settings.OLLAMA_API_URL,
    )


def get_vector_search_config() -> VectorSearchConfig:
    """Get vector search configuration from settings."""
    settings = get_settings()
    return VectorSearchConfig(
        similarity_threshold=settings.PGVECTOR_SIMILARITY_THRESHOLD,
        knowledge_similarity_threshold=settings.KNOWLEDGE_SIMILARITY_THRESHOLD,
        knowledge_enabled=settings.KNOWLEDGE_BASE_ENABLED,
        embedding_model=settings.KNOWLEDGE_EMBEDDING_MODEL,
    )


__all__ = [
    "LLMConfig",
    "VectorSearchConfig",
    "get_llm_config",
    "get_vector_search_config",
]
