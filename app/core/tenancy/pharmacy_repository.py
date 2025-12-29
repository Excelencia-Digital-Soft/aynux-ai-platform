# ============================================================================
# SCOPE: MULTI-TENANT
# Description: Repository for pharmacy configuration database operations.
#              Encapsulates all SQLAlchemy queries for PharmacyMerchantConfig.
# Tenant-Aware: Yes - queries filtered by organization membership.
# ============================================================================
"""Repository for pharmacy configuration database operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.tenancy import Organization, OrganizationUser
from app.models.db.tenancy.pharmacy_merchant_config import PharmacyMerchantConfig


class PharmacyRepository:
    """Database operations for pharmacy configurations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy async session for database queries
        """
        self._db = db

    async def get_by_id(
        self, pharmacy_id: UUID, *, load_organization: bool = True
    ) -> PharmacyMerchantConfig | None:
        """
        Get pharmacy by ID with optional organization eager load.

        Args:
            pharmacy_id: UUID of the pharmacy to fetch
            load_organization: Whether to eagerly load the organization relationship

        Returns:
            PharmacyMerchantConfig if found, None otherwise
        """
        stmt = select(PharmacyMerchantConfig).where(PharmacyMerchantConfig.id == pharmacy_id)
        if load_organization:
            stmt = stmt.options(selectinload(PharmacyMerchantConfig.organization))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_org_ids(self, user_id: UUID) -> list[UUID]:
        """
        Get organization IDs the user belongs to.

        Args:
            user_id: UUID of the user

        Returns:
            List of organization UUIDs the user is a member of
        """
        stmt = select(OrganizationUser.organization_id).where(
            OrganizationUser.user_id == user_id
        )
        result = await self._db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def get_user_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> OrganizationUser | None:
        """
        Get user's membership in an organization.

        Args:
            user_id: UUID of the user
            organization_id: UUID of the organization

        Returns:
            OrganizationUser if membership exists, None otherwise
        """
        stmt = select(OrganizationUser).where(
            OrganizationUser.user_id == user_id,
            OrganizationUser.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_organization(self, org_id: UUID) -> Organization | None:
        """
        Get organization by ID.

        Args:
            org_id: UUID of the organization

        Returns:
            Organization if found, None otherwise
        """
        stmt = select(Organization).where(Organization.id == org_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pharmacies(
        self,
        *,
        org_ids: list[UUID] | None = None,
        search: str | None = None,
        mp_enabled: bool | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[PharmacyMerchantConfig], int]:
        """
        List pharmacies with filters and pagination.

        Args:
            org_ids: Filter to these organization IDs (None = all orgs for system admins)
            search: Search by name, phone, or WhatsApp number
            mp_enabled: Filter by Mercado Pago enabled status
            page: Page number (1-based)
            page_size: Number of items per page

        Returns:
            Tuple of (list of pharmacies, total count)
        """
        stmt = select(PharmacyMerchantConfig).options(
            selectinload(PharmacyMerchantConfig.organization)
        )

        # Filter by orgs
        if org_ids is not None:
            stmt = stmt.where(PharmacyMerchantConfig.organization_id.in_(org_ids))

        # Search filter
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    PharmacyMerchantConfig.pharmacy_name.ilike(pattern),
                    PharmacyMerchantConfig.pharmacy_phone.ilike(pattern),
                    PharmacyMerchantConfig.whatsapp_phone_number.ilike(pattern),
                )
            )

        # MP filter
        if mp_enabled is not None:
            stmt = stmt.where(PharmacyMerchantConfig.mp_enabled == mp_enabled)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self._db.execute(count_stmt)
        total = count_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        stmt = (
            stmt.order_by(PharmacyMerchantConfig.pharmacy_name).offset(offset).limit(page_size)
        )

        result = await self._db.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def create(self, pharmacy: PharmacyMerchantConfig) -> PharmacyMerchantConfig:
        """
        Create a new pharmacy configuration.

        Args:
            pharmacy: PharmacyMerchantConfig instance to persist

        Returns:
            The persisted pharmacy with ID populated
        """
        self._db.add(pharmacy)
        await self._db.flush()
        return pharmacy

    async def delete(self, pharmacy: PharmacyMerchantConfig) -> None:
        """
        Delete a pharmacy configuration.

        Args:
            pharmacy: PharmacyMerchantConfig instance to delete
        """
        await self._db.delete(pharmacy)

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._db.commit()

    async def refresh(self, pharmacy: PharmacyMerchantConfig) -> None:
        """
        Refresh pharmacy from database.

        Args:
            pharmacy: PharmacyMerchantConfig instance to refresh
        """
        await self._db.refresh(pharmacy)
