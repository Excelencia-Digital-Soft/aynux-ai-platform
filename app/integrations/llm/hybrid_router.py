# ============================================================================
# SCOPE: GLOBAL
# Description: Hybrid LLM Router - Routes requests to providers based on complexity.
#              COMPLEX/REASONING → External API (DeepSeek, KIMI)
#              SIMPLE/SUMMARY → Ollama local
# Tenant-Aware: No - configuration via settings, tenant override via BaseAgent.
# ============================================================================
"""
Hybrid LLM Router - Routes requests to appropriate provider based on complexity.

Routing Logic:
- COMPLEX → External API (DeepSeek, KIMI, etc.)
- REASONING → External API (DeepSeek, KIMI, etc.)
- SIMPLE → Ollama local
- SUMMARY → Ollama local

Features:
- Automatic fallback to Ollama if external API fails
- Lazy initialization of provider instances
- Singleton pattern via get_hybrid_router()
- Health check for all providers

Example:
    ```python
    from app.integrations.llm.hybrid_router import get_hybrid_router

    router = get_hybrid_router()

    # COMPLEX tier → Uses DeepSeek API
    response = await router.generate("Complex question", complexity=ModelComplexity.COMPLEX)

    # SIMPLE tier → Uses Ollama locally
    response = await router.generate("Simple question", complexity=ModelComplexity.SIMPLE)
    ```
"""

import logging
from typing import TYPE_CHECKING, AsyncIterator, Dict, List, Optional

from app.config.settings import get_settings
from app.core.interfaces.llm import (
    ILLM,
    IChatLLM,
    LLMConnectionError,
    LLMGenerationError,
    LLMProvider,
    LLMRateLimitError,
)
from app.integrations.llm.model_provider import ModelComplexity

if TYPE_CHECKING:
    from app.integrations.llm.ollama import OllamaLLM
    from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

logger = logging.getLogger(__name__)


