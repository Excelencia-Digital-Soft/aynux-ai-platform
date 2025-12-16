# ============================================================================
# SCOPE: GLOBAL
# Description: OpenAI-compatible LLM implementation for external APIs.
#              Supports DeepSeek, KIMI, and any OpenAI-compatible API.
# Tenant-Aware: No - configuration via settings, tenant override via BaseAgent.
# ============================================================================
"""
OpenAI-compatible LLM implementation for external APIs.

Supports any OpenAI-compatible API including:
- DeepSeek (https://api.deepseek.com/v1)
- KIMI/Moonshot (https://api.moonshot.ai/v1)
- OpenAI (https://api.openai.com/v1)

Features:
- Uses langchain_openai.ChatOpenAI with configurable base_url
- LRU caching of ChatOpenAI instances
- Rate limit handling with LLMRateLimitError
- Automatic deepseek-r1 <think> tag cleaning
- Health check functionality
"""

import logging
import re
from typing import AsyncIterator, Dict, List, Optional

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config.settings import get_settings
from app.core.interfaces.llm import (
    ILLM,
    IChatLLM,
    LLMConnectionError,
    LLMError,
    LLMGenerationError,
    LLMProvider,
    LLMRateLimitError,
)
from app.integrations.llm.model_provider import ModelComplexity

logger = logging.getLogger(__name__)

# Regex pattern for cleaning deepseek-r1 think tags (shared with ollama.py)
DEEPSEEK_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


