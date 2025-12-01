"""
List Modules Use Case

Lists all ERP modules with optional filtering.
"""

import logging
import math
from dataclasses import dataclass

from app.domains.excelencia.application.ports import IModuleRepository
from app.domains.excelencia.domain.entities.module import ModuleCategory, ModuleStatus

logger = logging.getLogger(__name__)


@dataclass
class ListModulesResult:
    """Result of listing modules."""

    modules: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class ListModulesUseCase:
    """
    Use Case: List all ERP modules with optional filtering.

    Single Responsibility: Retrieve and filter module list.
    """

    def __init__(self, repository: IModuleRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ListModulesResult:
        """
        Execute the use case.

        Args:
            category: Filter by category
            status: Filter by status
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ListModulesResult with paginated modules
        """
        logger.info(f"Listing modules - category={category}, status={status}, page={page}")

        # Get all modules
        if category:
            try:
                cat_enum = ModuleCategory(category)
                modules = await self.repository.get_by_category(cat_enum)
            except ValueError:
                logger.warning(f"Invalid category: {category}")
                modules = []
        else:
            modules = await self.repository.get_all()

        # Filter by status if provided
        if status:
            try:
                status_enum = ModuleStatus(status)
                modules = [m for m in modules if m.status == status_enum]
            except ValueError:
                logger.warning(f"Invalid status: {status}")

        # Calculate pagination
        total = len(modules)
        total_pages = max(1, math.ceil(total / page_size))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_modules = modules[start_idx:end_idx]

        # Convert to dicts
        module_dicts = [m.to_dict() for m in paginated_modules]

        return ListModulesResult(
            modules=module_dicts,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
