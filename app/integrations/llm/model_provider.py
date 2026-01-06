# app/integrations/llm/model_provider.py
"""
Model Provider - Model selection for LLM tasks.

Uses a single vLLM model (qwen-3b) for all complexity tiers.
The ModelComplexity enum is preserved for backward compatibility with
existing code that passes complexity parameters.
"""

from enum import Enum, auto
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config.settings import get_settings


class ModelComplexity(Enum):
    """
    Defines the complexity of a task.

    Note: All complexity tiers now use the same model (VLLM_MODEL).
    The enum is preserved for backward compatibility with existing code.

    - SIMPLE: Fast model for intent analysis, quick classifications
    - COMPLEX: Powerful model for generating detailed responses
    - REASONING: Deep reasoning model for complex multi-step analysis
    - SUMMARY: Fast non-reasoning model for conversation summarization
    """

    SIMPLE = auto()
    COMPLEX = auto()
    REASONING = auto()
    SUMMARY = auto()


@lru_cache(maxsize=1)
def get_model_name_for_complexity(complexity: ModelComplexity) -> str:
    """
    Returns the configured vLLM model name.

    Note: All complexity tiers use the same model (VLLM_MODEL).
    The complexity parameter is ignored but preserved for backward compatibility.

    Args:
        complexity: The complexity of the task (ignored - all tiers use same model).

    Returns:
        The single configured model name from settings.
    """
    settings = get_settings()
    return settings.VLLM_MODEL


def get_llm_for_task(
    complexity: ModelComplexity, temperature: float = 0.7, **kwargs
) -> BaseChatModel:
    """
    Factory function to get a configured ChatOpenAI instance (vLLM) for a specific task complexity.

    Args:
        complexity: The complexity of the task (SIMPLE, COMPLEX, REASONING, or SUMMARY).
        temperature: The generation temperature.
        **kwargs: Additional arguments for the ChatOpenAI constructor.

    Returns:
        A configured ChatOpenAI instance connected to vLLM.
    """
    settings = get_settings()
    model_name = get_model_name_for_complexity(complexity)

    return ChatOpenAI(
        model=model_name,
        base_url=settings.VLLM_BASE_URL,
        api_key=settings.VLLM_API_KEY,
        temperature=temperature,
        timeout=settings.VLLM_REQUEST_TIMEOUT,
        max_retries=settings.VLLM_MAX_RETRIES,
        **kwargs,
    )

