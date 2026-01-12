"""
TaskLoader - Cargador de tasks desde archivos YAML.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from .models import TaskTemplate
from .utils.validator import TaskValidator

logger = logging.getLogger(__name__)


class TaskLoader:
    """
    Cargador de tasks desde archivos YAML.

    Soporta:
    - Carga desde archivos YAML organizados por dominio
    - Validacion automatica
    - Cache a nivel de clase (compartido entre todas las instancias)

    Estructura de archivos:
        templates/
        └── pharmacy/
            ├── identification.yaml
            ├── greeting.yaml
            └── confirmation.yaml

    Formato de key: domain.flow.action
        Ejemplo: pharmacy.identification.request_dni
        Se convierte a: templates/pharmacy/identification.yaml
    """

    # Class-level cache shared across all instances for performance
    _file_cache: dict[str, TaskTemplate] = {}

    def __init__(self, templates_dir: Path | None = None):
        """
        Inicializa el loader.

        Args:
            templates_dir: Directorio base de templates YAML
        """
        if templates_dir is None:
            # Directorio por defecto relativo a este archivo
            self.templates_dir = Path(__file__).parent / "templates"
        else:
            self.templates_dir = templates_dir

        logger.debug(f"TaskLoader initialized with templates_dir: {self.templates_dir}")

    async def load(self, key: str) -> TaskTemplate | None:
        """
        Carga un task desde archivo YAML.

        Args:
            key: Clave del task (ej: "pharmacy.identification.request_dni")

        Returns:
            TaskTemplate si se encuentra, None si no existe
        """
        return await self.load_from_file(key)

    async def load_from_file(self, key: str) -> TaskTemplate | None:
        """
        Carga un task desde archivo YAML.

        Args:
            key: Clave del task (ej: "pharmacy.identification.request_dni")

        Returns:
            TaskTemplate si el archivo existe y es valido
        """
        # Verificar cache a nivel de clase
        if key in TaskLoader._file_cache:
            logger.debug(f"Loading task '{key}' from file cache")
            return TaskLoader._file_cache[key]

        # Convertir clave a ruta de archivo
        # pharmacy.identification.request_dni → templates/pharmacy/identification.yaml
        parts = key.split(".")
        if len(parts) < 2:
            logger.error(f"Invalid task key format: {key}")
            return None

        # Construir ruta: domain/flow.yaml
        domain = parts[0]
        filename = f"{parts[1]}.yaml"
        file_path = self.templates_dir / domain / filename

        if not file_path.exists():
            logger.warning(f"Task file not found: {file_path}")
            return None

        try:
            # Cargar YAML
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Validar estructura
            if not isinstance(data, dict):
                logger.error(f"Invalid YAML structure in {file_path}")
                return None

            # Buscar el task especifico por key
            task_data = None
            if "tasks" in data:
                # Archivo con multiples tasks
                for task in data["tasks"]:
                    if task.get("key") == key:
                        task_data = task
                        break
            elif data.get("key") == key:
                # Archivo con un solo task
                task_data = data

            if not task_data:
                logger.warning(f"Task with key '{key}' not found in {file_path}")
                return None

            # Validar task
            validation = TaskValidator.validate_task(task_data)
            if not validation["is_valid"]:
                logger.error(f"Invalid task in {file_path}: {validation['errors']}")
                return None

            # Crear template
            template = TaskTemplate(
                key=task_data["key"],
                name=task_data["name"],
                description=task_data["description"],
                version=task_data.get("version", "1.0.0"),
                metadata=task_data.get("metadata", {}),
            )

            # Cachear a nivel de clase
            TaskLoader._file_cache[key] = template
            logger.info(f"Loaded task '{key}' from file: {file_path}")

            return template

        except Exception as e:
            logger.error(f"Error loading task from file {file_path}: {e}")
            return None

    async def list_available_tasks(self, domain: str | None = None) -> list[str]:
        """
        Lista todos los tasks disponibles.

        Args:
            domain: Filtrar por dominio (opcional)

        Returns:
            Lista de claves de tasks disponibles
        """
        available: list[str] = []

        try:
            # Si se especifica dominio, solo buscar en ese directorio
            if domain:
                domain_dirs = [self.templates_dir / domain]
            else:
                domain_dirs = [
                    d
                    for d in self.templates_dir.iterdir()
                    if d.is_dir() and not d.name.startswith("_")
                ]

            for domain_dir in domain_dirs:
                if not domain_dir.exists():
                    continue

                for yaml_file in domain_dir.glob("*.yaml"):
                    try:
                        with open(yaml_file, encoding="utf-8") as f:
                            data = yaml.safe_load(f)

                        if isinstance(data, dict):
                            if "tasks" in data:
                                for task in data["tasks"]:
                                    if "key" in task:
                                        available.append(task["key"])
                            elif "key" in data:
                                available.append(data["key"])
                    except Exception as e:
                        logger.warning(f"Error reading {yaml_file}: {e}")

        except Exception as e:
            logger.error(f"Error scanning task files: {e}")

        return available

    def clear_cache(self) -> None:
        """Limpia el cache de archivos."""
        cache_size = len(TaskLoader._file_cache)
        TaskLoader._file_cache.clear()
        logger.info(f"Task cache cleared - removed {cache_size} entries")

    def get_cache_info(self) -> dict[str, Any]:
        """Retorna informacion sobre el cache."""
        return {
            "size": len(TaskLoader._file_cache),
            "keys": list(TaskLoader._file_cache.keys()),
        }
