"""
Demo Repository Implementation

SQLAlchemy implementation of demo repository for Excelencia ERP.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import cast

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.excelencia.application.ports import IDemoRepository
from app.domains.excelencia.domain.entities.demo import (
    Demo,
    DemoRequest,
    DemoStatus,
    DemoType,
)
from app.domains.excelencia.infrastructure.persistence.sqlalchemy.models import (
    DemoModel,
)

logger = logging.getLogger(__name__)


class SQLAlchemyDemoRepository(IDemoRepository):
    """
    SQLAlchemy implementation of IDemoRepository.

    Handles all demo data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def save(self, demo: Demo) -> Demo:
        """Save or update a demo."""
        # Try to find existing by entity ID
        existing_model = None
        if demo.id.startswith("demo-"):
            try:
                int_id = int(demo.id.replace("demo-", ""))
                result = await self.session.execute(
                    select(DemoModel).where(DemoModel.id == int_id)
                )
                existing_model = result.scalar_one_or_none()
            except ValueError:
                pass

        if existing_model:
            # Update existing
            self._update_model(existing_model, demo)
            model = existing_model
        else:
            # Create new
            model = self._to_model(demo)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        logger.info(f"Saved demo: demo-{model.id:03d} for {model.company_name}")
        return self._to_entity(model)

    async def get_by_id(self, demo_id: str) -> Demo | None:
        """Get demo by ID."""
        # ID in entity is string like 'demo-001', DB uses integer
        try:
            int_id = int(demo_id.replace("demo-", "")) if demo_id.startswith("demo-") else int(demo_id)
            result = await self.session.execute(
                select(DemoModel).where(DemoModel.id == int_id)
            )
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None
        except ValueError:
            return None

    async def get_pending(self) -> list[Demo]:
        """Get all pending demos."""
        result = await self.session.execute(
            select(DemoModel).where(DemoModel.status == DemoStatus.PENDING.value)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_status(self, status: DemoStatus) -> list[Demo]:
        """Get demos by status."""
        result = await self.session.execute(
            select(DemoModel).where(DemoModel.status == status.value)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_date_range(self, start: datetime, end: datetime) -> list[Demo]:
        """Get demos scheduled in date range."""
        result = await self.session.execute(
            select(DemoModel).where(
                and_(
                    DemoModel.scheduled_at >= start,
                    DemoModel.scheduled_at <= end,
                    DemoModel.scheduled_at.isnot(None),
                )
            )
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def delete(self, demo_id: str) -> bool:
        """Delete a demo."""
        try:
            int_id = int(demo_id.replace("demo-", "")) if demo_id.startswith("demo-") else int(demo_id)
            result = await self.session.execute(
                select(DemoModel).where(DemoModel.id == int_id)
            )
            model = result.scalar_one_or_none()

            if model:
                await self.session.delete(model)
                await self.session.commit()
                logger.info(f"Deleted demo: {demo_id}")
                return True
            return False
        except ValueError:
            return False

    async def get_all(self) -> list[Demo]:
        """Get all demos."""
        result = await self.session.execute(select(DemoModel))
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count(self) -> int:
        """Get total demo count."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).select_from(DemoModel)
        )
        return result.scalar_one()

    async def count_by_status(self, status: DemoStatus) -> int:
        """Count demos by status."""
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).where(DemoModel.status == status.value)
        )
        return result.scalar_one()

    async def get_by_email(self, email: str) -> list[Demo]:
        """Get demos by contact email."""
        result = await self.session.execute(
            select(DemoModel).where(DemoModel.contact_email == email)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def get_by_company(self, company_name: str) -> list[Demo]:
        """Get demos by company name."""
        result = await self.session.execute(
            select(DemoModel).where(DemoModel.company_name.ilike(f"%{company_name}%"))
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    # Mapping methods

    def _to_entity(self, model: DemoModel) -> Demo:
        """Convert model to entity."""
        # Cast SQLAlchemy Column types to Python types
        company_name = cast(str, model.company_name)
        contact_name = cast(str, model.contact_name)
        contact_email = cast(str, model.contact_email)
        contact_phone = cast(str | None, model.contact_phone)
        modules_of_interest = cast(list[str] | None, model.modules_of_interest) or []
        demo_type_str = cast(str | None, model.demo_type)
        request_notes = cast(str | None, model.request_notes) or ""
        scheduled_at = cast(datetime | None, model.scheduled_at)
        duration_minutes = cast(int | None, model.duration_minutes) or 60
        status_str = cast(str, model.status)
        assigned_to = cast(str | None, model.assigned_to)
        meeting_link = cast(str | None, model.meeting_link)
        created_at = cast(datetime, model.created_at)
        updated_at = cast(datetime, model.updated_at)
        model_id = cast(int, model.id)

        # Reconstruct DemoRequest value object
        request = DemoRequest(
            company_name=company_name,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            modules_of_interest=modules_of_interest,
            demo_type=DemoType(demo_type_str) if demo_type_str else DemoType.GENERAL,
            notes=request_notes,
        )

        return Demo(
            id=f"demo-{model_id:03d}",
            request=request,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            status=DemoStatus(status_str),
            assigned_to=assigned_to,
            meeting_link=meeting_link,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_model(self, demo: Demo) -> DemoModel:
        """Convert entity to model."""
        return DemoModel(
            company_name=demo.request.company_name,
            contact_name=demo.request.contact_name,
            contact_email=demo.request.contact_email,
            contact_phone=demo.request.contact_phone,
            modules_of_interest=demo.request.modules_of_interest,
            demo_type=demo.request.demo_type.value,
            request_notes=demo.request.notes,
            scheduled_at=demo.scheduled_at,
            duration_minutes=demo.duration_minutes,
            status=demo.status.value,
            assigned_to=demo.assigned_to,
            meeting_link=demo.meeting_link,
        )

    def _update_model(self, model: DemoModel, demo: Demo) -> None:
        """Update model from entity."""
        # Update request information
        model.company_name = demo.request.company_name  # type: ignore[assignment]
        model.contact_name = demo.request.contact_name  # type: ignore[assignment]
        model.contact_email = demo.request.contact_email  # type: ignore[assignment]
        model.contact_phone = demo.request.contact_phone  # type: ignore[assignment]
        model.modules_of_interest = demo.request.modules_of_interest  # type: ignore[assignment]
        model.demo_type = demo.request.demo_type.value  # type: ignore[assignment]
        model.request_notes = demo.request.notes  # type: ignore[assignment]

        # Update scheduling information
        model.scheduled_at = demo.scheduled_at  # type: ignore[assignment]
        model.duration_minutes = demo.duration_minutes  # type: ignore[assignment]
        model.status = demo.status.value  # type: ignore[assignment]
        model.assigned_to = demo.assigned_to  # type: ignore[assignment]
        model.meeting_link = demo.meeting_link  # type: ignore[assignment]


# Keep backward compatibility alias
InMemoryDemoRepository = SQLAlchemyDemoRepository
