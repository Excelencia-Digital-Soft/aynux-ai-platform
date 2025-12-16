# ============================================================================
# SCOPE: GLOBAL
# Description: Módulo base de LLM con interfaces y factories. Singleton compartido.
# Tenant-Aware: No - provee instancias globales. Configuración por tenant via
#              TenantDependencyContainer.get_llm().
# ============================================================================
"""
Base LLM module - Exports interfaces and factory functions

This module provides a convenient way to import LLM-related interfaces
and create LLM instances without knowing implementation details.
"""

from app.core.interfaces.llm import (  # Interfaces; Enums; Exceptions
    ILLM,
    IChatLLM,
    IEmbeddingModel,
    ILLMFactory,
    IStructuredLLM,
    LLMConnectionError,
    LLMError,
    LLMGenerationError,
    LLMProvider,
    LLMRateLimitError,
)

from .hybrid_router import (
    HybridLLMRouter,
    create_hybrid_router,
    get_hybrid_router,
    reset_hybrid_router,
)
from .ollama import (
    OllamaEmbeddingModel,
    OllamaLLM,
    create_ollama_embedder,
    create_ollama_llm,
)
from .openai_compatible import (
    OpenAICompatibleLLM,
    create_openai_compatible_llm,
)

__all__ = [
    # Interfaces
    "ILLM",
    "IEmbeddingModel",
    "IChatLLM",
    "IStructuredLLM",
    "ILLMFactory",
    # Enums
    "LLMProvider",
    # Exceptions
    "LLMError",
    "LLMConnectionError",
    "LLMGenerationError",
    "LLMRateLimitError",
    # Implementations
    "OllamaLLM",
    "OllamaEmbeddingModel",
    "OpenAICompatibleLLM",
    "HybridLLMRouter",
    # Factory functions
    "create_ollama_llm",
    "create_ollama_embedder",
    "create_openai_compatible_llm",
    "create_hybrid_router",
    "get_hybrid_router",
    "reset_hybrid_router",
    "create_llm",
    "create_embedder",
]


def create_llm(provider: LLMProvider = LLMProvider.OLLAMA, model_name: str | None = None, **kwargs) -> ILLM:
    """
    Factory function to create LLM instance based on provider.

    Args:
        provider: LLM provider (OLLAMA, HYBRID, DEEPSEEK, OPENAI, etc.)
        model_name: Model name (optional, uses settings if not provided)
        **kwargs: Additional parameters

    Returns:
        ILLM instance

    Example:
        ```python
        from app.integrations.llm import create_llm, LLMProvider

        # Create Ollama LLM
        llm = create_llm(
            provider=LLMProvider.OLLAMA,
            model_name="deepseek-r1:7b",
            temperature=0.7
        )

        # Create Hybrid Router (routes COMPLEX/REASONING to external, SIMPLE/SUMMARY to Ollama)
        llm = create_llm(provider=LLMProvider.HYBRID)

        # Create DeepSeek LLM directly
        llm = create_llm(provider=LLMProvider.DEEPSEEK)

        # Use it
        response = await llm.generate("Hello, world!")
        ```
    """
    if provider == LLMProvider.OLLAMA:
        return create_ollama_llm(model_name=model_name, **kwargs)
    elif provider == LLMProvider.HYBRID:
        return create_hybrid_router(**kwargs)
    elif provider == LLMProvider.DEEPSEEK:
        return create_openai_compatible_llm(provider="deepseek", **kwargs)
    elif provider == LLMProvider.KIMI:
        return create_openai_compatible_llm(provider="kimi", **kwargs)
    elif provider == LLMProvider.OPENAI:
        return create_openai_compatible_llm(provider="openai", **kwargs)
    elif provider == LLMProvider.ANTHROPIC:
        # TODO: Implement Anthropic integration (not OpenAI-compatible)
        raise NotImplementedError("Anthropic integration not yet implemented")
    elif provider == LLMProvider.GROQ:
        # Groq is OpenAI-compatible
        return create_openai_compatible_llm(provider="groq", **kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def create_embedder(provider: LLMProvider = LLMProvider.OLLAMA, model_name: str | None = None, **kwargs) -> IEmbeddingModel:
    """
    Factory function to create embedding model based on provider.

    Args:
        provider: LLM provider
        model_name: Embedding model name
        **kwargs: Additional parameters

    Returns:
        IEmbeddingModel instance

    Example:
        ```python
        from app.integrations.llm import create_embedder, LLMProvider

        # Create Ollama embedder
        embedder = create_embedder(
            provider=LLMProvider.OLLAMA,
            model_name="nomic-embed-text:v1.5"
        )

        # Use it
        embedding = await embedder.embed_text("Hello, world!")
        ```
    """
    if provider == LLMProvider.OLLAMA:
        return create_ollama_embedder(model_name=model_name, **kwargs)
    elif provider == LLMProvider.OPENAI:
        # TODO: Implement OpenAI embeddings
        raise NotImplementedError("OpenAI embeddings not yet implemented")
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
