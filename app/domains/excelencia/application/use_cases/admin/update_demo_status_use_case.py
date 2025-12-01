"""
Update Demo Status Use Case

Updates only the status of a demo.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.application.ports import IDemoRepository
from app.domains.excelencia.domain.entities.demo import DemoStatus

logger = logging.getLogger(__name__)


class UpdateDemoStatusUseCase:
    """
    Use Case: Update demo status only.

    Single Responsibility: Handle status transitions for demos.
    """

    def __init__(self, repository: IDemoRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        demo_id: str,
        new_status: str,
        notes: str | None = None,
    ) -> dict | None:
        """
        Execute the use case.

        Args:
            demo_id: Demo ID to update
            new_status: New status value
            notes: Optional notes about the status change

        Returns:
            Updated demo as dict, or None if not found

        Raises:
            ValueError: If invalid status provided
        """
        logger.info(f"Updating demo status: {demo_id} -> {new_status}")

        # Get existing demo
        demo = await self.repository.get_by_id(demo_id)
        if not demo:
            logger.warning(f"Demo not found: {demo_id}")
            return None

        # Validate and set status
        try:
            status_enum = DemoStatus(new_status)
        except ValueError as e:
            raise ValueError(f"Invalid status: {new_status}") from e

        old_status = demo.status
        demo.status = status_enum
        demo.updated_at = datetime.now(UTC)

        # If notes provided, append to request notes
        if notes:
            current_notes = demo.request.notes or ""
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
            status_note = f"\n[{timestamp}] Status: {old_status.value} -> {new_status}: {notes}"
            # Create new request with updated notes
            from app.domains.excelencia.domain.entities.demo import DemoRequest

            demo.request = DemoRequest(
                company_name=demo.request.company_name,
                contact_name=demo.request.contact_name,
                contact_email=demo.request.contact_email,
                contact_phone=demo.request.contact_phone,
                modules_of_interest=demo.request.modules_of_interest,
                demo_type=demo.request.demo_type,
                notes=current_notes + status_note,
            )

        # Persist
        saved_demo = await self.repository.save(demo)
        logger.info(f"Demo status updated: {saved_demo.id} -> {new_status}")

        # Return flattened dict
        result = saved_demo.to_dict()
        request_data = result.pop("request", {})
        result.update(request_data)
        return result
