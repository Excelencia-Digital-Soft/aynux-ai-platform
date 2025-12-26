"""
Base classes for smart input interpretation.

Provides common functionality for LLM-backed interpreters.
"""

import logging
from dataclasses import dataclass

from app.integrations.llm import ModelComplexity, OllamaLLM

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

    async def _invoke_llm(
        self,
        prompt: str,
        llm: OllamaLLM,
        temperature: float = 0.1,
    ) -> str | None:
        """
        Helper to invoke LLM with standard error handling.

        Args:
            prompt: The prompt to send to the LLM
            llm: OllamaLLM instance
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
            return OllamaLLM.clean_deepseek_response(result)
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            return None
