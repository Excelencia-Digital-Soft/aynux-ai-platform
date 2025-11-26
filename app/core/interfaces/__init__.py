"""
Core Interfaces Module

This module provides all abstract interfaces (ports) for the application.
Following the Dependency Inversion Principle, high-level modules depend
on these abstractions rather than concrete implementations.
"""

# Repository interfaces
from app.core.interfaces.repository import (
    ICacheRepository,
    IKnowledgeRepository,
    IReadOnlyRepository,
    IRepository,
    ISearchableRepository,
)

# LLM interfaces
from app.core.interfaces.llm import (
    IChatLLM,
    IEmbeddingModel,
    ILLM,
    ILLMFactory,
    IStructuredLLM,
    LLMConnectionError,
    LLMError,
    LLMGenerationError,
    LLMProvider,
    LLMRateLimitError,
)

# Vector store interfaces
from app.core.interfaces.vector_store import (
    Document,
    IHybridSearch,
    IVectorStore,
    IVectorStoreFactory,
    IVectorStoreMetrics,
    VectorSearchResult,
    VectorStoreConnectionError,
    VectorStoreError,
    VectorStoreIndexError,
    VectorStoreQueryError,
    VectorStoreType,
)

# Cache interfaces
from app.core.interfaces.cache import (
    CacheBackend,
    CacheConnectionError,
    CacheEntry,
    CacheError,
    CacheKeyError,
    CacheSerializationError,
    IAdvancedCache,
    ICache,
    ICacheMetrics,
    ICacheWithCallback,
    IMultiLayerCache,
    IPatternCache,
)

# Agent interfaces
from app.core.interfaces.agent import (
    AgentError,
    AgentExecutionError,
    AgentStatus,
    AgentTimeoutError,
    AgentType,
    AgentValidationError,
    IAgent,
    IConversationalAgent,
    ISupervisorAgent,
)

__all__ = [
    # Repository
    "IRepository",
    "IReadOnlyRepository",
    "ISearchableRepository",
    "IKnowledgeRepository",
    "ICacheRepository",
    # LLM
    "ILLM",
    "IEmbeddingModel",
    "IChatLLM",
    "IStructuredLLM",
    "ILLMFactory",
    "LLMProvider",
    "LLMError",
    "LLMConnectionError",
    "LLMGenerationError",
    "LLMRateLimitError",
    # Vector Store
    "IVectorStore",
    "IHybridSearch",
    "IVectorStoreMetrics",
    "IVectorStoreFactory",
    "Document",
    "VectorSearchResult",
    "VectorStoreType",
    "VectorStoreError",
    "VectorStoreConnectionError",
    "VectorStoreIndexError",
    "VectorStoreQueryError",
    # Cache
    "ICache",
    "IAdvancedCache",
    "IPatternCache",
    "ICacheWithCallback",
    "IMultiLayerCache",
    "ICacheMetrics",
    "CacheBackend",
    "CacheEntry",
    "CacheError",
    "CacheConnectionError",
    "CacheSerializationError",
    "CacheKeyError",
    # Agent
    "IAgent",
    "ISupervisorAgent",
    "IConversationalAgent",
    "AgentType",
    "AgentStatus",
    "AgentError",
    "AgentExecutionError",
    "AgentValidationError",
    "AgentTimeoutError",
]
