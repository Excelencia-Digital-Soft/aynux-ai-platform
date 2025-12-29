"""
PromptManager - Manager principal del sistema de gestión de prompts.
"""

import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.database.async_db import get_async_db_context
from app.models.db.prompts import Prompt, PromptVersion

from .loader import PromptLoader, PromptTemplate
from .utils.renderer import PromptRenderer
from .utils.validator import PromptValidator

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manager principal para gestión de prompts.

    Características:
    - Caché inteligente en memoria
    - Carga híbrida (archivos + BD)
    - Renderizado de templates con variables
    - Versionado y historial
    - Métricas de uso
    """

    def __init__(self, cache_size: int = 500, cache_ttl: int = 3600):
        """
        Inicializa el manager.

        Args:
            cache_size: Tamaño máximo del caché (número de prompts)
            cache_ttl: Tiempo de vida del caché en segundos
        """
        self.loader = PromptLoader()
        self.renderer = PromptRenderer()
        self.validator = PromptValidator()

        # Configuración del caché
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self._cache: OrderedDict[str, PromptTemplate] = OrderedDict()
        self._cache_timestamps: Dict[str, float] = {}

        # Métricas
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "file_loads": 0,
            "db_loads": 0,
            "render_errors": 0,
        }

        logger.info(f"PromptManager initialized - cache_size={cache_size}, cache_ttl={cache_ttl}s")

    async def get_prompt(
        self,
        key: str,
        variables: Optional[Dict[str, Any]] = None,
        prefer_db: bool = True,
        use_cache: bool = True,
    ) -> str:
        """
        Obtiene y renderiza un prompt.

        Args:
            key: Clave del prompt
            variables: Variables para renderizar el template
            prefer_db: Si True, prioriza BD sobre archivos
            use_cache: Si True, usa el caché

        Returns:
            Prompt renderizado con variables sustituidas

        Raises:
            ValueError: Si el prompt no se encuentra o hay error de renderizado
        """
        self._stats["total_requests"] += 1

        try:
            # 1. Intentar obtener del caché
            template = None
            if use_cache:
                template = self._get_from_cache(key)
                if template:
                    self._stats["cache_hits"] += 1
                    logger.debug(f"Cache hit for prompt: {key}")
                else:
                    self._stats["cache_misses"] += 1

            # 2. Cargar del source si no está en caché
            if template is None:
                template = await self.loader.load(key, prefer_db=prefer_db)

                if template is None:
                    raise ValueError(f"Prompt not found: {key}")

                # Actualizar estadísticas de carga
                if prefer_db:
                    self._stats["db_loads"] += 1
                else:
                    self._stats["file_loads"] += 1

                # Almacenar en caché
                if use_cache:
                    self._store_in_cache(key, template)

            # 3. Renderizar template con variables
            if variables:
                rendered = self.renderer.render(template.template, variables, strict=False)
            else:
                rendered = template.template

            return rendered

        except Exception as e:
            logger.error(f"Error getting prompt '{key}': {e}")
            self._stats["render_errors"] += 1
            raise

    async def get_template(self, key: str, prefer_db: bool = True) -> Optional[PromptTemplate]:
        """
        Obtiene un template sin renderizar.

        Args:
            key: Clave del prompt
            prefer_db: Si True, prioriza BD sobre archivos

        Returns:
            PromptTemplate o None si no se encuentra
        """
        # Verificar caché
        template = self._get_from_cache(key)
        if template:
            return template

        # Cargar y cachear
        template = await self.loader.load(key, prefer_db=prefer_db)
        if template:
            self._store_in_cache(key, template)

        return template

    async def save_dynamic_prompt(
        self,
        key: str,
        name: str,
        template: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> Prompt:
        """
        Guarda o actualiza un prompt dinámico en la base de datos.

        Args:
            key: Clave única del prompt
            name: Nombre descriptivo
            template: Template del prompt
            description: Descripción opcional
            metadata: Metadata adicional
            created_by: Usuario que crea/actualiza

        Returns:
            Objeto Prompt creado/actualizado

        Raises:
            ValueError: Si la validación falla
        """
        # Validar prompt
        prompt_data = {
            "key": key,
            "name": name,
            "template": template,
            "description": description,
            "metadata": metadata or {},
        }

        validation = self.validator.validate_prompt(prompt_data)
        if not validation["is_valid"]:
            raise ValueError(f"Invalid prompt: {', '.join(validation['errors'])}")

        try:
            async with get_async_db_context() as db:
                # Verificar si existe
                stmt = select(Prompt).where(Prompt.key == key)
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Actualizar existente
                    # Primero, crear versión histórica
                    version = PromptVersion(
                        prompt_id=existing.id,
                        version=existing.version,
                        template=existing.template,
                        created_by=created_by,
                        is_active=False,
                    )
                    db.add(version)

                    # Actualizar prompt
                    existing.template = template  # type: ignore[assignment]
                    existing.name = name  # type: ignore[assignment]
                    existing.description = description  # type: ignore[assignment]
                    existing.metadata = metadata or {}
                    existing.is_dynamic = True  # type: ignore[assignment]

                    await db.commit()
                    await db.refresh(existing)

                    # Invalidar caché
                    if key in self._cache:
                        del self._cache[key]
                        del self._cache_timestamps[key]

                    logger.info(f"Updated dynamic prompt: {key}")
                    return existing
                else:
                    # Crear nuevo
                    new_prompt = Prompt(
                        key=key,
                        name=name,
                        template=template,
                        description=description,
                        version="1.0.0",
                        is_dynamic=True,
                        is_active=True,
                        metadata=metadata or {},
                        created_by=created_by,
                    )

                    db.add(new_prompt)
                    await db.commit()
                    await db.refresh(new_prompt)

                    logger.info(f"Created new dynamic prompt: {key}")
                    return new_prompt

        except Exception as e:
            logger.error(f"Error saving dynamic prompt: {e}")
            raise

    async def list_prompts(
        self,
        domain: Optional[str] = None,
        is_dynamic: Optional[bool] = None,
        is_active: Optional[bool] = True,
    ) -> List[Dict[str, Any]]:
        """
        Lista prompts disponibles desde base de datos y archivos YAML.

        Args:
            domain: Filtrar por dominio (ej: "product")
            is_dynamic: Filtrar por tipo dinámico/estático
            is_active: Filtrar por estado activo

        Returns:
            Lista de diccionarios con información de prompts
        """
        results: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()

        try:
            # 1. Get prompts from database
            async with get_async_db_context() as db:
                stmt = select(Prompt)

                if is_dynamic is not None:
                    stmt = stmt.where(Prompt.is_dynamic == is_dynamic)
                if is_active is not None:
                    stmt = stmt.where(Prompt.is_active == is_active)
                if domain:
                    stmt = stmt.where(Prompt.key.startswith(f"{domain}."))

                result = await db.execute(stmt)
                db_prompts = result.scalars().all()

                for prompt in db_prompts:
                    prompt_dict = prompt.to_dict()
                    prompt_dict["source"] = "database"
                    prompt_dict["is_dynamic"] = True
                    results.append(prompt_dict)
                    seen_keys.add(prompt.key)

        except Exception as e:
            logger.error(f"Error listing prompts from database: {e}")

        # 2. Get prompts from YAML files (if not filtering for dynamic only)
        if is_dynamic is not True:  # Include file prompts unless specifically asking for dynamic
            try:
                file_keys = await self.loader.list_available_prompts(source="file")

                for key in file_keys:
                    # Skip if already loaded from DB (DB takes precedence)
                    if key in seen_keys:
                        continue

                    # Apply domain filter
                    if domain and not key.startswith(f"{domain}."):
                        continue

                    # Load the template to get full details
                    template = await self.loader.load_from_file(key)
                    if template:
                        prompt_dict = {
                            "id": key,  # Use key as ID for file-based prompts
                            "key": template.key,
                            "name": template.name,
                            "description": template.description,
                            "template": template.template,
                            "version": template.version,
                            "is_active": True,
                            "is_dynamic": False,
                            "metadata": template.metadata,
                            "source": "file",
                            "created_at": None,
                            "updated_at": None,
                            "created_by": None,
                        }
                        results.append(prompt_dict)
                        seen_keys.add(key)

            except Exception as e:
                logger.error(f"Error listing prompts from files: {e}")

        return results

    async def get_versions(self, prompt_key: str) -> List[Dict[str, Any]]:
        """
        Obtiene todas las versiones históricas de un prompt.

        Args:
            prompt_key: Clave del prompt

        Returns:
            Lista de versiones
        """
        try:
            async with get_async_db_context() as db:
                # Obtener prompt
                stmt = select(Prompt).where(Prompt.key == prompt_key)
                result = await db.execute(stmt)
                prompt = result.scalar_one_or_none()

                if not prompt:
                    return []

                # Obtener versiones
                stmt = select(PromptVersion).where(PromptVersion.prompt_id == prompt.id)
                result = await db.execute(stmt)
                versions = result.scalars().all()

                return [version.to_dict() for version in versions]

        except Exception as e:
            logger.error(f"Error getting prompt versions: {e}")
            return []

    async def rollback_to_version(self, prompt_key: str, version_id: str) -> bool:
        """
        Revierte un prompt a una versión anterior.

        Args:
            prompt_key: Clave del prompt
            version_id: ID de la versión a restaurar

        Returns:
            True si se realizó el rollback exitosamente
        """
        try:
            async with get_async_db_context() as db:
                # Obtener versión
                stmt = select(PromptVersion).where(PromptVersion.id == version_id)
                result = await db.execute(stmt)
                version = result.scalar_one_or_none()

                if not version:
                    logger.error(f"Version not found: {version_id}")
                    return False

                # Obtener prompt actual
                prompt = await db.get(Prompt, version.prompt_id)
                if not prompt:
                    return False

                # Crear versión de respaldo del estado actual
                backup_version = PromptVersion(
                    prompt_id=prompt.id,
                    version=prompt.version,
                    template=prompt.template,
                    is_active=False,
                )
                db.add(backup_version)

                # Actualizar prompt con la versión antigua
                prompt.template = version.template
                prompt.version = version.version

                await db.commit()

                # Invalidar caché
                if prompt_key in self._cache:
                    del self._cache[prompt_key]
                    del self._cache_timestamps[prompt_key]

                logger.info(f"Rolled back prompt '{prompt_key}' to version {version.version}")
                return True

        except Exception as e:
            logger.error(f"Error rolling back prompt: {e}")
            return False

    def _get_from_cache(self, key: str) -> Optional[PromptTemplate]:
        """Obtiene un template del caché si está vigente."""
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

        # Hit de caché válido - mover al final (LRU)
        template = self._cache.pop(key)
        self._cache[key] = template

        return template

    def _store_in_cache(self, key: str, template: PromptTemplate):
        """Almacena un template en el caché con gestión LRU."""
        current_time = time.time()

        # Gestión de tamaño (LRU)
        if len(self._cache) >= self.cache_size:
            # Remover el más antiguo
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        # Almacenar
        self._cache[key] = template
        self._cache_timestamps[key] = current_time

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de uso."""
        hit_rate = 0
        if self._stats["total_requests"] > 0:
            hit_rate = (self._stats["cache_hits"] / self._stats["total_requests"]) * 100

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.cache_size,
            "cache_hit_rate": f"{hit_rate:.1f}%",
            **self._stats,
        }

    def clear_cache(self):
        """Limpia el caché completamente."""
        cache_size = len(self._cache)
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info(f"Prompt cache cleared - removed {cache_size} entries")
