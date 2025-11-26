"""
Demo Repository Implementation

In-memory implementation of demo repository for Excelencia ERP.
Can be replaced with SQLAlchemy implementation when database is needed.
"""

import logging
from datetime import UTC, datetime

from app.domains.excelencia.domain.entities.demo import Demo, DemoStatus

logger = logging.getLogger(__name__)


class InMemoryDemoRepository:
    """
    In-memory implementation of IDemoRepository.

    Stores demo requests in memory. For production use,
    replace with SQLAlchemy or other persistent storage.
    """

    def __init__(self):
        self._demos: dict[str, Demo] = {}

    async def save(self, demo: Demo) -> Demo:
        """Save a demo"""
        demo.updated_at = datetime.now(UTC)
        self._demos[demo.id] = demo
        logger.info(f"Saved demo: {demo.id} for {demo.request.company_name}")
        return demo

    async def get_by_id(self, demo_id: str) -> Demo | None:
        """Get demo by ID"""
        return self._demos.get(demo_id)

    async def get_pending(self) -> list[Demo]:
        """Get all pending demos"""
        return [d for d in self._demos.values() if d.status == DemoStatus.PENDING]

    async def get_by_status(self, status: DemoStatus) -> list[Demo]:
        """Get demos by status"""
        return [d for d in self._demos.values() if d.status == status]

    async def get_by_date_range(self, start: datetime, end: datetime) -> list[Demo]:
        """Get demos scheduled in date range"""
        result = []
        for demo in self._demos.values():
            if demo.scheduled_at and start <= demo.scheduled_at <= end:
                result.append(demo)
        return result

    async def delete(self, demo_id: str) -> bool:
        """Delete a demo"""
        if demo_id in self._demos:
            del self._demos[demo_id]
            logger.info(f"Deleted demo: {demo_id}")
            return True
        return False

    async def get_all(self) -> list[Demo]:
        """Get all demos"""
        return list(self._demos.values())
