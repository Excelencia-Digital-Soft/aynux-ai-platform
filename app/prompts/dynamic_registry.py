"""
Dynamic prompt registry for centralized access to all prompts.

This module provides a centralized registry for accessing prompts
by key, with support for domain and agent filtering.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .yaml_loader import YAMLPromptLoader, PromptLoadError
from .models import PromptTemplate

logger = logging.getLogger(__name__)


class PromptNotFoundError(Exception):
    """Raised when a requested prompt is not found."""

    pass


class DynamicRegistry:
    """
    Centralized registry for all prompt templates.

    Provides fast lookup by key and filtering capabilities.
    Follows SRP: Only responsible for storing and retrieving prompts.
    """

    def __init__(self, loader: Optional[YAMLPromptLoader] = None):
        """
        Initialize the prompt registry.

        Args:
            loader: YAMLPromptLoader instance. If None, creates a new one.
        """
        self.loader = loader or YAMLPromptLoader()
        self._prompts: Dict[str, PromptTemplate] = {}
        self._loaded = False

    def load_all(self, force_reload: bool = False) -> None:
        """
        Load all prompts from the templates directory.

        Args:
            force_reload: If True, reload even if already loaded
        """
        if self._loaded and not force_reload:
            logger.debug("Prompts already loaded, skipping")
            return

        self._prompts.clear()

        try:
            collections = self.loader.load_directory()

            for collection in collections:
                for prompt in collection.prompts:
                    if prompt.key in self._prompts:
                        logger.warning(f"Duplicate prompt key: {prompt.key} (will be overwritten)")

                    self._prompts[prompt.key] = prompt

            self._loaded = True
            logger.info(f"Loaded {len(self._prompts)} prompts into registry")

        except Exception as e:
            logger.error(f"Failed to load prompts into registry: {e}")
            raise

    def get(self, key: str, strict: bool = True) -> Optional[PromptTemplate]:
        """
        Get a prompt by key.

        Args:
            key: Prompt key (e.g., 'ecommerce.product.search')
            strict: If True, raise error if not found. If False, return None.

        Returns:
            PromptTemplate if found, None if not found and strict=False

        Raises:
            PromptNotFoundError: If prompt not found and strict=True
        """
        if not self._loaded:
            self.load_all()

        prompt = self._prompts.get(key)

        if prompt is None and strict:
            raise PromptNotFoundError(f"Prompt not found: {key}")

        return prompt

    def get_by_prefix(self, prefix: str) -> List[PromptTemplate]:
        """
        Get all prompts with keys starting with a prefix.

        Args:
            prefix: Key prefix (e.g., 'ecommerce.product')

        Returns:
            List of matching prompts
        """
        if not self._loaded:
            self.load_all()

        return [prompt for key, prompt in self._prompts.items() if key.startswith(prefix)]

    def get_by_domain(self, domain: str) -> List[PromptTemplate]:
        """
        Get all prompts for a specific domain.

        Args:
            domain: Domain name (e.g., 'ecommerce', 'credit', 'hospital')

        Returns:
            List of prompts for the domain
        """
        if not self._loaded:
            self.load_all()

        return [prompt for prompt in self._prompts.values() if prompt.metadata.domain == domain]

    def get_by_agent(self, agent: str) -> List[PromptTemplate]:
        """
        Get all prompts for a specific agent.

        Args:
            agent: Agent name (e.g., 'product', 'greeting', 'support')

        Returns:
            List of prompts for the agent
        """
        if not self._loaded:
            self.load_all()

        return [prompt for prompt in self._prompts.values() if prompt.metadata.agent == agent]

    def get_by_tag(self, tag: str) -> List[PromptTemplate]:
        """
        Get all prompts with a specific tag.

        Args:
            tag: Tag name

        Returns:
            List of prompts with the tag
        """
        if not self._loaded:
            self.load_all()

        return [prompt for prompt in self._prompts.values() if tag in prompt.metadata.tags]

    def list_all_keys(self) -> List[str]:
        """Get all registered prompt keys."""
        if not self._loaded:
            self.load_all()

        return sorted(self._prompts.keys())

    def list_domains(self) -> List[str]:
        """Get all unique domains."""
        if not self._loaded:
            self.load_all()

        domains = {prompt.metadata.domain for prompt in self._prompts.values() if prompt.metadata.domain}
        return sorted(domains)

    def list_agents(self) -> List[str]:
        """Get all unique agents."""
        if not self._loaded:
            self.load_all()

        agents = {prompt.metadata.agent for prompt in self._prompts.values() if prompt.metadata.agent}
        return sorted(agents)

    def exists(self, key: str) -> bool:
        """Check if a prompt exists."""
        if not self._loaded:
            self.load_all()

        return key in self._prompts

    def count(self) -> int:
        """Get total number of prompts."""
        if not self._loaded:
            self.load_all()

        return len(self._prompts)

    def reload(self) -> None:
        """Reload all prompts from disk."""
        self.loader.reload()
        self.load_all(force_reload=True)
        logger.info("Registry reloaded from disk")

    def get_stats(self) -> Dict[str, any]:
        """Get registry statistics."""
        if not self._loaded:
            self.load_all()

        return {
            "total_prompts": self.count(),
            "domains": len(self.list_domains()),
            "agents": len(self.list_agents()),
            "loader_cache": self.loader.get_cache_stats(),
        }
