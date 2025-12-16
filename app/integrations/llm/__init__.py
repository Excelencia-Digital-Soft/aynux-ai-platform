"""
LLM Integrations

AI/LLM integration services:
- Ollama LLM implementation (local models)
- OpenAI-compatible API implementation (DeepSeek, KIMI, etc.)
- Hybrid Router for automatic provider selection
"""

from app.integrations.llm.base import (
    # Interfaces
    ILLM,
    IChatLLM,
    IEmbeddingModel,
    ILLMFactory,
    IStructuredLLM,
    # Enums
    LLMProvider,
    # Exceptions
    LLMConnectionError,
    LLMError,
    LLMGenerationError,
    LLMRateLimitError,
    # Implementations
    HybridLLMRouter,
    OllamaEmbeddingModel,
    OllamaLLM,
    OpenAICompatibleLLM,
    # Factory functions
    create_embedder,
    create_hybrid_router,
    create_llm,
    create_ollama_embedder,
    create_ollama_llm,
    create_openai_compatible_llm,
    get_hybrid_router,
    reset_hybrid_router,
)
from app.integrations.llm.model_provider import (
    ModelComplexity,
    get_llm_for_task,
    get_model_name_for_complexity,
)

__all__ = [
    # Interfaces
    "ILLM",
    "IChatLLM",
    "IEmbeddingModel",
    "ILLMFactory",
    "IStructuredLLM",
    # Enums
    "LLMProvider",
    "ModelComplexity",
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
    "create_llm",
    "create_embedder",
    "create_ollama_llm",
    "create_ollama_embedder",
    "create_openai_compatible_llm",
    "create_hybrid_router",
    "get_hybrid_router",
    "reset_hybrid_router",
    # Model provider utilities
    "get_model_name_for_complexity",
    "get_llm_for_task",
]

# Backward-compatible alias for migration from OllamaIntegration
OllamaIntegration = OllamaLLM
