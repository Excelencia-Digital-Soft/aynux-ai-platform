"""
TaskTemplate - Modelo de datos para templates de tareas.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskTemplate:
    """
    Representa un template de tarea con su metadata.

    Attributes:
        key: Clave unica del task (ej: pharmacy.identification.request_dni)
        name: Nombre descriptivo del task
        description: Descripcion/instruccion para el LLM
        version: Version del template
        metadata: Metadata adicional (flow, tags, etc.)
    """

    key: str
    name: str
    description: str
    version: str = "1.0.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convierte el template a diccionario."""
        return {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"<TaskTemplate(key='{self.key}', version='{self.version}')>"
