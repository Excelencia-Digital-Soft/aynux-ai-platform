"""
Sistema de gestion centralizada de current_tasks para Aynux.

Este modulo proporciona una arquitectura para gestionar descripciones de tareas
que se envian al LLM como contexto de operacion:
- Tasks estaticos desde archivos YAML
- Sistema de templates con variables
- Cache inteligente para performance
- Soporte multi-dominio

Usage:
    from app.tasks import TaskManager, TaskRegistry

    manager = TaskManager()
    task = await manager.get_task(
        TaskRegistry.PHARMACY_IDENTIFICATION_REQUEST_DNI,
        variables={"customer_name": "Juan"}
    )
"""

from .loader import TaskLoader, TaskTemplate
from .manager import TaskManager
from .registry import TaskRegistry

__all__ = ["TaskManager", "TaskRegistry", "TaskLoader", "TaskTemplate"]
