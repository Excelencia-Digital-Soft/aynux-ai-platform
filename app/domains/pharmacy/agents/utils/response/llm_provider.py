# ============================================================================
# SCOPE: MULTI-TENANT
# Description: LLM provider for pharmacy domain response generation.
#              Handles LLM configuration and instance management.
# Tenant-Aware: Yes - LLM generates tenant-specific responses.
# ============================================================================
"""
Pharmacy LLM Provider - LLM configuration and instance management.

Responsibilities:
- Configure LLM parameters (temperature, max_tokens, timeout)
- Provide LLM instance for response generation
- Handle LLM invocation with timeout
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.integrations.llm import ModelComplexity, get_llm_for_task

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


@dataclass
class LLMConfig:
    """Configuration for pharmacy LLM responses."""

    timeout_seconds: float = 60.0
    temperature: float = 0.7
    max_tokens: int = 500
    complexity: ModelComplexity = field(default=ModelComplexity.COMPLEX)


class PharmacyLLMProvider:
    """
    Provides configured LLM instance for pharmacy domain.

    Single Responsibility: LLM configuration and instance management.
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        """
        Initialize LLM provider.

        Args:
            config: LLM configuration. Uses defaults if not provided.
        """
        self._config = config or LLMConfig()
        self._llm: BaseChatModel | None = None

    @property
    def config(self) -> LLMConfig:
        """Get current LLM configuration."""
        return self._config

    def get_llm(self) -> BaseChatModel:
        """
        Get or create LLM instance.

        Returns:
            Configured LLM instance
        """
        if self._llm is None:
            self._llm = get_llm_for_task(
                complexity=self._config.complexity,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )
        return self._llm

    async def invoke(
        self,
        messages: list[tuple[str, str]],
        timeout: float | None = None,
    ) -> Any:
        """
        Invoke LLM with messages and timeout.

        Args:
            messages: List of (role, content) tuples
            timeout: Optional timeout override

        Returns:
            LLM response object

        Raises:
            asyncio.TimeoutError: If LLM times out
        """
        llm = self.get_llm()
        effective_timeout = timeout or self._config.timeout_seconds

        return await asyncio.wait_for(
            llm.ainvoke(messages),
            timeout=effective_timeout,
        )


__all__ = ["LLMConfig", "PharmacyLLMProvider"]
