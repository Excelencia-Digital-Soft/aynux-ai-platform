# ============================================================================
# SCOPE: GLOBAL
# Description: Detector de capacidades para modelos de IA. Usa API de Ollama
#              con fallback a pattern matching para inferir capacidades.
# ============================================================================
"""
Capability Detector - Model capability detection service.

Single Responsibility: Detect vision and function calling capabilities.
Uses OllamaClient for API access, with pattern matching fallback.

Usage:
    client = OllamaClient()
    detector = CapabilityDetector(client)

    # Single model
    caps = await detector.detect("llama3.2:3b")

    # Batch detection
    caps_map = await detector.detect_batch(["llama3.2:3b", "gemma3:latest"])
"""

import asyncio
import logging

from app.config.model_capabilities import (
    ModelCapabilities,
    detect_capabilities_from_patterns,
    parse_api_capabilities,
)
from app.integrations.ollama.client import OllamaClient

logger = logging.getLogger(__name__)


class CapabilityDetector:
    """
    Model capability detection service.

    Single Responsibility: Detect model capabilities (vision, functions).
    Delegates HTTP to OllamaClient, uses model_capabilities for parsing.
    """

    def __init__(self, ollama_client: OllamaClient) -> None:
        """Initialize detector with Ollama client.

        Args:
            ollama_client: OllamaClient for API access
        """
        self._client = ollama_client

    async def detect(self, model_name: str) -> ModelCapabilities:
        """Detect capabilities for a single model.

        Strategy:
        1. Query Ollama /api/show for capabilities array
        2. If API fails, fallback to pattern matching
        3. Return detected capabilities with method used

        Args:
            model_name: Ollama model name (e.g., "llama3.2:3b")

        Returns:
            ModelCapabilities with detection results
        """
        # Try API detection first
        model_info = await self._client.get_model_info(model_name)

        if model_info:
            capabilities = parse_api_capabilities(
                capabilities=model_info.capabilities,
                model_info=model_info.model_info,
            )
            logger.debug(
                f"API detected for {model_name}: "
                f"vision={capabilities.supports_vision}, "
                f"functions={capabilities.supports_functions}"
            )
            return capabilities

        # Fallback to pattern matching
        capabilities = detect_capabilities_from_patterns(model_name)
        logger.debug(
            f"Pattern detected for {model_name}: "
            f"vision={capabilities.supports_vision}, "
            f"functions={capabilities.supports_functions}"
        )
        return capabilities

    async def detect_batch(
        self,
        model_names: list[str],
        max_concurrent: int = 5,
    ) -> dict[str, ModelCapabilities]:
        """Detect capabilities for multiple models in parallel.

        Uses semaphore to limit concurrent API requests.

        Args:
            model_names: List of model names to detect
            max_concurrent: Max concurrent /api/show requests

        Returns:
            Dict mapping model_name to ModelCapabilities
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results: dict[str, ModelCapabilities] = {}

        async def detect_with_limit(name: str) -> tuple[str, ModelCapabilities]:
            async with semaphore:
                return name, await self.detect(name)

        tasks = [detect_with_limit(name) for name in model_names]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in task_results:
            if isinstance(result, Exception):
                logger.warning(f"Capability detection failed: {result}")
                continue
            model_name, capabilities = result
            results[model_name] = capabilities

        logger.info(
            f"Batch detection complete: {len(results)}/{len(model_names)} successful"
        )
        return results

    async def detect_from_raw_data(
        self,
        ollama_data: dict,
    ) -> ModelCapabilities:
        """Detect capabilities from raw Ollama /api/show response.

        Useful when you already have the API response data.

        Args:
            ollama_data: Raw /api/show response dict

        Returns:
            ModelCapabilities parsed from the data
        """
        return parse_api_capabilities(
            capabilities=ollama_data.get("capabilities", []),
            model_info=ollama_data.get("model_info"),
        )
