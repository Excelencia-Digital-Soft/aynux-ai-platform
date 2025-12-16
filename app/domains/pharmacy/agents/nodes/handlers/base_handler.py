"""
Base Pharmacy Handler

Abstract base class with shared utilities for pharmacy domain handlers.
Provides LLM generation, response extraction, and state formatting.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.llm import ModelComplexity, OllamaLLM, get_llm_for_task
from app.prompts.manager import PromptManager


class BasePharmacyHandler:
    """
    Base class for pharmacy domain message handlers.

    Provides shared utilities for:
    - PromptManager access (lazy initialization)
    - LLM response generation with template fallback
    - Response content extraction and cleaning
    - State update formatting
    """

    def __init__(self, prompt_manager: PromptManager | None = None):
        """
        Initialize base handler.

        Args:
            prompt_manager: PromptManager instance (creates one if not provided)
        """
        self._prompt_manager = prompt_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def prompt_manager(self) -> PromptManager:
        """Get or create PromptManager instance (lazy init)."""
        if self._prompt_manager is None:
            self._prompt_manager = PromptManager()
        return self._prompt_manager

    async def _generate_llm_response(
        self,
        template_key: str,
        variables: dict[str, Any],
        complexity: ModelComplexity = ModelComplexity.SIMPLE,
        temperature: float = 0.5,
    ) -> str | None:
        """
        Generate LLM response from template.

        Args:
            template_key: Prompt template key (e.g., "pharmacy.greeting.generate")
            variables: Template variables
            complexity: LLM complexity tier
            temperature: LLM temperature

        Returns:
            Cleaned response text or None if generation failed
        """
        try:
            prompt = await self.prompt_manager.get_prompt(template_key, variables=variables)
            llm = get_llm_for_task(complexity=complexity, temperature=temperature)
            response = await llm.ainvoke(prompt)
            return self._extract_response_content(response)
        except ValueError as e:
            self.logger.warning(f"Template not found: {template_key} - {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM generation failed: {e}")
            return None

    def _extract_response_content(self, response: Any) -> str | None:
        """
        Extract and clean content from LLM response.

        Args:
            response: LLM response object

        Returns:
            Cleaned text content or None
        """
        if not hasattr(response, "content"):
            return None

        content = response.content
        if isinstance(content, str):
            cleaned = OllamaLLM.clean_deepseek_response(content)
            return cleaned.strip()
        if isinstance(content, list):
            return " ".join(str(item) for item in content).strip()
        return None

    def _format_state_update(
        self,
        message: str,
        intent_type: str,
        workflow_step: str,
        is_complete: bool = False,
        next_agent: str = "__end__",
        state: dict[str, Any] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """
        Format standard state update dictionary.

        Args:
            message: Response message content
            intent_type: Pharmacy intent type
            workflow_step: Current workflow step
            is_complete: Whether workflow is complete
            next_agent: Next agent to route to (default: "__end__" to terminate)
            state: Current state dict (used to combine pending_greeting)
            **extra: Additional state fields

        Returns:
            Formatted state update dictionary
        """
        # Combine pending_greeting with message if present
        final_message = message
        if state and state.get("pending_greeting"):
            final_message = f"{state['pending_greeting']}\n\n{message}"

        return {
            "messages": [{"role": "assistant", "content": final_message}],
            "pharmacy_intent_type": intent_type,
            "workflow_step": workflow_step,
            "is_complete": is_complete,
            "next_agent": next_agent,
            "pending_greeting": None,  # Clear after use
            **extra,
        }