class HybridLLMRouter(ILLM, IChatLLM):
    """
    Hybrid LLM Router - Routes to appropriate provider based on complexity tier.

    Routing Logic:
    - COMPLEX → External API (DeepSeek/KIMI)
    - REASONING → External API (DeepSeek/KIMI)
    - SIMPLE → Ollama (local)
    - SUMMARY → Ollama (local)

    Falls back to Ollama if external API is unavailable or fails.

    Attributes:
        settings: Application settings.
        _external_llm: External API provider (lazy loaded).
        _ollama_llm: Ollama provider (lazy loaded).
        _fallback_enabled: Whether to fallback to Ollama on external API failure.
        _external_available: Whether external API is currently available.
    """

    def __init__(
        self,
        external_llm: "OpenAICompatibleLLM | None" = None,
        ollama_llm: "OllamaLLM | None" = None,
        fallback_enabled: bool = True,
    ):
        """
        Initialize HybridLLMRouter.

        Args:
            external_llm: Pre-configured external LLM (optional, lazy loaded if not provided).
            ollama_llm: Pre-configured Ollama LLM (optional, lazy loaded if not provided).
            fallback_enabled: Whether to fallback to Ollama when external API fails.
        """
        self.settings = get_settings()
        self._fallback_enabled = fallback_enabled

        # Lazy initialization - instances created on first access
        self._external_llm = external_llm
        self._ollama_llm = ollama_llm

        # Track external API availability for circuit breaker pattern
        self._external_available = True

        logger.info(
            f"HybridLLMRouter initialized: "
            f"external_enabled={self.settings.EXTERNAL_LLM_ENABLED}, "
            f"provider={self.settings.EXTERNAL_LLM_PROVIDER}, "
            f"fallback={fallback_enabled}"
        )

    @property
    def external_llm(self) -> "OpenAICompatibleLLM":
        """
        Lazy load external LLM provider.

        Returns:
            OpenAICompatibleLLM instance.
        """
        if self._external_llm is None:
            from app.integrations.llm.openai_compatible import OpenAICompatibleLLM

            self._external_llm = OpenAICompatibleLLM(
                provider=self.settings.EXTERNAL_LLM_PROVIDER,
            )
        return self._external_llm

    @property
    def ollama_llm(self) -> "OllamaLLM":
        """
        Lazy load Ollama LLM provider.

        Returns:
            OllamaLLM instance.
        """
        if self._ollama_llm is None:
            from app.integrations.llm.ollama import OllamaLLM

            self._ollama_llm = OllamaLLM()
        return self._ollama_llm

    def _should_use_external(self, complexity: ModelComplexity) -> bool:
        """
        Determine if external API should be used for this complexity tier.

        Args:
            complexity: The complexity tier.

        Returns:
            True if external API should be used, False otherwise.
        """
        # External API disabled in settings
        if not self.settings.EXTERNAL_LLM_ENABLED:
            return False

        # External API unavailable and fallback not enabled
        if not self._external_available and not self._fallback_enabled:
            return False

        # Only COMPLEX and REASONING tiers use external API
        return complexity in (ModelComplexity.COMPLEX, ModelComplexity.REASONING)

    def _get_provider_for_complexity(self, complexity: ModelComplexity) -> ILLM:
        """
        Get the appropriate LLM provider for complexity tier.

        Args:
            complexity: The complexity tier.

        Returns:
            ILLM provider instance.
        """
        if self._should_use_external(complexity):
            return self.external_llm
        return self.ollama_llm

    def get_llm(
        self,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        temperature: float = 0.7,
        **kwargs,
    ):
        """
        Get ChatModel for the given complexity.

        Routes to appropriate provider based on complexity tier.

        Args:
            complexity: Model complexity tier.
            temperature: Generation temperature.
            **kwargs: Additional arguments.

        Returns:
            ChatModel instance (ChatOllama or ChatOpenAI).
        """
        provider = self._get_provider_for_complexity(complexity)
        return provider.get_llm(complexity=complexity, temperature=temperature, **kwargs)

    @property
    def provider(self) -> LLMProvider:
        """Return HYBRID as the provider type."""
        return LLMProvider.HYBRID

    @property
    def model_name(self) -> str:
        """Return descriptive model name showing both providers."""
        return f"hybrid:{self.settings.EXTERNAL_LLM_PROVIDER}+ollama"

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
        Generate text with automatic routing and fallback.

        Args:
            prompt: Input text.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens.
            **kwargs: Additional parameters.

        Returns:
            Generated text.

        Raises:
            LLMGenerationError: If generation fails and fallback is unavailable.
        """
        use_external = self._should_use_external(complexity)

        if use_external:
            try:
                return await self.external_llm.generate(
                    prompt,
                    complexity=complexity,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except (LLMConnectionError, LLMRateLimitError, LLMGenerationError) as e:
                logger.warning(
                    f"External API ({self.settings.EXTERNAL_LLM_PROVIDER}) failed: {e}. "
                    f"Falling back to Ollama with {self.settings.EXTERNAL_LLM_FALLBACK_MODEL}"
                )
                if self._fallback_enabled:
                    self._external_available = False
                    # Use fallback model for COMPLEX/REASONING on Ollama
                    return await self.ollama_llm.generate(
                        prompt,
                        complexity=complexity,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=self.settings.EXTERNAL_LLM_FALLBACK_MODEL,
                        **kwargs,
                    )
                raise

        # SIMPLE/SUMMARY tiers always use Ollama
        return await self.ollama_llm.generate(
            prompt,
            complexity=complexity,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

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
        Generate chat response with automatic routing and fallback.

        Args:
            messages: List of messages.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens.
            **kwargs: Additional parameters.

        Returns:
            Generated response.

        Raises:
            LLMGenerationError: If generation fails and fallback is unavailable.
        """
        use_external = self._should_use_external(complexity)

        if use_external:
            try:
                return await self.external_llm.generate_chat(
                    messages,
                    complexity=complexity,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            except (LLMConnectionError, LLMRateLimitError, LLMGenerationError) as e:
                logger.warning(
                    f"External API ({self.settings.EXTERNAL_LLM_PROVIDER}) failed: {e}. "
                    f"Falling back to Ollama with {self.settings.EXTERNAL_LLM_FALLBACK_MODEL}"
                )
                if self._fallback_enabled:
                    self._external_available = False
                    return await self.ollama_llm.generate_chat(
                        messages,
                        complexity=complexity,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=self.settings.EXTERNAL_LLM_FALLBACK_MODEL,
                        **kwargs,
                    )
                raise

        return await self.ollama_llm.generate_chat(
            messages,
            complexity=complexity,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

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
        Generate text in streaming mode with routing.

        Note: Streaming does not support automatic fallback mid-stream.

        Args:
            prompt: Input text.
            complexity: Model complexity tier.
            temperature: Generation temperature.
            max_tokens: Maximum tokens.
            **kwargs: Additional parameters.

        Yields:
            Generated tokens.
        """
        provider = self._get_provider_for_complexity(complexity)
        return provider.generate_stream(
            prompt,
            complexity=complexity,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def chat(
        self,
        message: str,
        conversation_id: str,
        system_prompt: Optional[str] = None,
        complexity: ModelComplexity = ModelComplexity.COMPLEX,
        **kwargs,
    ) -> str:
        """
        Chat with conversation history and routing.

        Args:
            message: User message.
            conversation_id: Conversation ID for context.
            system_prompt: Optional system prompt.
            complexity: Model complexity tier.
            **kwargs: Additional parameters.

        Returns:
            Assistant response.
        """
        provider = self._get_provider_for_complexity(complexity)
        return await provider.chat(
            message,
            conversation_id,
            system_prompt=system_prompt,
            complexity=complexity,
            **kwargs,
        )

    async def reset_conversation(self, conversation_id: str) -> None:
        """
        Reset conversation on both providers.

        Args:
            conversation_id: ID of conversation to reset.
        """
        await self.ollama_llm.reset_conversation(conversation_id)
        if self._external_llm is not None:
            await self.external_llm.reset_conversation(conversation_id)
        logger.info(f"Reset conversation on all providers: {conversation_id}")

    async def health_check(self) -> dict:
        """
        Check health of all providers.

        Returns:
            Dict with health status for each provider.
        """
        result = {
            "ollama": await self.ollama_llm.health_check(),
            "external": None,
            "external_provider": self.settings.EXTERNAL_LLM_PROVIDER,
            "external_enabled": self.settings.EXTERNAL_LLM_ENABLED,
            "external_available": self._external_available,
        }

        if self.settings.EXTERNAL_LLM_ENABLED:
            try:
                result["external"] = await self.external_llm.health_check()
                if result["external"]:
                    self._external_available = True
            except Exception as e:
                logger.error(f"External API health check failed: {e}")
                result["external"] = False
                self._external_available = False

        return result

    def reset_external_availability(self) -> None:
        """
        Reset external API availability flag.

        Call this to retry external API after it was marked unavailable
        due to previous failures.
        """
        self._external_available = True
        logger.info("Reset external API availability flag - will retry external API on next request")

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

        Provides compatibility with OllamaLLM interface.

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


# Singleton instance for the hybrid router
_hybrid_router: HybridLLMRouter | None = None


def get_hybrid_router() -> HybridLLMRouter:
    """
    Get singleton HybridLLMRouter instance.

    Returns:
        HybridLLMRouter instance.

    Example:
        ```python
        router = get_hybrid_router()
        response = await router.generate("Hello", complexity=ModelComplexity.COMPLEX)
        ```
    """
    global _hybrid_router
    if _hybrid_router is None:
        _hybrid_router = HybridLLMRouter()
    return _hybrid_router


def create_hybrid_router(
    fallback_enabled: bool = True,
    **kwargs,
) -> HybridLLMRouter:
    """
    Factory function to create new HybridLLMRouter instance.

    Unlike get_hybrid_router(), this creates a new instance each time.

    Args:
        fallback_enabled: Whether to fallback to Ollama on external API failure.
        **kwargs: Additional parameters.

    Returns:
        New HybridLLMRouter instance.
    """
    return HybridLLMRouter(fallback_enabled=fallback_enabled, **kwargs)


def reset_hybrid_router() -> None:
    """
    Reset singleton instance.

    Useful for testing or when configuration changes.
    """
    global _hybrid_router
    _hybrid_router = None
    logger.info("Reset hybrid router singleton")
