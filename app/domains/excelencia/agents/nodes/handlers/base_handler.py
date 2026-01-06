"""
Base Excelencia Handler

Abstract base class with shared utilities for Excelencia domain handlers.
Provides LLM generation, response extraction, and deepseek-r1 tag cleaning.
"""

from __future__ import annotations

import logging
from typing import Any

from app.integrations.llm import ModelComplexity, VllmLLM


class BaseExcelenciaHandler:
    """
    Base class for Excelencia domain handlers.

    Provides shared utilities for:
    - LLM access with complexity tiers
    - Response content extraction and cleaning
    - deepseek-r1 <think> tag removal
    """

    def __init__(self, llm: VllmLLM | None = None):
        """
        Initialize base handler.

        Args:
            llm: VllmLLM instance (creates one if not provided)
        """
        self._llm = llm or VllmLLM()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def llm(self) -> VllmLLM:
        """Get VllmLLM instance."""
        return self._llm

    def get_llm(self, complexity: ModelComplexity, temperature: float = 0.7):
        """
        Get LLM instance with specified complexity and temperature.

        Args:
            complexity: Model complexity tier (SIMPLE, COMPLEX, etc.)
            temperature: LLM temperature for generation

        Returns:
            Configured LLM instance
        """
        return self._llm.get_llm(complexity=complexity, temperature=temperature)

    def extract_response_content(self, response: Any) -> str:
        """
        Extract and clean content from LLM response.

        Handles various response formats and cleans deepseek-r1 <think> tags.

        Args:
            response: LLM response object

        Returns:
            Cleaned text content
        """
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, str):
                result = content.strip()
            elif isinstance(content, list):
                result = " ".join(str(item) for item in content).strip()
            else:
                result = str(content).strip()
        else:
            result = str(response).strip()

        # Clean deepseek-r1 <think> tags
        return VllmLLM.clean_deepseek_response(result)
