"""
List Demos Use Case

Lists all demos with optional filtering.
"""

import logging
import math
from dataclasses import dataclass

from app.domains.excelencia.application.ports import IDemoRepository
from app.domains.excelencia.domain.entities.demo import DemoStatus

logger = logging.getLogger(__name__)


@dataclass
class ListDemosResult:
    """Result of listing demos."""

    demos: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class ListDemosUseCase:
    """
    Use Case: List all demos with optional filtering.

    Single Responsibility: Retrieve and filter demo list.
    """

    def __init__(self, repository: IDemoRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        status: str | None = None,
        company: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ListDemosResult:
        """
        Execute the use case.

        Args:
            status: Filter by status
            company: Filter by company name
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ListDemosResult with paginated demos
        """
        logger.info(f"Listing demos - status={status}, company={company}, page={page}")

        # Get demos based on filters
        if status:
            try:
                status_enum = DemoStatus(status)
                demos = await self.repository.get_by_status(status_enum)
            except ValueError:
                logger.warning(f"Invalid status: {status}")
                demos = []
        elif company:
            demos = await self.repository.get_by_company(company)
        else:
            demos = await self.repository.get_all()

        # Calculate pagination
        total = len(demos)
        total_pages = max(1, math.ceil(total / page_size))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_demos = demos[start_idx:end_idx]

        # Convert to dicts with flattened request
        demo_dicts = []
        for demo in paginated_demos:
            demo_dict = demo.to_dict()
            # Flatten request into main dict for API response
            request_data = demo_dict.pop("request", {})
            demo_dict.update(request_data)
            demo_dicts.append(demo_dict)

        return ListDemosResult(
            demos=demo_dicts,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
