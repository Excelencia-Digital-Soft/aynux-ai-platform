"""
YAML prompt loader.

This module handles loading prompt templates from YAML files,
with caching and validation support.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import ValidationError

from .models import PromptCollection, PromptTemplate

logger = logging.getLogger(__name__)


class PromptLoadError(Exception):
    """Raised when a prompt file cannot be loaded."""

    pass


class YAMLPromptLoader:
    """
    Loads prompt templates from YAML files.

    Provides caching and validation of prompt templates.
    Follows SRP: Only responsible for loading and parsing YAML files.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the prompt loader.

        Args:
            templates_dir: Directory containing YAML template files.
                          Defaults to app/prompts/templates/
        """
        if templates_dir is None:
            # Default to app/prompts/templates/
            current_file = Path(__file__)
            templates_dir = current_file.parent / "templates"

        self.templates_dir = Path(templates_dir)
        self._cache: Dict[str, PromptCollection] = {}
        self._file_timestamps: Dict[str, float] = {}

        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")

    def load_file(self, file_path: Path, use_cache: bool = True) -> PromptCollection:
        """
        Load prompts from a single YAML file.

        Args:
            file_path: Path to the YAML file
            use_cache: Whether to use cached version if available

        Returns:
            PromptCollection with all prompts from the file

        Raises:
            PromptLoadError: If file cannot be loaded or validated
        """
        file_path = Path(file_path)

        # Check cache
        cache_key = str(file_path)
        if use_cache and cache_key in self._cache:
            # Check if file has been modified
            current_mtime = file_path.stat().st_mtime
            cached_mtime = self._file_timestamps.get(cache_key, 0)

            if current_mtime <= cached_mtime:
                logger.debug(f"Using cached prompts from {file_path}")
                return self._cache[cache_key]

        # Load and parse YAML
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                raise PromptLoadError(f"Empty YAML file: {file_path}")

            # Validate and create PromptCollection
            collection = PromptCollection(**data)

            # Cache the result
            self._cache[cache_key] = collection
            self._file_timestamps[cache_key] = file_path.stat().st_mtime

            logger.info(f"Loaded {len(collection.prompts)} prompts from {file_path}")
            return collection

        except FileNotFoundError:
            raise PromptLoadError(f"Prompt file not found: {file_path}")
        except yaml.YAMLError as e:
            raise PromptLoadError(f"Invalid YAML in {file_path}: {e}")
        except ValidationError as e:
            raise PromptLoadError(f"Invalid prompt structure in {file_path}: {e}")
        except Exception as e:
            raise PromptLoadError(f"Error loading {file_path}: {e}")

    def load_directory(self, directory: Optional[Path] = None, recursive: bool = True) -> List[PromptCollection]:
        """
        Load all YAML files from a directory.

        Args:
            directory: Directory to load from. Defaults to templates_dir
            recursive: Whether to search subdirectories

        Returns:
            List of PromptCollections from all files
        """
        if directory is None:
            directory = self.templates_dir

        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return []

        collections = []
        pattern = "**/*.yaml" if recursive else "*.yaml"

        for yaml_file in directory.glob(pattern):
            try:
                collection = self.load_file(yaml_file)
                collections.append(collection)
            except PromptLoadError as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
                # Continue loading other files

        logger.info(f"Loaded {len(collections)} prompt collections from {directory}")
        return collections

    def load_prompt(self, file_path: Path, prompt_key: str) -> Optional[PromptTemplate]:
        """
        Load a specific prompt from a file.

        Args:
            file_path: Path to the YAML file
            prompt_key: Key of the prompt to load

        Returns:
            PromptTemplate if found, None otherwise
        """
        try:
            collection = self.load_file(file_path)
            return collection.get_prompt(prompt_key)
        except PromptLoadError as e:
            logger.error(f"Failed to load prompt {prompt_key} from {file_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()
        self._file_timestamps.clear()
        logger.debug("Prompt cache cleared")

    def reload(self) -> None:
        """Reload all cached prompts from disk."""
        self.clear_cache()
        logger.info("Prompt cache reloaded")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "cached_files": len(self._cache),
            "total_prompts": sum(len(c.prompts) for c in self._cache.values()),
        }
