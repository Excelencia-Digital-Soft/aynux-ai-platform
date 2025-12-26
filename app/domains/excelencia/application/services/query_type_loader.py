"""Loader for query type configuration from YAML.

This module handles loading query type definitions from YAML configuration,
following the Open/Closed Principle - new types can be added by editing
the YAML file without modifying code.
"""

import logging
from pathlib import Path

import yaml

from .query_type_detector import (
    CompositeQueryTypeDetector,
    FuzzyQueryTypeDetector,
    KeywordQueryTypeDetector,
    QueryTypeRegistry,
)

logger = logging.getLogger(__name__)

# Default path to query types YAML
DEFAULT_YAML_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "prompts"
    / "templates"
    / "excelencia"
    / "query_types.yaml"
)


def load_query_types_from_yaml(yaml_path: Path | None = None) -> QueryTypeRegistry:
    """Load query types from YAML configuration file.

    Args:
        yaml_path: Optional path to YAML file. Uses default if not provided.

    Returns:
        QueryTypeRegistry populated with types from YAML,
        or default registry if YAML loading fails.

    Example:
        registry = load_query_types_from_yaml()
        keywords = registry.get_keywords("incident")
    """
    if yaml_path is None:
        yaml_path = DEFAULT_YAML_PATH

    registry = QueryTypeRegistry()

    try:
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            logger.warning(f"Empty YAML file at {yaml_path}, using defaults")
            return _get_default_registry()

        query_types = config.get("query_types", {})
        priority_order = query_types.get("priority_order", [])
        types = query_types.get("types", {})

        # Load types in priority order
        for type_name in priority_order:
            type_config = types.get(type_name, {})
            keywords = type_config.get("keywords", [])
            if keywords:
                registry.add_type(type_name, keywords)

        logger.info(f"Loaded {len(registry.types)} query types from YAML: {yaml_path}")
        return registry

    except FileNotFoundError:
        logger.warning(f"Query types YAML not found at {yaml_path}, using defaults")
        return _get_default_registry()
    except yaml.YAMLError as e:
        logger.error(f"Error parsing query types YAML: {e}")
        return _get_default_registry()
    except Exception as e:
        logger.error(f"Unexpected error loading query types YAML: {e}")
        return _get_default_registry()


def load_fuzzy_config_from_yaml(yaml_path: Path | None = None) -> dict:
    """Load fuzzy matching configuration from YAML.

    Args:
        yaml_path: Optional path to YAML file.

    Returns:
        Dict with fuzzy matching config, or defaults if loading fails.
    """
    if yaml_path is None:
        yaml_path = DEFAULT_YAML_PATH

    defaults = {
        "enabled": True,
        "similarity_threshold": 0.8,
        "min_word_length": 4,
    }

    try:
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        fuzzy_config = config.get("fuzzy_matching", {})
        return {
            "enabled": fuzzy_config.get("enabled", defaults["enabled"]),
            "similarity_threshold": fuzzy_config.get(
                "similarity_threshold", defaults["similarity_threshold"]
            ),
            "min_word_length": fuzzy_config.get(
                "min_word_length", defaults["min_word_length"]
            ),
        }
    except Exception:
        return defaults


def create_query_type_detector(yaml_path: Path | None = None) -> CompositeQueryTypeDetector:
    """Create a fully configured CompositeQueryTypeDetector.

    This is a convenience factory function that creates a detector
    with both exact and fuzzy matching strategies, configured from YAML.

    Args:
        yaml_path: Optional path to YAML configuration file.

    Returns:
        CompositeQueryTypeDetector ready for use.

    Example:
        detector = create_query_type_detector()
        match = detector.detect("tengo una incendencia")  # Handles typo
        print(match.query_type)  # "incident"
        print(match.confidence)  # ~0.87
    """
    registry = load_query_types_from_yaml(yaml_path)
    fuzzy_config = load_fuzzy_config_from_yaml(yaml_path)

    detectors: list = [KeywordQueryTypeDetector(registry)]

    # Add fuzzy detector if enabled
    if fuzzy_config.get("enabled", True):
        detectors.append(
            FuzzyQueryTypeDetector(
                registry=registry,
                similarity_threshold=fuzzy_config.get("similarity_threshold", 0.8),
                min_word_length=fuzzy_config.get("min_word_length", 4),
            )
        )

    return CompositeQueryTypeDetector(detectors)


def _get_default_registry() -> QueryTypeRegistry:
    """Create a default registry with essential types (fallback).

    This provides basic functionality if YAML loading fails.

    Returns:
        QueryTypeRegistry with minimal default types.
    """
    registry = QueryTypeRegistry()

    # Essential types with minimal keywords
    registry.add_type(
        "incident",
        ["incidencia", "reportar", "ticket", "bug", "falla", "no funciona"],
    )
    registry.add_type(
        "feedback",
        ["sugerencia", "comentario", "feedback", "opinión"],
    )
    registry.add_type(
        "error",
        ["error", "fallo", "crash", "mensaje de error"],
    )
    registry.add_type(
        "training",
        ["capacitación", "curso", "entrenamiento", "tutorial"],
    )
    registry.add_type(
        "general",
        ["ayuda", "help", "soporte", "support", "consulta"],
    )

    logger.info("Using default query type registry (5 types)")
    return registry
