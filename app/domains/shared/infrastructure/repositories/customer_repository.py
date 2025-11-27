"""
Customer Repository Implementation

SQLAlchemy implementation of ICustomerRepository.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.application.ports.customer_repository import ICustomerRepository
from app.models.db.customers import Customer as CustomerModel

logger = logging.getLogger(__name__)


class SQLAlchemyCustomerRepository(ICustomerRepository):
    """
    SQLAlchemy implementation of customer repository.

    Handles all customer data persistence operations using async patterns.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def find_by_phone(self, phone_number: str) -> dict[str, Any] | None:
        """Find customer by phone number."""
        result = await self.session.execute(select(CustomerModel).where(CustomerModel.phone_number == phone_number))
        model = result.scalar_one_or_none()
        return self._to_dict(model) if model else None

    async def find_by_id(self, customer_id: str) -> dict[str, Any] | None:
        """Find customer by ID."""
        result = await self.session.execute(select(CustomerModel).where(CustomerModel.id == customer_id))
        model = result.scalar_one_or_none()
        return self._to_dict(model) if model else None

    async def save(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Save or update a customer."""
        customer_id = customer_data.get("id")

        if customer_id:
            # Update existing
            result = await self.session.execute(select(CustomerModel).where(CustomerModel.id == customer_id))
            model = result.scalar_one_or_none()
            if model:
                self._update_model(model, customer_data)
            else:
                model = self._to_model(customer_data)
                self.session.add(model)
        else:
            # Create new
            model = self._to_model(customer_data)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        return self._to_dict(model)

    async def update_last_contact(self, customer_id: str) -> bool:
        """Update customer's last contact timestamp."""
        result = await self.session.execute(select(CustomerModel).where(CustomerModel.id == customer_id))
        model = result.scalar_one_or_none()
        if model:
            model.last_contact = datetime.now(timezone.utc)
            await self.session.commit()
            return True
        return False

    async def increment_interactions(self, customer_id: str) -> bool:
        """Increment customer's total interactions counter."""
        result = await self.session.execute(select(CustomerModel).where(CustomerModel.id == customer_id))
        model = result.scalar_one_or_none()
        if model:
            model.total_interactions = (model.total_interactions or 0) + 1
            model.last_contact = datetime.now(timezone.utc)
            await self.session.commit()
            return True
        return False

    async def get_or_create(
        self,
        phone_number: str,
        profile_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get existing customer or create new one.

        Handles race conditions with proper retry logic.
        """
        # Try to find existing customer
        existing = await self.find_by_phone(phone_number)
        if existing:
            # Update interaction stats
            await self.increment_interactions(existing["id"])
            if profile_name and not existing.get("profile_name"):
                # Update profile name if not set
                result = await self.session.execute(select(CustomerModel).where(CustomerModel.id == existing["id"]))
                model = result.scalar_one_or_none()
                if model:
                    model.profile_name = profile_name
                    await self.session.commit()
                    await self.session.refresh(model)
                    return self._to_dict(model)
            return existing

        # Create new customer
        try:
            now = datetime.now(timezone.utc)
            model = CustomerModel(
                phone_number=phone_number,
                profile_name=profile_name,
                first_contact=now,
                last_contact=now,
                total_interactions=1,
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            logger.info(f"New customer created: {phone_number}")
            return self._to_dict(model)

        except IntegrityError as e:
            # Handle race condition (duplicate key)
            await self.session.rollback()
            if "unique constraint" in str(e).lower() or "duplicate key" in str(e).lower():
                # Another process created the customer, fetch it
                existing = await self.find_by_phone(phone_number)
                if existing:
                    logger.info(f"Customer found after race condition: {phone_number}")
                    return existing
            logger.error(f"Failed to create customer: {phone_number} - {e}")
            return None

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating customer: {phone_number} - {e}")
            return None

    # Mapping methods

    def _to_dict(self, model: CustomerModel) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "id": str(model.id),
            "phone_number": model.phone_number,
            "name": model.name,
            "first_name": model.first_name,
            "last_name": model.last_name,
            "profile_name": model.profile_name,
            "date_of_birth": model.date_of_birth,
            "gender": model.gender,
            "total_interactions": model.total_interactions,
            "total_inquiries": model.total_inquiries,
            "interests": model.interests,
            "preferences": model.preferences,
            "meta_data": model.meta_data,
            "budget_range": model.budget_range,
            "preferred_brands": model.preferred_brands,
            "active": model.active,
            "blocked": model.blocked,
            "vip": model.vip,
            "first_contact": model.first_contact,
            "last_contact": model.last_contact,
        }

    def _to_model(self, data: dict[str, Any]) -> CustomerModel:
        """Convert dictionary to model."""
        return CustomerModel(
            phone_number=data.get("phone_number"),
            name=data.get("name"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            profile_name=data.get("profile_name"),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            total_interactions=data.get("total_interactions", 0),
            total_inquiries=data.get("total_inquiries", 0),
            interests=data.get("interests"),
            preferences=data.get("preferences", {}),
            meta_data=data.get("meta_data", {}),
            budget_range=data.get("budget_range"),
            preferred_brands=data.get("preferred_brands"),
            active=data.get("active", True),
            blocked=data.get("blocked", False),
            vip=data.get("vip", False),
            first_contact=data.get("first_contact", datetime.now(timezone.utc)),
            last_contact=data.get("last_contact", datetime.now(timezone.utc)),
        )

    def _update_model(self, model: CustomerModel, data: dict[str, Any]) -> None:
        """Update model from dictionary."""
        if "name" in data:
            model.name = data["name"]
        if "first_name" in data:
            model.first_name = data["first_name"]
        if "last_name" in data:
            model.last_name = data["last_name"]
        if "profile_name" in data:
            model.profile_name = data["profile_name"]
        if "date_of_birth" in data:
            model.date_of_birth = data["date_of_birth"]
        if "gender" in data:
            model.gender = data["gender"]
        if "interests" in data:
            model.interests = data["interests"]
        if "preferences" in data:
            model.preferences = data["preferences"]
        if "meta_data" in data:
            model.meta_data = data["meta_data"]
        if "budget_range" in data:
            model.budget_range = data["budget_range"]
        if "preferred_brands" in data:
            model.preferred_brands = data["preferred_brands"]
        if "active" in data:
            model.active = data["active"]
        if "blocked" in data:
            model.blocked = data["blocked"]
        if "vip" in data:
            model.vip = data["vip"]


__all__ = ["SQLAlchemyCustomerRepository"]
