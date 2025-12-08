# app/integrations/llm/model_provider.py
"""
Model Provider - Dynamic model selection based on task complexity.

Provides a tiered model system:
- SIMPLE: Fast model for intent analysis, classification (deepseek-r1:1.5b)
- COMPLEX: Powerful model for complex responses (deepseek-r1:7b)
- REASONING: Deep reasoning model for complex analysis (deepseek-r1:7b)
- SUMMARY: Fast non-reasoning model for conversation summarization (llama3.2:3b)
"""

from enum import Enum, auto
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.config.settings import get_settings


class ModelComplexity(Enum):
    """
    Defines the complexity of a task to select the appropriate LLM.

    - SIMPLE: Fast model for intent analysis, quick classifications
    - COMPLEX: Powerful model for generating detailed responses
    - REASONING: Deep reasoning model for complex multi-step analysis
    - SUMMARY: Fast non-reasoning model for conversation summarization
    """

    SIMPLE = auto()
    COMPLEX = auto()
    REASONING = auto()
    SUMMARY = auto()


@lru_cache(maxsize=4)
def get_model_name_for_complexity(complexity: ModelComplexity) -> str:
    """
    Returns the appropriate Ollama model name based on task complexity.

    Model Tier Mapping:
    - SIMPLE → OLLAMA_API_MODEL_SIMPLE (default: deepseek-r1:1.5b)
    - COMPLEX → OLLAMA_API_MODEL_COMPLEX (default: deepseek-r1:7b)
    - REASONING → OLLAMA_API_MODEL_REASONING (default: deepseek-r1:7b)
    - SUMMARY → OLLAMA_API_MODEL_SUMMARY (default: llama3.2:3b)

    Args:
        complexity: The complexity of the task (SIMPLE, COMPLEX, REASONING, or SUMMARY).

    Returns:
        The model name from settings.
    """
    settings = get_settings()

    if complexity == ModelComplexity.SIMPLE:
        return settings.OLLAMA_API_MODEL_SIMPLE

    if complexity == ModelComplexity.REASONING:
        return settings.OLLAMA_API_MODEL_REASONING

    if complexity == ModelComplexity.SUMMARY:
        return settings.OLLAMA_API_MODEL_SUMMARY

    # Default to COMPLEX model
    return settings.OLLAMA_API_MODEL_COMPLEX


def get_llm_for_task(
    complexity: ModelComplexity, temperature: float = 0.7, **kwargs
) -> BaseChatModel:
    """
    Factory function to get a configured ChatOllama instance for a specific task complexity.

    Args:
        complexity: The complexity of the task (SIMPLE or COMPLEX).
        temperature: The generation temperature.
        **kwargs: Additional arguments for the ChatOllama constructor.

    Returns:
        A configured ChatOllama instance.
    """
    settings = get_settings()
    model_name = get_model_name_for_complexity(complexity)

    return ChatOllama(
        model=model_name,
        base_url=settings.OLLAMA_API_URL,
        temperature=temperature,
        **kwargs,
    )

