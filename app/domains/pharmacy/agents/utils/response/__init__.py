# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Pharmacy response generation module.
#              Provides LLM-driven response generation with database config.
# Tenant-Aware: Yes - each organization has its own configuration.
# ============================================================================
"""
Pharmacy Response Generation Module.

This module provides LLM-driven response generation for the pharmacy domain.
All configuration comes from the database - NO HARDCODING.

Main exports:
- PharmacyResponseGenerator: Main orchestrator class
- GeneratedResponse: Response result dataclass
- ResponseType: Response classification enum
- get_response_generator: Singleton factory function

Internal modules (for advanced usage):
- PharmacyTemplateLoader: YAML template loading
- PharmacyTemplateRenderer: Template variable substitution
- PharmacyConfigProvider: Database configuration access
- PharmacyLLMProvider: LLM instance management
"""

from .config_provider import PharmacyConfigProvider
from .generator import (
    GeneratedResponse,
    PharmacyResponseGenerator,
    ResponseType,
    get_response_generator,
)
from .llm_provider import LLMConfig, PharmacyLLMProvider
from .template_loader import LoadedTemplates, PharmacyTemplateLoader
from .template_renderer import PharmacyTemplateRenderer

__all__ = [
    # Main public API
    "GeneratedResponse",
    "PharmacyResponseGenerator",
    "ResponseType",
    "get_response_generator",
    # Template system
    "LoadedTemplates",
    "PharmacyTemplateLoader",
    "PharmacyTemplateRenderer",
    # Configuration
    "PharmacyConfigProvider",
    # LLM
    "LLMConfig",
    "PharmacyLLMProvider",
]
