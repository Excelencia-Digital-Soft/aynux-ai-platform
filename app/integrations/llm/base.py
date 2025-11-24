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

from .ollama import (
    OllamaEmbeddingModel,
    OllamaLLM,
    create_ollama_embedder,
    create_ollama_llm,
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
    # Factory functions
    "create_ollama_llm",
    "create_ollama_embedder",
    "create_llm",
    "create_embedder",
]


def create_llm(provider: LLMProvider = LLMProvider.OLLAMA, model_name: str = None, **kwargs) -> ILLM:
    """
    Factory function to create LLM instance based on provider.

    Args:
        provider: LLM provider (OLLAMA, OPENAI, ANTHROPIC, etc.)
        model_name: Model name
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

        # Use it
        response = await llm.generate("Hello, world!")
        ```
    """
    if provider == LLMProvider.OLLAMA:
        return create_ollama_llm(model_name=model_name, **kwargs)
    elif provider == LLMProvider.OPENAI:
        # TODO: Implement OpenAI integration
        raise NotImplementedError("OpenAI integration not yet implemented")
    elif provider == LLMProvider.ANTHROPIC:
        # TODO: Implement Anthropic integration
        raise NotImplementedError("Anthropic integration not yet implemented")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def create_embedder(provider: LLMProvider = LLMProvider.OLLAMA, model_name: str = None, **kwargs) -> IEmbeddingModel:
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
