"""
Sistema de gestión centralizada de prompts para Aynux.

Este módulo proporciona una arquitectura completa para gestionar prompts de AI:
- Prompts estáticos desde archivos YAML
- Prompts dinámicos desde base de datos
- Sistema de templates con variables
- Versionado y A/B testing
- Caché inteligente para performance

Usage:
    from app.prompts import PromptManager, PromptRegistry

    manager = PromptManager()
    prompt = await manager.get_prompt(
        PromptRegistry.PRODUCT_SEARCH,
        variables={"message": "busco laptop"}
    )
"""

from .manager import PromptManager
from .registry import PromptRegistry

__all__ = ["PromptManager", "PromptRegistry"]
