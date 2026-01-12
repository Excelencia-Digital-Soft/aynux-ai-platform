"""
TaskManager - Manager principal del sistema de gestion de tasks.
"""

import logging
import time
from collections import OrderedDict
from typing import Any

from .loader import TaskLoader
from .models import TaskTemplate
from .utils.renderer import TaskRenderer

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Manager principal para gestion de tasks.

    Caracteristicas:
    - Cache inteligente en memoria con LRU y TTL
    - Carga desde archivos YAML
    - Renderizado de templates con variables
    - Metricas de uso
    """

    def __init__(self, cache_size: int = 500, cache_ttl: int = 3600):
        """
        Inicializa el manager.

        Args:
            cache_size: Tamano maximo del cache (numero de tasks)
            cache_ttl: Tiempo de vida del cache en segundos (default: 1 hora)
        """
        self.loader = TaskLoader()
        self.renderer = TaskRenderer()

        # Configuracion del cache
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self._cache: OrderedDict[str, TaskTemplate] = OrderedDict()
        self._cache_timestamps: dict[str, float] = {}

        # Metricas
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "file_loads": 0,
            "render_errors": 0,
        }

        logger.info(
            f"TaskManager initialized - cache_size={cache_size}, cache_ttl={cache_ttl}s"
        )

    async def get_task(
        self,
        key: str,
        variables: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> str:
        """
        Obtiene y renderiza la descripcion de un task.

        Args:
            key: Clave del task
            variables: Variables para renderizar el template
            use_cache: Si True, usa el cache

        Returns:
            Descripcion del task renderizada con variables sustituidas

        Raises:
            ValueError: Si el task no se encuentra
        """
        self._stats["total_requests"] += 1

        try:
            # 1. Intentar obtener del cache
            template = None
            if use_cache:
                template = self._get_from_cache(key)
                if template:
                    self._stats["cache_hits"] += 1
                    logger.debug(f"Cache hit for task: {key}")
                else:
                    self._stats["cache_misses"] += 1

            # 2. Cargar del archivo si no esta en cache
            if template is None:
                template = await self.loader.load(key)

                if template is None:
                    raise ValueError(f"Task not found: {key}")

                self._stats["file_loads"] += 1

                # Almacenar en cache
                if use_cache:
                    self._store_in_cache(key, template)

            # 3. Renderizar template con variables
            if variables:
                rendered = self.renderer.render(
                    template.description, variables, strict=False
                )
            else:
                rendered = template.description

            return rendered

        except ValueError:
            # Re-raise ValueError as is
            raise
        except Exception as e:
            logger.error(f"Error getting task '{key}': {e}")
            self._stats["render_errors"] += 1
            raise ValueError(f"Error loading task '{key}': {e}") from e

    async def get_description(
        self,
        key: str,
        variables: dict[str, Any] | None = None,
    ) -> str:
        """
        Alias para get_task - obtiene la descripcion de un task.

        Args:
            key: Clave del task
            variables: Variables para renderizar el template

        Returns:
            Descripcion del task renderizada
        """
        return await self.get_task(key, variables)

    async def get_template(self, key: str) -> TaskTemplate | None:
        """
        Obtiene un template sin renderizar.

        Args:
            key: Clave del task

        Returns:
            TaskTemplate o None si no se encuentra
        """
        # Verificar cache
        template = self._get_from_cache(key)
        if template:
            return template

        # Cargar y cachear
        template = await self.loader.load(key)
        if template:
            self._store_in_cache(key, template)

        return template

    async def list_tasks(self, domain: str | None = None) -> list[dict[str, Any]]:
        """
        Lista tasks disponibles desde archivos YAML.

        Args:
            domain: Filtrar por dominio (ej: "pharmacy")

        Returns:
            Lista de diccionarios con informacion de tasks
        """
        results: list[dict[str, Any]] = []

        try:
            task_keys = await self.loader.list_available_tasks(domain=domain)

            for key in task_keys:
                # Aplicar filtro de dominio si se especifica
                if domain and not key.startswith(f"{domain}."):
                    continue

                # Cargar el template para obtener detalles completos
                template = await self.loader.load_from_file(key)
                if template:
                    task_dict = {
                        "key": template.key,
                        "name": template.name,
                        "description": template.description,
                        "version": template.version,
                        "metadata": template.metadata,
                        "source": "file",
                    }
                    results.append(task_dict)

        except Exception as e:
            logger.error(f"Error listing tasks: {e}")

        return results

    def _get_from_cache(self, key: str) -> TaskTemplate | None:
        """Obtiene un template del cache si esta vigente."""
        if key not in self._cache:
            return None

        # Verificar TTL
        current_time = time.time()
        cache_time = self._cache_timestamps.get(key, 0)

        if current_time - cache_time > self.cache_ttl:
            # Expirado
            del self._cache[key]
            del self._cache_timestamps[key]
            return None

        # Hit de cache valido - mover al final (LRU)
        template = self._cache.pop(key)
        self._cache[key] = template

        return template

    def _store_in_cache(self, key: str, template: TaskTemplate) -> None:
        """Almacena un template en el cache con gestion LRU."""
        current_time = time.time()

        # Gestion de tamano (LRU)
        if len(self._cache) >= self.cache_size:
            # Remover el mas antiguo
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        # Almacenar
        self._cache[key] = template
        self._cache_timestamps[key] = current_time

    def get_stats(self) -> dict[str, Any]:
        """Obtiene estadisticas de uso."""
        hit_rate = 0.0
        if self._stats["total_requests"] > 0:
            hit_rate = (self._stats["cache_hits"] / self._stats["total_requests"]) * 100

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.cache_size,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            **self._stats,
        }

    def clear_cache(self) -> None:
        """Limpia el cache completamente."""
        cache_size = len(self._cache)
        self._cache.clear()
        self._cache_timestamps.clear()
        self.loader.clear_cache()
        logger.info(f"Task cache cleared - removed {cache_size} entries")
