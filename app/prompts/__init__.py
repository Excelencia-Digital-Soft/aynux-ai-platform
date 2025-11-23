"""
Sistema de gestión centralizada de prompts para Aynux.

Este módulo proporciona una arquitectura completa para gestionar prompts de AI:
- Prompts estáticos desde archivos YAML
- Prompts dinámicos desde base de datos
- Sistema de templates con variables (Jinja2)
- Versionado y validación con Pydantic
- Caché inteligente para performance
- Registro centralizado y búsqueda

Architecture:
- PromptLoader: Carga prompts desde archivos YAML
- PromptRenderer: Renderiza templates con variables
- PromptRegistry: Registro centralizado de prompts (legacy constants)
- UnifiedPromptService: Servicio de alto nivel que integra todo
- PromptManager: Gestor de prompts con soporte de BD (legacy async)

Usage (New):
    from app.prompts import UnifiedPromptService

    service = UnifiedPromptService.get_instance()
    rendered = service.render(
        "ecommerce.sales.assistant",
        message="busco laptop",
        historial="...",
        contexto="..."
    )

Usage (Legacy):
    from app.prompts import PromptManager, PromptRegistry

    manager = PromptManager()
    prompt = await manager.get_prompt(
        PromptRegistry.PRODUCT_SEARCH,
        variables={"message": "busco laptop"}
    )
"""

# Core new system imports
from .yaml_loader import YAMLPromptLoader
from .dynamic_registry import DynamicRegistry
from .models import PromptRenderContext, PromptTemplate
from .registry import PromptRegistry
from .renderer import PromptRenderer
from .service import UnifiedPromptService

# Legacy imports (with optional dependencies)
try:
    from .db_loader import PromptLoader  # Legacy DB loader (requires SQLAlchemy)
    from .manager import PromptManager  # Legacy manager (requires async DB)
    _legacy_available = True
except ImportError:
    # If dependencies not available, create placeholder
    PromptLoader = None
    PromptManager = None
    _legacy_available = False

__all__ = [
    # New unified system
    "UnifiedPromptService",
    "YAMLPromptLoader",
    "DynamicRegistry",
    "PromptRenderer",
    "PromptTemplate",
    "PromptRenderContext",
    # Legacy components (may be None if dependencies unavailable)
    "PromptLoader",
    "PromptManager",
    "PromptRegistry",
]
