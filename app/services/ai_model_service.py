# ============================================================================
# SCOPE: GLOBAL
# Description: Servicio coordinador para gestión de modelos de IA. Orquesta
#              operaciones entre Repository, CapabilityDetector y ModelSeeder
#              siguiendo Single Responsibility Principle.
# Tenant-Aware: No - modelos son globales, visibilidad controlada por is_enabled.
# ============================================================================
"""
AI Model Service - Thin coordinator for AI model operations.

Orchestrates operations between specialized services:
- AIModelRepository: Data persistence
- CapabilityDetector: Capability detection (pattern-based)
- ModelSeeder: External model seeding

Single Responsibility: Coordinate and orchestrate model operations.
No direct DB access, no HTTP calls - delegates to specialized services.

Usage:
    # With explicit dependencies
    service = AIModelService(repository, detector, seeder)

    # Or use factory with just DB session
    service = AIModelService.with_session(db)

    models = await service.list_models()
    result = await service.seed_external_models()
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
        capability_detector: CapabilityDetector,
        seeder: ModelSeeder,
    ) -> None:
        """Initialize service with dependencies.

        Args:
            repository: AIModelRepository for data access
            capability_detector: CapabilityDetector for capability detection
            seeder: ModelSeeder for seeding external models
        """
        self._repository = repository
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
        detector = CapabilityDetector()
        seeder = ModelSeeder(repository)

        return cls(
            repository=repository,
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
    # Capability Operations
    # =========================================================================

    async def refresh_capabilities(
        self,
        model_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """Refresh capability detection for models using pattern matching.

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
                if model:
                    models.append(model)
        else:
            models = await self._repository.find_all()

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

    def _apply_capabilities(
        self,
        model: AIModel,
        capabilities: "CapabilityDetector | None",
    ) -> None:
        """Apply detected capabilities to a model.

        Args:
            model: AIModel to update
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
