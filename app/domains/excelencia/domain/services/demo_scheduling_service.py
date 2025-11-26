"""
Demo Scheduling Service

Domain service for demo scheduling business logic.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.domains.excelencia.domain.entities.demo import Demo, DemoRequest, DemoStatus


class IDemoRepository(Protocol):
    """Interface for demo repository"""

    async def save(self, demo: Demo) -> Demo: ...
    async def get_by_id(self, demo_id: str) -> Demo | None: ...
    async def get_pending(self) -> list[Demo]: ...
    async def get_by_status(self, status: DemoStatus) -> list[Demo]: ...
    async def get_by_date_range(self, start: datetime, end: datetime) -> list[Demo]: ...


class DemoSchedulingService:
    """
    Domain service for demo scheduling logic.

    Single Responsibility: Handle demo scheduling workflow.
    """

    def __init__(self, repository: IDemoRepository):
        self._repository = repository

    async def request_demo(self, request: DemoRequest) -> Demo:
        """
        Create a new demo request.

        Args:
            request: Demo request details

        Returns:
            Created demo entity
        """
        demo = Demo(
            id=str(uuid4()),
            request=request,
            status=DemoStatus.PENDING,
        )
        return await self._repository.save(demo)

    async def schedule_demo(
        self,
        demo_id: str,
        scheduled_at: datetime,
        assigned_to: str,
        meeting_link: str | None = None,
    ) -> Demo | None:
        """
        Schedule a pending demo.

        Args:
            demo_id: Demo ID to schedule
            scheduled_at: Scheduled date and time
            assigned_to: Sales rep assigned
            meeting_link: Virtual meeting link

        Returns:
            Updated demo or None if not found
        """
        demo = await self._repository.get_by_id(demo_id)
        if not demo:
            return None

        if not demo.is_pending():
            raise ValueError(f"Demo {demo_id} cannot be scheduled (status: {demo.status})")

        demo.schedule(scheduled_at, assigned_to, meeting_link)
        return await self._repository.save(demo)

    async def complete_demo(self, demo_id: str) -> Demo | None:
        """Mark a demo as completed"""
        demo = await self._repository.get_by_id(demo_id)
        if not demo:
            return None

        demo.complete()
        return await self._repository.save(demo)

    async def cancel_demo(self, demo_id: str) -> Demo | None:
        """Cancel a demo"""
        demo = await self._repository.get_by_id(demo_id)
        if not demo:
            return None

        demo.cancel()
        return await self._repository.save(demo)

    async def get_pending_demos(self) -> list[Demo]:
        """Get all pending demo requests"""
        return await self._repository.get_pending()

    async def get_upcoming_demos(self, days: int = 7) -> list[Demo]:
        """Get demos scheduled in the next N days"""
        now = datetime.now(UTC)
        end = now + timedelta(days=days)
        demos = await self._repository.get_by_date_range(now, end)
        return [d for d in demos if d.is_scheduled()]

    def generate_confirmation_message(self, demo: Demo) -> str:
        """Generate confirmation message for scheduled demo"""
        if not demo.scheduled_at:
            return "La demo aun no ha sido agendada."

        scheduled_str = demo.scheduled_at.strftime("%d/%m/%Y a las %H:%M")
        lines = [
            f"Demo confirmada para {demo.request.company_name}",
            f"Fecha: {scheduled_str}",
            f"Duracion: {demo.duration_minutes} minutos",
            f"Contacto: {demo.request.contact_name}",
        ]

        if demo.meeting_link:
            lines.append(f"Link: {demo.meeting_link}")

        if demo.request.modules_of_interest:
            lines.append(f"Modulos: {', '.join(demo.request.modules_of_interest)}")

        return "\n".join(lines)
