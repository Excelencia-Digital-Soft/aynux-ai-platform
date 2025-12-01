"""
Schedule Demo Use Case (Admin)

Schedules a demo with full control over parameters.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.application.ports import IDemoRepository
from app.domains.excelencia.domain.entities.demo import DemoStatus

logger = logging.getLogger(__name__)


class ScheduleDemoAdminUseCase:
    """
    Use Case: Schedule a demo (admin version).

    Single Responsibility: Handle demo scheduling with full parameter control.
    """

    def __init__(self, repository: IDemoRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        demo_id: str,
        scheduled_at: datetime,
        assigned_to: str,
        duration_minutes: int = 60,
        meeting_link: str | None = None,
    ) -> dict | None:
        """
        Execute the use case.

        Args:
            demo_id: Demo ID to schedule
            scheduled_at: Scheduled date and time
            assigned_to: Sales rep to assign
            duration_minutes: Demo duration in minutes
            meeting_link: Optional meeting URL

        Returns:
            Updated demo as dict, or None if not found
        """
        logger.info(f"Scheduling demo: {demo_id} for {scheduled_at}")

        # Get existing demo
        demo = await self.repository.get_by_id(demo_id)
        if not demo:
            logger.warning(f"Demo not found: {demo_id}")
            return None

        # Use domain method to schedule
        demo.schedule(
            scheduled_at=scheduled_at,
            assigned_to=assigned_to,
            meeting_link=meeting_link,
        )

        # Override duration if different from default
        if duration_minutes != 60:
            demo.duration_minutes = duration_minutes

        # Ensure status is scheduled
        demo.status = DemoStatus.SCHEDULED
        demo.updated_at = datetime.now(UTC)

        # Persist
        saved_demo = await self.repository.save(demo)
        logger.info(f"Demo scheduled: {saved_demo.id} at {scheduled_at}")

        # Return flattened dict
        result = saved_demo.to_dict()
        request_data = result.pop("request", {})
        result.update(request_data)
        return result
