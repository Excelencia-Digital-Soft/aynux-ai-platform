"""
Domain State Registry

Auto-discovers and manages domain state schemas for generic state management.
Enables OrchestrationState to handle any domain's state without hardcoding.

Each domain state module (app/domains/*/agents/state.py) should export:
- DOMAIN_KEY: str - The domain identifier (e.g., "pharmacy")
- STATE_CLASS: type - The TypedDict state class
- get_state_defaults() -> dict[str, Any] - Function returning default values
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Callable, cast

logger = logging.getLogger(__name__)


class DomainStateRegistry:
    """
    Registry for domain state schemas with auto-discovery.

    Scans app/domains/*/agents/state.py for modules that export:
    - DOMAIN_KEY: str
    - STATE_CLASS: type (TypedDict)
    - get_state_defaults(): Callable[[], dict[str, Any]]
    """

    _registry: dict[str, type] = {}
    _defaults_funcs: dict[str, Callable[[], dict[str, Any]]] = {}
    _defaults_cache: dict[str, dict[str, Any]] = {}
    _discovered: bool = False

    @classmethod
    def discover_domains(cls, force: bool = False) -> None:
        """
        Scan app/domains/*/agents/state.py for domain state modules.

        Args:
            force: Force re-discovery even if already discovered
        """
        if cls._discovered and not force:
            return

        # Find the domains directory
        domains_path = Path(__file__).parent.parent / "domains"

        if not domains_path.exists():
            logger.warning(f"Domains directory not found: {domains_path}")
            return

        # Scan each domain directory
        for domain_dir in domains_path.iterdir():
            if not domain_dir.is_dir():
                continue

            state_file = domain_dir / "agents" / "state.py"
            if not state_file.exists():
                continue

            domain_name = domain_dir.name
            module_name = f"app.domains.{domain_name}.agents.state"

            try:
                module = importlib.import_module(module_name)

                # Check for required module-level exports
                domain_key = getattr(module, "DOMAIN_KEY", None)
                state_class = getattr(module, "STATE_CLASS", None)
                defaults_func = getattr(module, "get_state_defaults", None)

                if domain_key and state_class and callable(defaults_func):
                    cls._registry[domain_key] = state_class
                    cls._defaults_funcs[domain_key] = cast(
                        Callable[[], dict[str, Any]], defaults_func
                    )
                    logger.debug(
                        f"Discovered domain state: {domain_key} -> {state_class.__name__}"
                    )
                else:
                    logger.debug(
                        f"Module {module_name} missing required exports "
                        f"(DOMAIN_KEY={domain_key}, STATE_CLASS={state_class}, "
                        f"get_state_defaults={defaults_func})"
                    )

            except ImportError as e:
                logger.debug(f"Could not import {module_name}: {e}")
            except Exception as e:
                logger.warning(f"Error discovering domain {domain_name}: {e}")

        cls._discovered = True
        logger.info(f"Domain state discovery complete. Found: {list(cls._registry.keys())}")

    @classmethod
    def register(
        cls,
        domain_key: str,
        state_class: type,
        defaults_func: Callable[[], dict[str, Any]],
    ) -> None:
        """
        Manually register a domain state class.

        Args:
            domain_key: Domain identifier (e.g., 'pharmacy')
            state_class: State TypedDict class
            defaults_func: Function returning default values
        """
        cls._registry[domain_key] = state_class
        cls._defaults_funcs[domain_key] = defaults_func
        # Invalidate cache for this domain
        cls._defaults_cache.pop(domain_key, None)
        logger.debug(f"Registered domain state: {domain_key} -> {state_class.__name__}")

    @classmethod
    def get_defaults(cls, domain_key: str) -> dict[str, Any]:
        """
        Get default state values for a domain.

        Args:
            domain_key: Domain identifier

        Returns:
            Dictionary of default values for all domain state fields
        """
        # Ensure discovery has run
        cls.discover_domains()

        # Check cache first
        if domain_key in cls._defaults_cache:
            return cls._defaults_cache[domain_key].copy()

        # Get defaults function from registry
        defaults_func = cls._defaults_funcs.get(domain_key)
        if defaults_func is None:
            logger.warning(f"No defaults function registered for domain: {domain_key}")
            return {}

        try:
            defaults = defaults_func()
            cls._defaults_cache[domain_key] = defaults
            return defaults.copy()
        except Exception as e:
            logger.error(f"Error getting defaults for domain {domain_key}: {e}")
            return {}

    @classmethod
    def get_schema(cls, domain_key: str) -> type | None:
        """
        Get the state schema class for a domain.

        Args:
            domain_key: Domain identifier

        Returns:
            The TypedDict state class, or None if not found
        """
        cls.discover_domains()
        return cls._registry.get(domain_key)

    @classmethod
    def get_registered_domains(cls) -> list[str]:
        """
        Get list of all registered domain keys.

        Returns:
            List of domain keys
        """
        cls.discover_domains()
        return list(cls._registry.keys())

    @classmethod
    def is_registered(cls, domain_key: str) -> bool:
        """
        Check if a domain is registered.

        Args:
            domain_key: Domain identifier

        Returns:
            True if domain is registered
        """
        cls.discover_domains()
        return domain_key in cls._registry

    @classmethod
    def get_field_names(cls, domain_key: str) -> list[str]:
        """
        Get list of field names for a domain state.

        Args:
            domain_key: Domain identifier

        Returns:
            List of field names from the TypedDict annotations
        """
        state_class = cls.get_schema(domain_key)
        if state_class is None:
            return []

        # Get annotations from TypedDict
        annotations = getattr(state_class, "__annotations__", {})
        return list(annotations.keys())

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the defaults cache."""
        cls._defaults_cache.clear()

    @classmethod
    def reset(cls) -> None:
        """Reset the registry completely (for testing)."""
        cls._registry.clear()
        cls._defaults_funcs.clear()
        cls._defaults_cache.clear()
        cls._discovered = False