class OpenAICompatibleLLM(ILLM, IChatLLM):
    """
    OpenAI-compatible LLM implementation.

    Works with any OpenAI-compatible API:
    - DeepSeek (https://api.deepseek.com/v1)
    - KIMI/Moonshot (https://api.moonshot.ai/v1)
    - OpenAI (https://api.openai.com/v1)

    Example:
        ```python
        # Using settings (recommended)
        llm = OpenAICompatibleLLM()

        # Manual configuration
        llm = OpenAICompatibleLLM(
            provider="deepseek",
            api_key="sk-...",
            model_complex="deepseek-chat",
            model_reasoning="deepseek-reasoner",
        )

        # Generate with complexity tier
        response = await llm.generate("Hello", complexity=ModelComplexity.COMPLEX)
        ```
    """

    # Class-level cache for ChatOpenAI instances
    # Key: (base_url, model, temperature)
    _llm_cache: dict[tuple[str, str, float], ChatOpenAI] = {}

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model_complex: str | None = None,
        model_reasoning: str | None = None,
        temperature: float = 0.7,
        timeout: int | None = None,
        max_retries: int | None = None,
        **kwargs,
    ):
        """
        Initialize OpenAI-compatible LLM.

        Args:
            provider: Provider name (deepseek, kimi, openai). Uses settings if not provided.
            api_key: API key. Uses EXTERNAL_LLM_API_KEY from settings if not provided.
            base_url: Base URL. Auto-detected from provider if not provided.
            model_complex: Model for COMPLEX tier. Uses settings if not provided.
            model_reasoning: Model for REASONING tier. Uses settings if not provided.
            temperature: Default temperature for generation.
            timeout: Request timeout in seconds. Uses settings if not provided.
            max_retries: Max retries for failed requests. Uses settings if not provided.
            **kwargs: Additional arguments passed to ChatOpenAI.
        """
        self.settings = get_settings()

        self._provider = provider or self.settings.EXTERNAL_LLM_PROVIDER
        self._api_key = api_key or self.settings.EXTERNAL_LLM_API_KEY
        self._base_url = base_url or self.settings.external_llm_base_url_resolved
        self._model_complex = model_complex or self.settings.EXTERNAL_LLM_MODEL_COMPLEX
        self._model_reasoning = model_reasoning or self.settings.EXTERNAL_LLM_MODEL_REASONING
        self._temperature = temperature
        self._timeout = timeout if timeout is not None else self.settings.EXTERNAL_LLM_TIMEOUT
        self._max_retries = max_retries if max_retries is not None else self.settings.EXTERNAL_LLM_MAX_RETRIES
        self._kwargs = kwargs
        self._conversations: Dict[str, List[Dict[str, str]]] = {}

        if not self._api_key:
            raise LLMError(
                f"API key required for {self._provider}. "
                "Set EXTERNAL_LLM_API_KEY in environment or pass api_key parameter."
            )

        logger.info(
            f"Initialized OpenAICompatibleLLM: provider={self._provider}, "
            f"base_url={self._base_url}, models=complex:{self._model_complex}/reasoning:{self._model_reasoning}"
        )

    def _get_model_for_complexity(self, complexity: ModelComplexity) -> str:
        """
        Get model name based on complexity tier.

        Args:
            complexity: The complexity tier.

        Returns:
            Model name for the external API.
        """
        if complexity == ModelComplexity.REASONING:
            return self._model_reasoning
        # COMPLEX is the default for external API
        return self._model_complex

    @property
    def provider(self) -> LLMProvider:
        """Return the LLM provider enum value."""
        provider_map = {
            "deepseek": LLMProvider.DEEPSEEK,
            "kimi": LLMProvider.KIMI,
            "openai": LLMProvider.OPENAI,
        }
        return provider_map.get(self._provider, LLMProvider.DEEPSEEK)

    @property
    def model_name(self) -> str:
        """Return the default model name (COMPLEX tier)."""
        return self._model_complex

    def get_llm(
        self,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> ChatOpenAI:
        """
        Get a cached ChatOpenAI instance.

        Instances are cached by (base_url, model, temperature) to avoid
        repeated initialization.

        Args:
            complexity: Model complexity tier (COMPLEX or REASONING for external API).
            temperature: Override default temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional arguments for ChatOpenAI.

        Returns:
            Configured ChatOpenAI instance.
        """
        model = self._get_model_for_complexity(complexity)
        temp = temperature if temperature is not None else self._temperature
        cache_key = (self._base_url, model, temp)

        # Return cached instance if available
        if cache_key in OpenAICompatibleLLM._llm_cache:
            return OpenAICompatibleLLM._llm_cache[cache_key]

        # Combine kwargs from init and method call
        final_kwargs = {**self._kwargs, **kwargs}

        # Create new instance
        llm = ChatOpenAI(
            model=model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=temp,
            timeout=self._timeout,
            max_retries=self._max_retries,
            max_tokens=max_tokens,
            **final_kwargs,
        )

        # Cache the instance
        OpenAICompatibleLLM._llm_cache[cache_key] = llm
        logger.info(f"Created and cached ChatOpenAI: model={model}, temp={temp}, base_url={self._base_url}")

        return llm

    async def generate(
        self,
        prompt: str,
        *,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> str:
        """
        Generate text from a simple prompt.

        Args:
            prompt: Input text for the model.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters.

        Returns:
            Generated text.

        Raises:
            LLMConnectionError: If connection fails.
            LLMRateLimitError: If rate limit is exceeded.
            LLMGenerationError: If generation fails.
        """
        try:
            llm = self.get_llm(
                complexity=complexity,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            messages = [HumanMessage(content=prompt)]
            response = await llm.ainvoke(messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self.clean_deepseek_response(content)

        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling {self._provider} API: {e}")
            raise LLMConnectionError(f"Timeout calling {self._provider} API at {self._base_url}") from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error to {self._provider}: {e}")
            raise LLMConnectionError(f"Could not connect to {self._provider} at {self._base_url}") from e
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str or "429" in str(e):
                logger.warning(f"Rate limit exceeded for {self._provider}: {e}")
                raise LLMRateLimitError(f"Rate limit exceeded for {self._provider}: {e}") from e
            logger.error(f"Error generating text with {self._provider}: {e}")
            raise LLMGenerationError(f"Failed to generate text with {self._provider}: {e}") from e

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> str:
        """
        Generate a response in chat format.

        Args:
            messages: List of messages with format {"role": "...", "content": "..."}.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters.

        Returns:
            Generated response.

        Raises:
            LLMGenerationError: If generation fails.
        """
        try:
            llm = self.get_llm(
                complexity=complexity,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            lc_messages = [
                SystemMessage(content=msg["content"])
                if msg.get("role") == "system"
                else AIMessage(content=msg["content"])
                if msg.get("role") == "assistant"
                else HumanMessage(content=msg.get("content", ""))
                for msg in messages
            ]
            response = await llm.ainvoke(lc_messages)
            content = response.content if isinstance(response.content, str) else str(response.content)
            return self.clean_deepseek_response(content)

        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str or "429" in str(e):
                raise LLMRateLimitError(f"Rate limit exceeded for {self._provider}: {e}") from e
            logger.error(f"Error in chat generation with {self._provider}: {e}")
            raise LLMGenerationError(f"Failed to generate chat response with {self._provider}: {e}") from e

    def generate_stream(
        self,
        prompt: str,
        *,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int = 500,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Generate text in streaming mode.

        Args:
            prompt: Input text.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens.
            **kwargs: Additional parameters.

        Yields:
            Generated tokens one by one.
        """
        return self._stream_generator(prompt, complexity, temperature, max_tokens, **kwargs)

    async def _stream_generator(
        self,
        prompt: str,
        complexity: ModelComplexity,
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Internal async generator for streaming."""
        try:
            llm = self.get_llm(
                complexity=complexity,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            messages = [HumanMessage(content=prompt)]
            async for chunk in llm.astream(messages):
                yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)
        except Exception as e:
            logger.error(f"Error in streaming generation with {self._provider}: {e}")
            raise LLMGenerationError(f"Failed to stream text with {self._provider}: {e}") from e

    async def chat(
        self,
        message: str,
        conversation_id: str,
        system_prompt: Optional[str] = None,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        **kwargs,
    ) -> str:
        """
        Chat with conversation history.

        Args:
            message: User message.
            conversation_id: ID for maintaining conversation context.
            system_prompt: Optional system prompt.
            complexity: Model complexity tier.
            **kwargs: Additional parameters.

        Returns:
            Assistant response.
        """
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
            if system_prompt:
                self._conversations[conversation_id].append({"role": "system", "content": system_prompt})

        self._conversations[conversation_id].append({"role": "user", "content": message})
        response = await self.generate_chat(
            messages=self._conversations[conversation_id],
            complexity=complexity,
            **kwargs,
        )
        self._conversations[conversation_id].append({"role": "assistant", "content": response})
        return response

    async def reset_conversation(self, conversation_id: str) -> None:
        """
        Reset conversation history.

        Args:
            conversation_id: ID of the conversation to reset.
        """
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            logger.info(f"Reset conversation: {conversation_id}")

    async def health_check(self) -> bool:
        """
        Check API health by making a simple request.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            llm = self.get_llm(complexity=ModelComplexity.COMPLEX)
            # Simple ping request
            await llm.ainvoke([HumanMessage(content="ping")])
            return True
        except Exception as e:
            logger.error(f"Health check failed for {self._provider}: {e}")
            return False

    @staticmethod
    def clean_deepseek_response(response: str) -> str:
        """
        Remove deepseek-r1 <think> tags from response.

        DeepSeek reasoning models include <think>...</think> blocks with
        internal reasoning. This method removes them for cleaner output.

        Args:
            response: Raw response from the model.

        Returns:
            Cleaned response without think tags.
        """
        if not response:
            return response
        cleaned = DEEPSEEK_THINK_PATTERN.sub("", response)
        return cleaned.strip()

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate response using system and user prompts.

        This method provides compatibility with OllamaLLM interface.

        Args:
            system_prompt: System prompt for context.
            user_prompt: User prompt/question.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens to generate.

        Returns:
            Generated response.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self.generate_chat(
            messages=messages,
            complexity=complexity,
            temperature=temperature,
            max_tokens=max_tokens or 500,
        )


def create_openai_compatible_llm(
    provider: str | None = None,
    **kwargs,
) -> OpenAICompatibleLLM:
    """
    Factory function to create OpenAICompatibleLLM instance.

    Args:
        provider: Provider name (deepseek, kimi, openai).
        **kwargs: Additional parameters for OpenAICompatibleLLM.

    Returns:
        Configured OpenAICompatibleLLM instance.

    Example:
        ```python
        # Using settings
        llm = create_openai_compatible_llm()

        # Explicit provider
        llm = create_openai_compatible_llm(provider="deepseek")
        ```
    """
    return OpenAICompatibleLLM(provider=provider, **kwargs)
