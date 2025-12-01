"""
Update Demo Use Case

Updates an existing demo.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.application.ports import IDemoRepository
from app.domains.excelencia.domain.entities.demo import DemoRequest, DemoStatus, DemoType

logger = logging.getLogger(__name__)


class UpdateDemoUseCase:
    """
    Use Case: Update an existing demo.

    Single Responsibility: Validate and update demo data.
    """

    def __init__(self, repository: IDemoRepository):
        """Initialize with repository."""
        self.repository = repository

    async def execute(
        self,
        demo_id: str,
        update_data: dict,
    ) -> dict | None:
        """
        Execute the use case.

        Args:
            demo_id: Demo ID to update
            update_data: Fields to update

        Returns:
            Updated demo as dict, or None if not found

        Raises:
            ValueError: If invalid data provided
        """
        logger.info(f"Updating demo: {demo_id}")

        # Get existing demo
        demo = await self.repository.get_by_id(demo_id)
        if not demo:
            logger.warning(f"Demo not found: {demo_id}")
            return None

        # Update request fields
        request = demo.request
        if "company_name" in update_data and update_data["company_name"]:
            request = DemoRequest(
                company_name=update_data["company_name"],
                contact_name=request.contact_name,
                contact_email=request.contact_email,
                contact_phone=request.contact_phone,
                modules_of_interest=request.modules_of_interest,
                demo_type=request.demo_type,
                notes=request.notes,
            )
            demo.request = request

        if "contact_name" in update_data and update_data["contact_name"]:
            demo.request = DemoRequest(
                company_name=demo.request.company_name,
                contact_name=update_data["contact_name"],
                contact_email=demo.request.contact_email,
                contact_phone=demo.request.contact_phone,
                modules_of_interest=demo.request.modules_of_interest,
                demo_type=demo.request.demo_type,
                notes=demo.request.notes,
            )

        if "contact_email" in update_data and update_data["contact_email"]:
            demo.request = DemoRequest(
                company_name=demo.request.company_name,
                contact_name=demo.request.contact_name,
                contact_email=update_data["contact_email"],
                contact_phone=demo.request.contact_phone,
                modules_of_interest=demo.request.modules_of_interest,
                demo_type=demo.request.demo_type,
                notes=demo.request.notes,
            )

        if "contact_phone" in update_data:
            demo.request = DemoRequest(
                company_name=demo.request.company_name,
                contact_name=demo.request.contact_name,
                contact_email=demo.request.contact_email,
                contact_phone=update_data["contact_phone"],
                modules_of_interest=demo.request.modules_of_interest,
                demo_type=demo.request.demo_type,
                notes=demo.request.notes,
            )

        if "modules_of_interest" in update_data:
            demo.request = DemoRequest(
                company_name=demo.request.company_name,
                contact_name=demo.request.contact_name,
                contact_email=demo.request.contact_email,
                contact_phone=demo.request.contact_phone,
                modules_of_interest=update_data["modules_of_interest"] or [],
                demo_type=demo.request.demo_type,
                notes=demo.request.notes,
            )

        if "demo_type" in update_data and update_data["demo_type"]:
            try:
                demo_type = DemoType(update_data["demo_type"])
                demo.request = DemoRequest(
                    company_name=demo.request.company_name,
                    contact_name=demo.request.contact_name,
                    contact_email=demo.request.contact_email,
                    contact_phone=demo.request.contact_phone,
                    modules_of_interest=demo.request.modules_of_interest,
                    demo_type=demo_type,
                    notes=demo.request.notes,
                )
            except ValueError as e:
                raise ValueError(f"Invalid demo_type: {update_data['demo_type']}") from e

        if "request_notes" in update_data:
            demo.request = DemoRequest(
                company_name=demo.request.company_name,
                contact_name=demo.request.contact_name,
                contact_email=demo.request.contact_email,
                contact_phone=demo.request.contact_phone,
                modules_of_interest=demo.request.modules_of_interest,
                demo_type=demo.request.demo_type,
                notes=update_data["request_notes"] or "",
            )

        # Update demo fields
        if "scheduled_at" in update_data:
            demo.scheduled_at = update_data["scheduled_at"]

        if "duration_minutes" in update_data and update_data["duration_minutes"]:
            demo.duration_minutes = update_data["duration_minutes"]

        if "assigned_to" in update_data:
            demo.assigned_to = update_data["assigned_to"]

        if "meeting_link" in update_data:
            demo.meeting_link = update_data["meeting_link"]

        if "status" in update_data and update_data["status"]:
            try:
                demo.status = DemoStatus(update_data["status"])
            except ValueError as e:
                raise ValueError(f"Invalid status: {update_data['status']}") from e

        # Update timestamp
        demo.updated_at = datetime.now(UTC)

        # Persist
        saved_demo = await self.repository.save(demo)
        logger.info(f"Demo updated: {saved_demo.id}")

        # Return flattened dict
        result = saved_demo.to_dict()
        request_data = result.pop("request", {})
        result.update(request_data)
        return result
