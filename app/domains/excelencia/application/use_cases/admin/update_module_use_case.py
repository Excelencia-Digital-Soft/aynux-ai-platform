"""
Update Module Use Case

Updates an existing ERP module.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.application.ports import IModuleRepository
from app.domains.excelencia.domain.entities.module import ModuleCategory, ModuleStatus

logger = logging.getLogger(__name__)


class UpdateModuleUseCase:
    """
    Use Case: Update an existing ERP module.

    Single Responsibility: Validate and update module data.
    """

    def __init__(self, repository: IModuleRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        module_id: str,
        update_data: dict,
    ) -> dict | None:
        """
        Execute the use case.

        Args:
            module_id: Module ID or code to update
            update_data: Fields to update

        Returns:
            Updated module as dict, or None if not found

        Raises:
            ValueError: If invalid data provided
        """
        logger.info(f"Updating module: {module_id}")

        # Get existing module
        module = await self.repository.get_by_id(module_id)
        if not module:
            # Try by code
            module = await self.repository.get_by_code(module_id)

        if not module:
            logger.warning(f"Module not found: {module_id}")
            return None

        # Update fields
        if "name" in update_data and update_data["name"]:
            module.name = update_data["name"]

        if "description" in update_data:
            module.description = update_data["description"] or ""

        if "category" in update_data and update_data["category"]:
            try:
                module.category = ModuleCategory(update_data["category"])
            except ValueError as e:
                raise ValueError(f"Invalid category: {update_data['category']}") from e

        if "status" in update_data and update_data["status"]:
            try:
                module.status = ModuleStatus(update_data["status"])
            except ValueError as e:
                raise ValueError(f"Invalid status: {update_data['status']}") from e

        if "features" in update_data:
            module.features = update_data["features"] or []

        if "pricing_tier" in update_data and update_data["pricing_tier"]:
            module.pricing_tier = update_data["pricing_tier"]

        # Update timestamp
        module.updated_at = datetime.now(UTC)

        # Persist
        saved_module = await self.repository.save(module)
        logger.info(f"Module updated: {saved_module.id}")

        return saved_module.to_dict()
