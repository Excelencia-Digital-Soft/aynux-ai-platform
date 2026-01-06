# ============================================================================
# SCOPE: GLOBAL
# Description: Detección de capacidades para modelos LLM. Utiliza el
#              endpoint /api/show para detectar soporte de visión y tools,
#              con fallback a pattern matching para modelos conocidos.
# ============================================================================
"""
LLM Model Capability Detection Module.

Provides capability detection for LLM models through:
1. API-based detection via /api/show capabilities array
2. Pattern-based fallback for known model families

Usage:
    from app.config.model_capabilities import (
        detect_capabilities_from_patterns,
        parse_api_capabilities,
        ModelCapabilities,
    )

    # From API response
    caps = parse_api_capabilities(
        capabilities=["completion", "vision"],
        model_info={"gemma3.vision.image_size": 896}
    )

    # From model name (fallback)
    caps = detect_capabilities_from_patterns("llava:7b")
"""

import re
from dataclasses import dataclass, field
from typing import Literal

# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ModelCapabilities:
    """Detected capabilities for an LLM model.

    Attributes:
        supports_vision: Whether model supports image/multimodal input
        supports_functions: Whether model supports function/tool calling
        detection_method: How capabilities were detected (api, pattern, default)
        raw_capabilities: Original capabilities array from /api/show (if available)
    """

    supports_vision: bool = False
    supports_functions: bool = False
    detection_method: Literal["api", "pattern", "default"] = "default"
    raw_capabilities: list[str] | None = field(default=None)


# =============================================================================
# Known Model Patterns
# =============================================================================

# Vision-capable model patterns (name-based detection)
VISION_MODEL_PATTERNS: list[str] = [
    r"llava",  # LLaVA family
    r"llama3\.2.*vision",  # Llama 3.2 Vision
    r"gemma.*vision",  # Gemma Vision variants
    r"qwen.*vl",  # Qwen VL (Vision-Language)
    r"bakllava",  # BakLLaVA
    r"moondream",  # Moondream
    r"minicpm.*v",  # MiniCPM-V
    r"cogvlm",  # CogVLM
    r"llama-3\.2.*\d+b-vision",  # Alternative Llama 3.2 vision naming
]

# Function/tool calling capable model patterns
FUNCTION_CALLING_PATTERNS: list[str] = [
    r"llama3\.1",  # Llama 3.1 supports tools
    r"llama3\.2",  # Llama 3.2 supports tools (all variants)
    r"llama-3\.1",  # Alternative naming
    r"llama-3\.2",  # Alternative naming
    r"qwen2\.5",  # Qwen 2.5 supports tools
    r"qwen3",  # Qwen 3 supports tools
    r"mistral",  # Mistral supports tools
    r"mixtral",  # Mixtral supports tools
    r"command-r",  # Cohere Command-R
    r"granite",  # IBM Granite
    r"firefunction",  # FireFunction
    r"hermes",  # Hermes models
    r"nexusraven",  # NexusRaven
    r"functionary",  # Functionary models
]

# Compiled patterns for performance
_VISION_REGEX = [re.compile(p, re.IGNORECASE) for p in VISION_MODEL_PATTERNS]
_FUNCTION_REGEX = [re.compile(p, re.IGNORECASE) for p in FUNCTION_CALLING_PATTERNS]


# =============================================================================
# Detection Functions
# =============================================================================


def detect_capabilities_from_patterns(model_name: str) -> ModelCapabilities:
    """
    Detect capabilities using name pattern matching.

    This is the fallback method when API detection fails or is unavailable.
    Uses known patterns for vision and function calling models.

    Args:
        model_name: LLM model name (e.g., "llava:7b", "llama3.1:8b")

    Returns:
        ModelCapabilities with pattern-detected values
    """
    name_lower = model_name.lower()

    supports_vision = any(pattern.search(name_lower) for pattern in _VISION_REGEX)
    supports_functions = any(pattern.search(name_lower) for pattern in _FUNCTION_REGEX)

    return ModelCapabilities(
        supports_vision=supports_vision,
        supports_functions=supports_functions,
        detection_method="pattern",
    )


def parse_api_capabilities(
    capabilities: list[str] | None,
    model_info: dict | None = None,
) -> ModelCapabilities:
    """
    Parse capabilities from LLM /api/show response.

    Primary detection method using the official API response.

    Args:
        capabilities: The capabilities array from /api/show response
                      (e.g., ["completion", "vision", "tools"])
        model_info: Optional model_info dict for additional vision detection
                    via *.vision.* keys

    Returns:
        ModelCapabilities with API-detected values

    Example:
        >>> caps = parse_api_capabilities(
        ...     capabilities=["completion", "vision"],
        ...     model_info={"gemma3.vision.image_size": 896}
        ... )
        >>> caps.supports_vision
        True
    """
    if capabilities is None:
        capabilities = []

    # Primary detection from capabilities array
    supports_vision = "vision" in capabilities
    supports_functions = "tools" in capabilities

    # Secondary check: look for vision keys in model_info
    # Some models expose vision config without "vision" in capabilities
    if not supports_vision and model_info:
        vision_keys = [k for k in model_info.keys() if ".vision." in k.lower()]
        supports_vision = len(vision_keys) > 0

    return ModelCapabilities(
        supports_vision=supports_vision,
        supports_functions=supports_functions,
        detection_method="api",
        raw_capabilities=capabilities if capabilities else None,
    )


def get_default_capabilities() -> ModelCapabilities:
    """
    Get default capabilities for unknown models.

    Conservative defaults: assume no special capabilities.
    Admin can manually override in the UI.

    Returns:
        ModelCapabilities with default (false) values
    """
    return ModelCapabilities(
        supports_vision=False,
        supports_functions=False,
        detection_method="default",
    )
