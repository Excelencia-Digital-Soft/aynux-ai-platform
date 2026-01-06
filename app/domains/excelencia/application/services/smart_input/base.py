"""
Base classes for smart input interpretation.

Provides common functionality for LLM-backed interpreters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.integrations.llm import ModelComplexity, VllmLLM

if TYPE_CHECKING:
    from app.prompts import PromptManager

logger = logging.getLogger(__name__)


@dataclass
class InterpretationResult:
    """Result of input interpretation."""

    success: bool
    value: str | None = None
    confidence: float = 1.0
    method: str = "direct"  # "direct" | "llm"
    edit_request: str | None = None  # For confirmation: "description" | "priority"


class BaseInterpreter:
    """Base class for interpreters with LLM fallback pattern."""

    async def _get_prompt_from_yaml(
        self,
        prompt_manager: "PromptManager | None",
        prompt_key: str,
        variables: dict,
        fallback_prompt: str,
    ) -> str:
        """
        Get prompt from YAML template with fallback.

        Args:
            prompt_manager: PromptManager instance (can be None)
            prompt_key: Registry key for the prompt
            variables: Variables to render in the template
            fallback_prompt: Fallback prompt if YAML loading fails

        Returns:
            Rendered prompt string
        """
        if prompt_manager:
            try:
                return await prompt_manager.get_prompt(prompt_key, variables=variables)
            except Exception as e:
                logger.warning(f"Failed to load YAML prompt {prompt_key}: {e}")
        return fallback_prompt

    async def _invoke_llm(
        self,
        prompt: str,
        llm: VllmLLM,
        temperature: float = 0.1,
    ) -> str | None:
        """
        Helper to invoke LLM with standard error handling.

        Args:
            prompt: The prompt to send to the LLM
            llm: VllmLLM instance
            temperature: LLM temperature (default 0.1 for deterministic output)

        Returns:
            Cleaned response string or None on error
        """
        try:
            llm_instance = llm.get_llm(
                complexity=ModelComplexity.SIMPLE,
                temperature=temperature,
            )
            response = await llm_instance.ainvoke(prompt)
            # response.content is str but typed as Union[str, list] in Langchain
            content = str(response.content) if response.content else ""
            result = content.strip().lower()
            return VllmLLM.clean_deepseek_response(result)
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            return None
