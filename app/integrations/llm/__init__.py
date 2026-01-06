"""
LLM Integrations

AI/LLM integration services:
- vLLM for high-performance LLM inference (single model: qwen-3b)
- TEI for embeddings (BAAI/bge-m3, 1024 dims)
- OpenAI-compatible API implementation (DeepSeek, KIMI, etc.)
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
    VllmLLM,
    TEIEmbeddingModel,
    OpenAICompatibleLLM,
    # Factory functions
    create_embedder,
    create_tei_embedder,
    create_llm,
    create_openai_compatible_llm,
    create_vllm_llm,
    # Backward compatibility
    InfinityEmbeddingModel,
    create_infinity_embedder,
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
    "VllmLLM",
    "TEIEmbeddingModel",
    "OpenAICompatibleLLM",
    # Factory functions
    "create_llm",
    "create_embedder",
    "create_vllm_llm",
    "create_tei_embedder",
    "create_openai_compatible_llm",
    # Model provider utilities
    "get_model_name_for_complexity",
    "get_llm_for_task",
    # Backward compatibility aliases (TEI only)
    "InfinityEmbeddingModel",
    "create_infinity_embedder",
]

# =============================================================================
# Backward Compatibility Aliases (TEI only)
# =============================================================================
# InfinityEmbeddingModel and create_infinity_embedder are imported from base.py
# as aliases to TEI (backward compatibility)
