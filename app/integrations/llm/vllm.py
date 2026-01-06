# ============================================================================
# SCOPE: GLOBAL
# Description: vLLM implementation using OpenAI-compatible API.
#              Uses a single model (qwen-3b) for all complexity tiers.
# Tenant-Aware: No - configuration via settings, tenant override via BaseAgent.
# ============================================================================
"""
vLLM implementation using OpenAI-compatible API.

vLLM exposes an OpenAI-compatible endpoint at /v1/chat/completions.
Uses a single model (VLLM_MODEL) for all complexity tiers.

Features:
- Uses langchain_openai.ChatOpenAI with vLLM base_url
- LRU caching of ChatOpenAI instances by (model, temperature)
- Automatic <think> tag cleaning for reasoning-style responses
- Single model for all complexity tiers (backward compatible API)
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

# Regex pattern for cleaning deepseek-r1 think tags
DEEPSEEK_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


class VllmLLM(ILLM, IChatLLM):
    """
    vLLM implementation using OpenAI-compatible API.

    Uses a single model (VLLM_MODEL) for all complexity tiers.
    The complexity parameter is preserved for backward compatibility
    but all tiers use the same model.

    Example:
        ```python
        # Using settings (recommended)
        llm = VllmLLM()

        # Generate (complexity parameter is ignored)
        response = await llm.generate("Hello", complexity=ModelComplexity.COMPLEX)

        # Chat with history
        response = await llm.chat(
            "What's the weather?",
            conversation_id="conv-123",
            complexity=ModelComplexity.SIMPLE
        )
        ```
    """

    # Class-level cache for ChatOpenAI instances
    # Key: (base_url, model, temperature)
    _llm_cache: dict[tuple[str, str, float], ChatOpenAI] = {}

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        timeout: int | None = None,
        max_retries: int | None = None,
        **kwargs,
    ):
        """
        Initialize vLLM client.

        Args:
            base_url: vLLM API base URL. Uses VLLM_BASE_URL from settings if not provided.
            api_key: API key (typically "EMPTY" for local vLLM). Uses settings if not provided.
            model: Model name. Uses VLLM_MODEL from settings if not provided.
            temperature: Default temperature for generation.
            timeout: Request timeout in seconds. Uses settings if not provided.
            max_retries: Max retries for failed requests. Uses settings if not provided.
            **kwargs: Additional arguments passed to ChatOpenAI.
        """
        self.settings = get_settings()

        self._base_url = base_url or self.settings.VLLM_BASE_URL
        self._api_key = api_key or self.settings.VLLM_API_KEY
        self._model = model or self.settings.VLLM_MODEL
        self._temperature = temperature
        self._timeout = timeout if timeout is not None else self.settings.VLLM_REQUEST_TIMEOUT
        self._max_retries = max_retries if max_retries is not None else self.settings.VLLM_MAX_RETRIES
        self._kwargs = kwargs
        self._conversations: Dict[str, List[Dict[str, str]]] = {}

        logger.info(
            f"Initialized VllmLLM: base_url={self._base_url}, model={self._model}"
        )

    def _get_model_for_complexity(self, complexity: ModelComplexity) -> str:
        """
        Get model name.

        Note: All complexity tiers use the same model.
        The complexity parameter is ignored but preserved for backward compatibility.

        Args:
            complexity: The complexity tier (ignored).

        Returns:
            The single configured model name.
        """
        return self._model

    @property
    def provider(self) -> LLMProvider:
        """Return the LLM provider enum value."""
        return LLMProvider.VLLM

    @property
    def model_name(self) -> str:
        """Return the configured model name."""
        return self._model

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
            complexity: Model complexity tier.
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
        if cache_key in VllmLLM._llm_cache:
            return VllmLLM._llm_cache[cache_key]

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
        VllmLLM._llm_cache[cache_key] = llm
        logger.info(f"Created and cached vLLM client: model={model}, temp={temp}, base_url={self._base_url}")

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
            return self.clean_reasoning_response(content)

        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling vLLM API: {e}")
            raise LLMConnectionError(f"Timeout calling vLLM API at {self._base_url}") from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error to vLLM: {e}")
            raise LLMConnectionError(f"Could not connect to vLLM at {self._base_url}") from e
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str or "429" in str(e):
                logger.warning(f"Rate limit exceeded for vLLM: {e}")
                raise LLMRateLimitError(f"Rate limit exceeded for vLLM: {e}") from e
            logger.error(f"Error generating text with vLLM: {e}")
            raise LLMGenerationError(f"Failed to generate text with vLLM: {e}") from e

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
            return self.clean_reasoning_response(content)

        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "rate limit" in error_str or "429" in str(e):
                raise LLMRateLimitError(f"Rate limit exceeded for vLLM: {e}") from e
            logger.error(f"Error in chat generation with vLLM: {e}")
            raise LLMGenerationError(f"Failed to generate chat response with vLLM: {e}") from e

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
            logger.error(f"Error in streaming generation with vLLM: {e}")
            raise LLMGenerationError(f"Failed to stream text with vLLM: {e}") from e

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
        Check vLLM API health by making a simple request.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            # Try health endpoint first
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url.rstrip('/v1')}/health",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return True
        except Exception:
            pass

        # Fallback to model list endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    timeout=5.0,
                    headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key != "EMPTY" else {},
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed for vLLM: {e}")
            return False

    @staticmethod
    def clean_reasoning_response(response: str) -> str:
        """
        Remove reasoning model <think> tags from response.

        DeepSeek-R1 and similar reasoning models include <think>...</think>
        blocks with internal reasoning. This method removes them for cleaner output.

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

        Provides compatibility with legacy interface.

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


def create_vllm_llm(**kwargs) -> VllmLLM:
    """
    Factory function to create VllmLLM instance.

    Args:
        **kwargs: Additional parameters for VllmLLM.

    Returns:
        Configured VllmLLM instance.

    Example:
        ```python
        # Using settings (recommended)
        llm = create_vllm_llm()

        # With custom temperature
        llm = create_vllm_llm(temperature=0.5)

        # Override base URL
        llm = create_vllm_llm(base_url="http://192.168.1.100:8090/v1")
        ```
    """
    return VllmLLM(**kwargs)
