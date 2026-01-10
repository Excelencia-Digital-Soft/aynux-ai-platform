"""
PromptLoader - Cargador de prompts desde archivos YAML y base de datos.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from sqlalchemy import select

from app.database.async_db import get_async_db_context
from app.models.db.prompts import Prompt

from .utils.validator import PromptValidator

logger = logging.getLogger(__name__)


class PromptTemplate:
    """
    Representa un template de prompt con su metadata.
    """

    def __init__(
        self,
        key: str,
        name: str,
        template: str,
        description: Optional[str] = None,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.key = key
        self.name = name
        self.template = template
        self.description = description
        self.version = version
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el template a diccionario."""
        return {
            "key": self.key,
            "name": self.name,
            "template": self.template,
            "description": self.description,
            "version": self.version,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return f"<PromptTemplate(key='{self.key}', version='{self.version}')>"


class PromptLoader:
    """
    Cargador de prompts desde múltiples fuentes.

    Soporta:
    - Carga desde archivos YAML
    - Carga desde base de datos
    - Validación automática
    - Caché a nivel de clase (compartido entre todas las instancias)
    """

    # Class-level cache shared across all instances for performance
    _file_cache: Dict[str, PromptTemplate] = {}
    _db_cache: Dict[str, PromptTemplate] = {}

    def __init__(self, templates_dir: Optional[Path] = None):
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

        logger.debug(f"PromptLoader initialized with templates_dir: {self.templates_dir}")

    async def load(self, key: str, prefer_db: bool = True) -> Optional[PromptTemplate]:
        """
        Carga un prompt intentando primero base de datos y luego archivos.

        Args:
            key: Clave del prompt
            prefer_db: Si True, intenta cargar de BD primero

        Returns:
            PromptTemplate si se encuentra, None si no existe
        """
        if prefer_db:
            # Intentar cargar de BD primero
            db_template = await self.load_from_db(key)
            if db_template:
                return db_template

            # Fallback a archivo
            return await self.load_from_file(key)
        else:
            # Intentar archivo primero
            file_template = await self.load_from_file(key)
            if file_template:
                return file_template

            # Fallback a BD
            return await self.load_from_db(key)

    async def load_from_file(self, key: str) -> Optional[PromptTemplate]:
        """
        Carga un prompt desde archivo YAML.

        Args:
            key: Clave del prompt (ej: "product.search.intent")

        Returns:
            PromptTemplate si el archivo existe y es válido
        """
        # Verificar caché a nivel de clase
        if key in PromptLoader._file_cache:
            logger.debug(f"Loading prompt '{key}' from file cache")
            return PromptLoader._file_cache[key]

        # Convertir clave a ruta de archivo
        # product.search.intent → templates/product/search.yaml
        parts = key.split(".")
        if len(parts) < 2:
            logger.error(f"Invalid prompt key format: {key}")
            return None

        # Construir ruta: domain/subdomain.yaml
        domain = parts[0]
        filename = f"{parts[1]}.yaml"
        file_path = self.templates_dir / domain / filename

        if not file_path.exists():
            logger.warning(f"Prompt file not found: {file_path}")
            return None

        try:
            # Cargar YAML
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            # Validar estructura
            if not isinstance(data, dict):
                logger.error(f"Invalid YAML structure in {file_path}")
                return None

            # Buscar el prompt específico por key
            prompt_data = None
            if "prompts" in data:
                # Archivo con múltiples prompts
                for prompt in data["prompts"]:
                    if prompt.get("key") == key:
                        prompt_data = prompt
                        break
            elif data.get("key") == key:
                # Archivo con un solo prompt
                prompt_data = data

            if not prompt_data:
                logger.warning(f"Prompt with key '{key}' not found in {file_path}")
                return None

            # Validar prompt
            validation = PromptValidator.validate_prompt(prompt_data)
            if not validation["is_valid"]:
                logger.error(f"Invalid prompt in {file_path}: {validation['errors']}")
                return None

            # Crear template
            template = PromptTemplate(
                key=prompt_data["key"],
                name=prompt_data["name"],
                template=prompt_data["template"],
                description=prompt_data.get("description"),
                version=prompt_data.get("version", "1.0.0"),
                metadata=prompt_data.get("metadata", {}),
            )

            # Cachear a nivel de clase
            PromptLoader._file_cache[key] = template
            logger.info(f"Loaded prompt '{key}' from file: {file_path}")

            return template

        except Exception as e:
            logger.error(f"Error loading prompt from file {file_path}: {e}")
            return None

    async def load_from_db(self, key: str) -> Optional[PromptTemplate]:
        """
        Carga un prompt desde base de datos con caché.

        Args:
            key: Clave del prompt

        Returns:
            PromptTemplate si existe en BD y está activo
        """
        # Verificar caché a nivel de clase
        if key in PromptLoader._db_cache:
            logger.debug(f"Loading prompt '{key}' from DB cache")
            return PromptLoader._db_cache[key]

        try:
            async with get_async_db_context() as db:
                # Buscar prompt activo
                stmt = select(Prompt).where(Prompt.key == key, Prompt.is_active)
                result = await db.execute(stmt)
                prompt = result.scalar_one_or_none()

                if not prompt:
                    logger.debug(f"Prompt '{key}' not found in database")
                    return None

                # Crear template
                template = PromptTemplate(
                    key=str(prompt.key),
                    name=str(prompt.name),
                    template=str(prompt.template),
                    description=str(prompt.description),
                    version=str(prompt.version),
                    metadata=prompt.meta_data,
                )

                # Cachear a nivel de clase
                PromptLoader._db_cache[key] = template
                logger.info(f"Loaded prompt '{key}' from database")
                return template

        except Exception as e:
            logger.error(f"Error loading prompt from database: {e}")
            return None

    async def list_available_prompts(self, source: str = "all") -> list[str]:
        """
        Lista todos los prompts disponibles.

        Args:
            source: "all", "file", or "db"

        Returns:
            Lista de claves de prompts disponibles
        """
        available = []

        if source in ["all", "file"]:
            # Escanear archivos YAML
            try:
                for domain_dir in self.templates_dir.iterdir():
                    if domain_dir.is_dir() and not domain_dir.name.startswith("_"):
                        for yaml_file in domain_dir.glob("*.yaml"):
                            try:
                                with open(yaml_file, "r", encoding="utf-8") as f:
                                    data = yaml.safe_load(f)

                                if isinstance(data, dict):
                                    if "prompts" in data:
                                        for prompt in data["prompts"]:
                                            if "key" in prompt:
                                                available.append(prompt["key"])
                                    elif "key" in data:
                                        available.append(data["key"])
                            except Exception as e:
                                logger.warning(f"Error reading {yaml_file}: {e}")
            except Exception as e:
                logger.error(f"Error scanning template files: {e}")

        if source in ["all", "db"]:
            # Consultar BD
            try:
                async with get_async_db_context() as db:
                    stmt = select(Prompt.key).where(Prompt.is_active)
                    result = await db.execute(stmt)
                    db_keys = [row[0] for row in result.fetchall()]
                    available.extend(db_keys)
            except Exception as e:
                logger.error(f"Error listing prompts from database: {e}")

        return list(set(available))  # Eliminar duplicados

    def clear_cache(self):
        """Limpia ambos cachés (archivos y BD)."""
        PromptLoader._file_cache.clear()
        PromptLoader._db_cache.clear()
        logger.info("Prompt caches cleared (file and DB)")
