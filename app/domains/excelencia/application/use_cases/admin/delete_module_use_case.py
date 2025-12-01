"""
Delete Module Use Case

Deletes an ERP module (soft or hard delete).
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.application.ports import IModuleRepository
from app.domains.excelencia.domain.entities.module import ModuleStatus

logger = logging.getLogger(__name__)


class DeleteModuleUseCase:
    """
    Use Case: Delete an ERP module.

    Single Responsibility: Handle module deletion (soft or hard).
    """

    def __init__(self, repository: IModuleRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        module_id: str,
        soft_delete: bool = True,
    ) -> bool:
        """
        Execute the use case.

        Args:
            module_id: Module ID or code to delete
            soft_delete: If True, mark as deprecated. If False, permanently delete.

        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting module: {module_id}, soft_delete={soft_delete}")

        # Get existing module
        module = await self.repository.get_by_id(module_id)
        if not module:
            # Try by code
            module = await self.repository.get_by_code(module_id)

        if not module:
            logger.warning(f"Module not found for deletion: {module_id}")
            return False

        if soft_delete:
            # Soft delete: mark as deprecated
            module.status = ModuleStatus.DEPRECATED
            module.updated_at = datetime.now(UTC)
            await self.repository.save(module)
            logger.info(f"Module soft-deleted (deprecated): {module_id}")
        else:
            # Hard delete: permanently remove
            success = await self.repository.delete(module.id)
            if not success:
                # Try deleting by code
                success = await self.repository.delete(module.code)
            logger.info(f"Module hard-deleted: {module_id}, success={success}")
            return success

        return True
