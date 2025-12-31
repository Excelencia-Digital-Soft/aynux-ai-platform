# ============================================================================
# SCOPE: GLOBAL
# Description: Servicio coordinador para gestión de modelos de IA. Orquesta
#              operaciones entre Repository, OllamaClient, CapabilityDetector
#              y ModelSeeder siguiendo Single Responsibility Principle.
# Tenant-Aware: No - modelos son globales, visibilidad controlada por is_enabled.
# ============================================================================
"""
AI Model Service - Thin coordinator for AI model operations.

Orchestrates operations between specialized services:
- AIModelRepository: Data persistence
- OllamaClient: Ollama API communication
- CapabilityDetector: Capability detection
- ModelSeeder: External model seeding

Single Responsibility: Coordinate and orchestrate model operations.
No direct DB access, no HTTP calls - delegates to specialized services.

Usage:
    # With explicit dependencies
    service = AIModelService(repository, ollama_client, detector, seeder)

    # Or use factory with just DB session
    service = AIModelService.create(db)

    models = await service.list_models()
    result = await service.sync_from_ollama()
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.ollama.client import OllamaClient, OllamaConnectionError
from app.models.db.ai_model import AIModel
from app.repositories.ai_model_repository import AIModelRepository
from app.services.capability_detector import CapabilityDetector
from app.services.model_seeder import ModelSeeder

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class AIModelServiceError(Exception):
    """Base exception for AI model service errors."""

    pass


class OllamaSyncError(AIModelServiceError):
    """Raised when Ollama sync fails."""

    pass


class ModelNotFoundError(AIModelServiceError):
    """Raised when a model is not found."""

    pass


# =============================================================================
# Service
# =============================================================================


class AIModelService:
    """
    AI Model Service - Thin coordinator.

    Single Responsibility: Orchestrate model operations.
    Delegates to specialized services for actual work.
    """

    def __init__(
        self,
        repository: AIModelRepository,
        ollama_client: OllamaClient,
        capability_detector: CapabilityDetector,
        seeder: ModelSeeder,
    ) -> None:
        """Initialize service with dependencies.

        Args:
            repository: AIModelRepository for data access
            ollama_client: OllamaClient for Ollama API
            capability_detector: CapabilityDetector for capability detection
            seeder: ModelSeeder for seeding external models
        """
        self._repository = repository
        self._ollama = ollama_client
        self._detector = capability_detector
        self._seeder = seeder

    @classmethod
    def with_session(cls, db: AsyncSession) -> "AIModelService":
        """Factory method to create service with all dependencies.

        Convenience method when you only have a DB session.

        Args:
            db: AsyncSession for database access

        Returns:
            Fully configured AIModelService
        """
        repository = AIModelRepository(db)
        ollama_client = OllamaClient()
        detector = CapabilityDetector(ollama_client)
        seeder = ModelSeeder(repository)

        return cls(
            repository=repository,
            ollama_client=ollama_client,
            capability_detector=detector,
            seeder=seeder,
        )

    # =========================================================================
    # Read Operations (delegated to repository)
    # =========================================================================

    async def list_models(
        self,
        provider: str | None = None,
        model_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[AIModel]:
        """List models with optional filtering.

        Args:
            provider: Filter by provider
            model_type: Filter by type
            enabled_only: Only return enabled models

        Returns:
            List of AIModel instances
        """
        return await self._repository.find_all(
            provider=provider,
            model_type=model_type,
            enabled_only=enabled_only,
        )

    async def get_enabled_models(self, model_type: str = "llm") -> list[dict]:
        """Get enabled models for UI select components.

        Args:
            model_type: Filter by model type

        Returns:
            List of dicts with value/label format
        """
        return await self._repository.get_enabled_for_select(model_type)

    async def get_by_id(self, model_id: UUID) -> AIModel | None:
        """Get model by UUID."""
        return await self._repository.get_by_id(model_id)

    async def get_by_model_id(self, model_id: str) -> AIModel | None:
        """Get model by provider-specific model ID."""
        return await self._repository.get_by_model_id(model_id)

    # =========================================================================
    # Write Operations (delegated to repository)
    # =========================================================================

    async def create(self, model_data: dict) -> AIModel:
        """Create a new AI model.

        Args:
            model_data: Model data dict

        Returns:
            Created AIModel
        """
        model = AIModel(**model_data)
        return await self._repository.create(model)

    async def update(self, model_id: UUID, update_data: dict) -> AIModel | None:
        """Update an existing model.

        Args:
            model_id: Model UUID
            update_data: Fields to update

        Returns:
            Updated AIModel or None if not found
        """
        model = await self._repository.get_by_id(model_id)
        if not model:
            return None

        for key, value in update_data.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)

        return await self._repository.update(model)

    async def delete(self, model_id: UUID) -> bool:
        """Delete a model."""
        return await self._repository.delete(model_id)

    async def toggle_enabled(self, model_id: UUID) -> AIModel | None:
        """Toggle model enabled status.

        Args:
            model_id: Model UUID

        Returns:
            Updated AIModel or None if not found
        """
        model = await self._repository.get_by_id(model_id)
        if not model:
            return None

        model.is_enabled = not model.is_enabled  # type: ignore[assignment]
        updated = await self._repository.update(model)

        logger.info(
            f"Model {updated.model_id} is now "
            f"{'enabled' if updated.is_enabled else 'disabled'}"
        )
        return updated

    async def set_enabled(self, model_id: UUID, enabled: bool) -> AIModel | None:
        """Set model enabled status explicitly."""
        return await self.update(model_id, {"is_enabled": enabled})

    # =========================================================================
    # Sync Operations (orchestrates multiple services)
    # =========================================================================

    async def sync_from_ollama(self) -> dict[str, int | list[str] | None]:
        """Sync models from Ollama with capability detection.

        Orchestrates:
        1. OllamaClient: Fetch model list
        2. CapabilityDetector: Detect capabilities in parallel
        3. Repository: Create/update models

        Returns:
            Dict with added, updated, capability_updates, errors

        Raises:
            OllamaSyncError: If cannot connect to Ollama
        """
        added = 0
        updated = 0
        capability_updates = 0
        errors: list[str] = []

        # Phase 1: Fetch models from Ollama
        try:
            ollama_models = await self._ollama.get_raw_models()
        except OllamaConnectionError as e:
            raise OllamaSyncError(str(e)) from e
        except Exception as e:
            raise OllamaSyncError(f"Unexpected error: {e}") from e

        logger.info(f"Found {len(ollama_models)} models in Ollama")

        if not ollama_models:
            return {"added": 0, "updated": 0, "capability_updates": 0, "errors": errors}

        # Phase 2: Detect capabilities in parallel
        model_names = [m.get("name", "") for m in ollama_models if m.get("name")]
        logger.info(f"Detecting capabilities for {len(model_names)} models...")

        detected_capabilities = await self._detector.detect_batch(
            model_names,
            max_concurrent=5,
        )

        # Phase 3: Create/update models
        for model_data in ollama_models:
            model_id = model_data.get("name", "")
            if not model_id:
                continue

            try:
                existing = await self._repository.get_by_model_id(model_id)
                details = model_data.get("details", {})
                capabilities = detected_capabilities.get(model_id)

                if existing:
                    # Update existing
                    capability_updates += self._update_existing_model(
                        existing, details, capabilities
                    )
                    await self._repository.update(existing)
                    updated += 1
                else:
                    # Create new
                    new_model = AIModel.from_ollama_model(model_data)
                    self._apply_capabilities(new_model, capabilities)
                    await self._repository.create(new_model)
                    added += 1
                    logger.info(f"Added new Ollama model: {model_id}")

            except Exception as e:
                msg = f"Error processing model {model_id}: {e}"
                logger.warning(msg)
                errors.append(msg)

        logger.info(
            f"Ollama sync complete: {added} added, {updated} updated, "
            f"{capability_updates} capability changes, {len(errors)} errors"
        )

        return {
            "added": added,
            "updated": updated,
            "capability_updates": capability_updates,
            "errors": errors,
        }

    async def refresh_capabilities(
        self,
        model_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """Refresh capability detection for Ollama models.

        Args:
            model_ids: Specific models to refresh, or None for all

        Returns:
            Dict with updated, vision_detected, functions_detected
        """
        # Get models to refresh
        if model_ids:
            models = []
            for mid in model_ids:
                model = await self._repository.get_by_model_id(mid)
                if model and model.provider == "ollama":
                    models.append(model)
        else:
            models = await self._repository.find_all(provider="ollama")

        if not models:
            return {"updated": 0, "vision_detected": 0, "functions_detected": 0}

        # Detect capabilities
        model_names = [str(m.model_id) for m in models]
        detected = await self._detector.detect_batch(model_names, max_concurrent=5)

        # Apply updates
        updated = 0
        vision_detected = 0
        functions_detected = 0

        for model in models:
            caps = detected.get(str(model.model_id))
            if not caps:
                continue

            if caps.supports_vision:
                vision_detected += 1
            if caps.supports_functions:
                functions_detected += 1

            # Check if changed
            if (
                model.supports_vision != caps.supports_vision
                or model.supports_functions != caps.supports_functions
            ):
                model.supports_vision = caps.supports_vision  # type: ignore[assignment]
                model.supports_functions = caps.supports_functions  # type: ignore[assignment]
                model.capabilities = {  # type: ignore[assignment]
                    **(model.capabilities or {}),
                    "detection_method": caps.detection_method,
                    "raw_capabilities": caps.raw_capabilities,
                    "refreshed_at": datetime.now(UTC).isoformat(),
                }
                await self._repository.update(model)
                updated += 1

        logger.info(
            f"Capability refresh: {updated} updated, "
            f"{vision_detected} vision, {functions_detected} functions"
        )

        return {
            "updated": updated,
            "vision_detected": vision_detected,
            "functions_detected": functions_detected,
        }

    async def seed_external_models(self) -> dict[str, int]:
        """Seed external provider models from config.

        Delegates to ModelSeeder.

        Returns:
            Dict with added and skipped counts
        """
        return await self._seeder.seed_external_models()

    # =========================================================================
    # Bulk Operations (delegated to repository)
    # =========================================================================

    async def enable_models(self, model_ids: list[UUID]) -> int:
        """Enable multiple models."""
        return await self._repository.bulk_update_enabled(model_ids, enabled=True)

    async def disable_models(self, model_ids: list[UUID]) -> int:
        """Disable multiple models."""
        return await self._repository.bulk_update_enabled(model_ids, enabled=False)

    async def update_sort_order(self, model_orders: list[dict]) -> int:
        """Update sort order for multiple models."""
        return await self._repository.bulk_update_sort_order(model_orders)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _update_existing_model(
        self,
        model: AIModel,
        details: dict,
        capabilities: "CapabilityDetector | None",
    ) -> int:
        """Update existing model with new data.

        Args:
            model: Existing AIModel to update
            details: Details dict from Ollama
            capabilities: Detected capabilities

        Returns:
            1 if capabilities changed, 0 otherwise
        """
        from app.config.model_capabilities import ModelCapabilities

        model.family = details.get("family") or model.family
        model.parameter_size = details.get("parameter_size") or model.parameter_size
        model.quantization_level = details.get("quantization_level") or model.quantization_level
        model.last_synced_at = datetime.now(UTC)

        capability_changed = 0
        if capabilities and isinstance(capabilities, ModelCapabilities):
            if (
                model.supports_vision != capabilities.supports_vision
                or model.supports_functions != capabilities.supports_functions
            ):
                capability_changed = 1

            model.supports_vision = capabilities.supports_vision  # type: ignore[assignment]
            model.supports_functions = capabilities.supports_functions  # type: ignore[assignment]
            model.capabilities = {  # type: ignore[assignment]
                **(model.capabilities or {}),
                "families": details.get("families", []),
                "detection_method": capabilities.detection_method,
                "raw_capabilities": capabilities.raw_capabilities,
            }

        return capability_changed

    def _apply_capabilities(
        self,
        model: AIModel,
        capabilities: "CapabilityDetector | None",
    ) -> None:
        """Apply detected capabilities to a new model.

        Args:
            model: New AIModel
            capabilities: Detected capabilities
        """
        from app.config.model_capabilities import ModelCapabilities

        if capabilities and isinstance(capabilities, ModelCapabilities):
            model.supports_vision = capabilities.supports_vision  # type: ignore[assignment]
            model.supports_functions = capabilities.supports_functions  # type: ignore[assignment]
            model.capabilities = {  # type: ignore[assignment]
                **(model.capabilities or {}),
                "detection_method": capabilities.detection_method,
                "raw_capabilities": capabilities.raw_capabilities,
            }
