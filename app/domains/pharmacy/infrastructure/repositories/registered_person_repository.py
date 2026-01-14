"""
RegisteredPerson Repository Implementation.

SQLAlchemy async repository for managing registered persons in the pharmacy flow.
Handles CRUD operations for locally cached authorized persons with 180-day expiration.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.tenancy.registered_person import RegisteredPerson

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

logger = logging.getLogger(__name__)


class RegisteredPersonRepository:
    """
    Repository for RegisteredPerson entity operations.

    Handles all database operations for registered persons including:
    - Finding valid (non-expired, active) registrations by phone
    - Creating/updating registrations with upsert logic
    - Marking registrations as used (which renews expiration)
    - Deactivating expired registrations for cleanup
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy async session
        """
        self._db = db

    async def get_valid_by_phone(
        self,
        phone_number: str,
        pharmacy_id: UUID,
    ) -> list[RegisteredPerson]:
        """
        Get all valid (non-expired, active) registrations for a phone number.

        Results are ordered with is_self=True first, then by most recently used.

        Args:
            phone_number: WhatsApp phone number
            pharmacy_id: Pharmacy UUID for multi-tenant isolation

        Returns:
            List of valid RegisteredPerson entities, ordered by priority
        """
        now = datetime.now(UTC)
        stmt = (
            select(RegisteredPerson)
            .where(
                and_(
                    RegisteredPerson.phone_number == phone_number,
                    RegisteredPerson.pharmacy_id == pharmacy_id,
                    RegisteredPerson.is_active.is_(True),  # type: ignore[union-attr]
                    cast("ColumnElement[bool]", RegisteredPerson.expires_at > now),
                )
            )
            .order_by(
                RegisteredPerson.is_self.desc(),
                RegisteredPerson.last_used_at.desc().nulls_last(),  # type: ignore[attr-defined]
            )
        )

        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_dni(
        self,
        dni: str,
        pharmacy_id: UUID,
    ) -> RegisteredPerson | None:
        """
        Find registration by DNI (regardless of phone).

        Returns active registration only.

        Args:
            dni: Document number
            pharmacy_id: Pharmacy UUID for multi-tenant isolation

        Returns:
            RegisteredPerson if found and active, None otherwise
        """
        stmt = select(RegisteredPerson).where(
            and_(
                RegisteredPerson.dni == dni,
                RegisteredPerson.pharmacy_id == pharmacy_id,
                RegisteredPerson.is_active.is_(True),  # type: ignore[union-attr]
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_phone_and_dni(
        self,
        phone_number: str,
        dni: str,
        pharmacy_id: UUID,
    ) -> RegisteredPerson | None:
        """
        Find registration by phone number and DNI.

        Args:
            phone_number: WhatsApp phone number
            dni: Document number
            pharmacy_id: Pharmacy UUID

        Returns:
            RegisteredPerson if found, None otherwise
        """
        stmt = select(RegisteredPerson).where(
            and_(
                RegisteredPerson.phone_number == phone_number,
                RegisteredPerson.dni == dni,
                RegisteredPerson.pharmacy_id == pharmacy_id,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_id(self, registration_id: UUID) -> RegisteredPerson | None:
        """
        Find registration by ID.

        Args:
            registration_id: Registration UUID

        Returns:
            RegisteredPerson if found, None otherwise
        """
        stmt = select(RegisteredPerson).where(RegisteredPerson.id == registration_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, registration: RegisteredPerson) -> RegisteredPerson:
        """
        Create or update registration.

        If a registration exists for the same phone+dni+pharmacy, updates it.
        Otherwise creates a new registration.

        Args:
            registration: RegisteredPerson to save

        Returns:
            Saved RegisteredPerson with updated fields
        """
        existing = await self.find_by_phone_and_dni(
            phone_number=str(registration.phone_number),
            dni=str(registration.dni),
            pharmacy_id=registration.pharmacy_id,  # type: ignore
        )

        if existing:
            # Update existing registration
            existing.name = registration.name
            existing.plex_customer_id = registration.plex_customer_id
            existing.is_self = registration.is_self
            existing.is_active = True
            existing.mark_used()  # Refresh expiration
            await self._db.commit()
            await self._db.refresh(existing)
            logger.info(f"Updated registered person: {existing.dni} for phone {existing.phone_number}")
            return existing

        # Create new registration
        try:
            self._db.add(registration)
            await self._db.commit()
            await self._db.refresh(registration)
            logger.info(f"Created registered person: {registration.dni} for phone {registration.phone_number}")
            return registration
        except IntegrityError as e:
            await self._db.rollback()
            # Handle race condition - try to fetch existing
            if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                existing = await self.find_by_phone_and_dni(
                    phone_number=str(registration.phone_number),
                    dni=str(registration.dni),
                    pharmacy_id=registration.pharmacy_id,  # type: ignore
                )
                if existing:
                    logger.info(f"Found existing after race condition: {existing.dni}")
                    return existing
            logger.error(f"Failed to create registered person: {e}")
            raise

    async def mark_used(self, registration_id: UUID) -> bool:
        """
        Mark registration as used, renewing its expiration.

        Args:
            registration_id: Registration UUID

        Returns:
            True if registration was found and updated, False otherwise
        """
        registration = await self.find_by_id(registration_id)
        if registration:
            registration.mark_used()
            await self._db.commit()
            logger.debug(f"Marked registration as used: {registration_id}")
            return True
        return False

    async def deactivate(self, registration_id: UUID) -> bool:
        """
        Soft-delete a registration.

        Args:
            registration_id: Registration UUID

        Returns:
            True if registration was found and deactivated, False otherwise
        """
        registration = await self.find_by_id(registration_id)
        if registration:
            registration.deactivate()
            await self._db.commit()
            logger.info(f"Deactivated registration: {registration_id}")
            return True
        return False

    async def deactivate_expired(self, pharmacy_id: UUID) -> int:
        """
        Deactivate all expired registrations for a pharmacy.

        This is a housekeeping operation that should be run periodically.

        Args:
            pharmacy_id: Pharmacy UUID

        Returns:
            Number of registrations deactivated
        """
        now = datetime.now(UTC)
        stmt = (
            update(RegisteredPerson)
            .where(
                and_(
                    RegisteredPerson.pharmacy_id == pharmacy_id,
                    RegisteredPerson.is_active.is_(True),  # type: ignore[union-attr]
                    cast("ColumnElement[bool]", RegisteredPerson.expires_at <= now),
                )
            )
            .values(is_active=False)
        )

        result = await self._db.execute(stmt)
        await self._db.commit()

        count = getattr(result, "rowcount", 0) or 0
        if count > 0:
            logger.info(f"Deactivated {count} expired registrations for pharmacy {pharmacy_id}")
        return count

    async def count_by_phone(
        self,
        phone_number: str,
        pharmacy_id: UUID,
        include_expired: bool = False,
    ) -> int:
        """
        Count registrations for a phone number.

        Args:
            phone_number: WhatsApp phone number
            pharmacy_id: Pharmacy UUID
            include_expired: Whether to include expired registrations

        Returns:
            Number of registrations
        """
        from sqlalchemy import func

        conditions: list[ColumnElement[bool]] = [
            cast("ColumnElement[bool]", RegisteredPerson.phone_number == phone_number),
            cast("ColumnElement[bool]", RegisteredPerson.pharmacy_id == pharmacy_id),
            RegisteredPerson.is_active.is_(True),  # type: ignore[union-attr, list-item]
        ]

        if not include_expired:
            conditions.append(cast("ColumnElement[bool]", RegisteredPerson.expires_at > datetime.now(UTC)))

        stmt = select(func.count()).select_from(RegisteredPerson).where(and_(*conditions))

        result = await self._db.execute(stmt)
        return result.scalar() or 0


__all__ = ["RegisteredPersonRepository"]
