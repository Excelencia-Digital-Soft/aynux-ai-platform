"""
LLM Integrations

AI/LLM integration services:
- Ollama LLM implementation (replaces legacy OllamaIntegration)
"""

from app.integrations.llm.ollama import (
    OllamaEmbeddingModel,
    OllamaLLM,
    create_ollama_embedder,
    create_ollama_llm,
)

__all__ = [
    # Ollama LLM (modern interface)
    "OllamaLLM",
    "OllamaEmbeddingModel",
    # Factory functions
    "create_ollama_llm",
    "create_ollama_embedder",
]

# Backward-compatible alias for migration from OllamaIntegration
OllamaIntegration = OllamaLLM
