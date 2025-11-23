"""
Unified Prompt Service.

This module provides a high-level service for accessing and rendering prompts.
Integrates loader, registry, and renderer into a single convenient interface.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate

from .yaml_loader import YAMLPromptLoader
from .models import PromptRenderContext, PromptTemplate
from .renderer import PromptRenderer, PromptRenderError
from .dynamic_registry import DynamicRegistry

logger = logging.getLogger(__name__)


class UnifiedPromptService:
    """
    Unified service for loading, rendering, and managing prompts.

    This service provides a simple interface for accessing prompts from YAML files,
    rendering them with variables, and managing the prompt registry.

    Follows SRP: Coordinates between loader, registry, and renderer.
    """

    _instance: Optional["UnifiedPromptService"] = None

    def __init__(self, templates_dir: Optional[Path] = None, auto_load: bool = True):
        """
        Initialize the unified prompt service.

        Args:
            templates_dir: Directory containing YAML templates
            auto_load: Whether to automatically load all prompts on initialization
        """
        self.loader = YAMLPromptLoader(templates_dir)
        self.registry = DynamicRegistry(self.loader)
        self.renderer = PromptRenderer(strict=True)

        if auto_load:
            try:
                self.registry.load_all()
                logger.info(f"UnifiedPromptService initialized with {self.registry.count()} prompts")
            except Exception as e:
                logger.error(f"Failed to auto-load prompts: {e}")

    @classmethod
    def get_instance(cls, templates_dir: Optional[Path] = None) -> "UnifiedPromptService":
        """
        Get singleton instance of the service.

        Args:
            templates_dir: Directory containing YAML templates (only used on first call)

        Returns:
            Singleton instance of UnifiedPromptService
        """
        if cls._instance is None:
            cls._instance = cls(templates_dir=templates_dir, auto_load=True)
        return cls._instance

    def get_prompt(self, key: str, strict: bool = True) -> Optional[PromptTemplate]:
        """
        Get a prompt template by key.

        Args:
            key: Prompt key (e.g., 'ecommerce.sales.assistant')
            strict: If True, raise error if not found

        Returns:
            PromptTemplate if found, None otherwise
        """
        return self.registry.get(key, strict=strict)

    def render(
        self,
        key: str,
        context: Optional[PromptRenderContext] = None,
        strict: bool = True,
        **kwargs: Any,
    ) -> str:
        """
        Get and render a prompt in one step.

        Args:
            key: Prompt key
            context: Optional rendering context
            strict: If True, raise error if prompt not found or rendering fails
            **kwargs: Variables to render

        Returns:
            Rendered prompt string

        Raises:
            PromptNotFoundError: If prompt not found and strict=True
            PromptRenderError: If rendering fails and strict=True
        """
        prompt = self.registry.get(key, strict=strict)
        if prompt is None:
            if strict:
                raise ValueError(f"Prompt not found: {key}")
            return ""

        try:
            return self.renderer.render(prompt, context, **kwargs)
        except PromptRenderError as e:
            logger.error(f"Failed to render prompt {key}: {e}")
            if strict:
                raise
            return ""

    def render_template(self, template: PromptTemplate, **kwargs: Any) -> str:
        """
        Render a PromptTemplate directly.

        Args:
            template: PromptTemplate to render
            **kwargs: Variables to render

        Returns:
            Rendered prompt string
        """
        return self.renderer.render(template, **kwargs)

    def get_prompts_by_domain(self, domain: str) -> list[PromptTemplate]:
        """
        Get all prompts for a specific domain.

        Args:
            domain: Domain name (e.g., 'ecommerce', 'credit')

        Returns:
            List of prompts for the domain
        """
        return self.registry.get_by_domain(domain)

    def get_prompts_by_agent(self, agent: str) -> list[PromptTemplate]:
        """
        Get all prompts for a specific agent.

        Args:
            agent: Agent name (e.g., 'product', 'sales', 'support')

        Returns:
            List of prompts for the agent
        """
        return self.registry.get_by_agent(agent)

    def list_available_prompts(self) -> list[str]:
        """
        List all available prompt keys.

        Returns:
            Sorted list of prompt keys
        """
        return self.registry.list_all_keys()

    def reload(self) -> None:
        """Reload all prompts from disk."""
        self.registry.reload()
        logger.info("Prompts reloaded from disk")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.

        Returns:
            Dict with service stats
        """
        return {
            "service": "UnifiedPromptService",
            "registry": self.registry.get_stats(),
            "prompts_loaded": self.registry.count(),
            "domains": self.registry.list_domains(),
            "agents": self.registry.list_agents(),
        }

    # ============================================================================
    # Legacy compatibility methods for existing code
    # ============================================================================

    def convert_to_chat_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """
        Convert a string to a chat prompt (legacy compatibility).

        This method maintains compatibility with existing code.

        Args:
            message: Template string
            context: Variables to substitute

        Returns:
            Rendered prompt string
        """
        prompt_template = ChatPromptTemplate.from_template(message)
        return prompt_template.format(**context)

    def build_improved_prompt(self, message: str, historial: str, contexto: str) -> str:
        """
        Build sales assistant prompt (legacy compatibility).

        This method now uses the YAML-based prompt system.

        Args:
            message: User message
            historial: Conversation history
            contexto: Product context

        Returns:
            Rendered sales prompt
        """
        try:
            return self.render(
                "ecommerce.sales.assistant",
                message=message,
                historial=historial,
                contexto=contexto,
                strict=False,
            )
        except Exception as e:
            logger.warning(f"Failed to use YAML prompt, falling back to legacy: {e}")
            # Fallback to legacy hardcoded prompt if YAML not available
            return self._legacy_build_improved_prompt(message, historial, contexto)

    def orquestator_prompt(self, message: str, historial: str) -> str:
        """
        Build orchestrator prompt (legacy compatibility).

        This method now uses the YAML-based prompt system.

        Args:
            message: User message
            historial: Conversation history

        Returns:
            Rendered orchestrator prompt
        """
        try:
            return self.render(
                "shared.orchestrator.intent_detection",
                message=message,
                historial=historial,
                strict=False,
            )
        except Exception as e:
            logger.warning(f"Failed to use YAML prompt, falling back to legacy: {e}")
            return self._legacy_orquestator_prompt(message, historial)

    def _legacy_build_improved_prompt(self, message: str, historial: str, contexto: str) -> str:
        """Legacy hardcoded sales prompt (fallback only)."""
        prompt = """
        **[ROL Y PERSONA]**
        Eres 'Asistente ProVentas', un experto y amigable asistente de ventas virtual
        diseñado para interactuar vía WhatsApp.

        **[OBJETIVO PRINCIPAL]**
        Tu meta es **maximizar las ventas** y **asegurar la satisfacción del cliente**.

        **[CONTEXTO DE PRODUCTOS Y PROMOCIONES]**
        ---
        {contexto}
        ---

        **[HISTORIAL DE CONVERSACIÓN]**
        ---
        {historial}
        ---

        **[MENSAJE DE USUARIO]**
        ---
        {message}
        ---
        """
        return self.convert_to_chat_prompt(
            prompt, {"contexto": contexto, "historial": historial, "message": message}
        )

    def _legacy_orquestator_prompt(self, message: str, historial: str) -> str:
        """Legacy hardcoded orchestrator prompt (fallback only)."""
        prompt = """
        **[ROL Y PERSONA]**
        Eres un Experto en Detección de Intenciones.

        **[HISTORIAL DE CONVERSACIÓN]**
        ---
        {historial}
        ---

        **[MENSAJE DE USUARIO]**
        ---
        {message}
        ---

        Genera ÚNICAMENTE el objeto JSON con la intención detectada.
        """
        return self.convert_to_chat_prompt(prompt, {"historial": historial, "message": message})
