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

Primary providers:
- vLLM: High-performance LLM inference (single model: qwen-3b)
- TEI: Text Embeddings Inference (BAAI/bge-m3, 1024 dims)
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

from .tei import (
    TEIEmbeddingModel,
    create_tei_embedder,
)
from .openai_compatible import (
    OpenAICompatibleLLM,
    create_openai_compatible_llm,
)
from .vllm import (
    VllmLLM,
    create_vllm_llm,
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
    "VllmLLM",
    "TEIEmbeddingModel",
    "OpenAICompatibleLLM",
    # Factory functions
    "create_vllm_llm",
    "create_tei_embedder",
    "create_openai_compatible_llm",
    "create_llm",
    "create_embedder",
    # Backward compatibility
    "InfinityEmbeddingModel",
    "create_infinity_embedder",
]

# Backward compatibility aliases (Infinity -> TEI)
InfinityEmbeddingModel = TEIEmbeddingModel
create_infinity_embedder = create_tei_embedder


def create_llm(provider: LLMProvider = LLMProvider.VLLM, model_name: str | None = None, **kwargs) -> ILLM:
    """
    Factory function to create LLM instance based on provider.

    Args:
        provider: LLM provider (VLLM, DEEPSEEK, OPENAI, etc.)
        model_name: Model name (optional, uses settings if not provided)
        **kwargs: Additional parameters

    Returns:
        ILLM instance

    Example:
        ```python
        from app.integrations.llm import create_llm, LLMProvider

        # Create vLLM (default, recommended)
        llm = create_llm()

        # Create vLLM with custom temperature
        llm = create_llm(
            provider=LLMProvider.VLLM,
            temperature=0.7
        )

        # Create DeepSeek LLM directly
        llm = create_llm(provider=LLMProvider.DEEPSEEK)

        # Use it
        response = await llm.generate("Hello, world!")
        ```
    """
    if provider == LLMProvider.VLLM:
        return create_vllm_llm(**kwargs)
    elif provider == LLMProvider.DEEPSEEK:
        return create_openai_compatible_llm(provider="deepseek", **kwargs)
    elif provider == LLMProvider.KIMI:
        return create_openai_compatible_llm(provider="kimi", **kwargs)
    elif provider == LLMProvider.OPENAI:
        return create_openai_compatible_llm(provider="openai", **kwargs)
    elif provider == LLMProvider.ANTHROPIC:
        raise NotImplementedError("Anthropic integration not yet implemented")
    elif provider == LLMProvider.GROQ:
        return create_openai_compatible_llm(provider="groq", **kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def create_embedder(**kwargs) -> IEmbeddingModel:
    """
    Factory function to create embedding model.

    Uses TEI with BAAI/bge-m3 (1024 dimensions) by default.

    Args:
        **kwargs: Additional parameters for TEIEmbeddingModel

    Returns:
        IEmbeddingModel instance (TEIEmbeddingModel)

    Example:
        ```python
        from app.integrations.llm import create_embedder

        # Create TEI embedder (default)
        embedder = create_embedder()

        # Use it
        embedding = await embedder.embed_text("Hello, world!")
        # Returns 1024-dimensional vector
        ```
    """
    return create_tei_embedder(**kwargs)
