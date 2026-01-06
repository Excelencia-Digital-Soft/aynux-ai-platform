# ============================================================================
# SCOPE: GLOBAL
# Description: Detector de capacidades para modelos de IA. Usa pattern matching
#              para inferir capacidades desde el nombre del modelo.
# ============================================================================
"""
Capability Detector - Model capability detection service.

Single Responsibility: Detect vision and function calling capabilities.
Uses pattern matching to infer capabilities from model name.

Usage:
    detector = CapabilityDetector()

    # Single model
    caps = await detector.detect("Qwen/Qwen2.5-7B-Instruct")

    # Batch detection
    caps_map = await detector.detect_batch(["Qwen/Qwen2.5-7B-Instruct", "deepseek-ai/DeepSeek-R1"])
"""

import asyncio
import logging

from app.config.model_capabilities import (
    ModelCapabilities,
    detect_capabilities_from_patterns,
)

logger = logging.getLogger(__name__)


class CapabilityDetector:
    """
    Model capability detection service.

    Single Responsibility: Detect model capabilities (vision, functions).
    Uses pattern matching to infer capabilities from model names.
    """

    def __init__(self) -> None:
        """Initialize detector."""
        pass

    async def detect(self, model_name: str) -> ModelCapabilities:
        """Detect capabilities for a single model.

        Uses pattern matching to infer capabilities from model name.

        Args:
            model_name: Model name (e.g., "Qwen/Qwen2.5-7B-Instruct")

        Returns:
            ModelCapabilities with detection results
        """
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

        Args:
            model_names: List of model names to detect
            max_concurrent: Max concurrent operations (for API compatibility)

        Returns:
            Dict mapping model_name to ModelCapabilities
        """
        results: dict[str, ModelCapabilities] = {}

        async def detect_model(name: str) -> tuple[str, ModelCapabilities]:
            return name, await self.detect(name)

        tasks = [detect_model(name) for name in model_names]
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
        model_data: dict,
    ) -> ModelCapabilities:
        """Detect capabilities from model info dict.

        Args:
            model_data: Model info dict with 'capabilities' key

        Returns:
            ModelCapabilities parsed from the data
        """
        model_name = model_data.get("model_id", model_data.get("name", ""))
        return await self.detect(model_name)
