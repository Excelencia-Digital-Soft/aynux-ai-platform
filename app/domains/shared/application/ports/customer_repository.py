"""
Customer Repository Interface

Port (interface) for customer data access following Clean Architecture.
Uses Protocol for structural typing.
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ICustomerRepository(Protocol):
    """
    Interface for customer repository.

    Defines the contract for customer data access operations.
    All implementations must provide async methods.
    """

    async def find_by_phone(self, phone_number: str) -> dict[str, Any] | None:
        """
        Find customer by phone number.

        Args:
            phone_number: Customer's phone number (unique identifier)

        Returns:
            Customer data as dictionary, or None if not found
        """
        ...

    async def find_by_id(self, customer_id: str) -> dict[str, Any] | None:
        """
        Find customer by ID.

        Args:
            customer_id: Customer's UUID

        Returns:
            Customer data as dictionary, or None if not found
        """
        ...

    async def save(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """
        Save or update a customer.

        Args:
            customer_data: Customer data to save

        Returns:
            Saved customer data with generated ID
        """
        ...

    async def update_last_contact(self, customer_id: str) -> bool:
        """
        Update customer's last contact timestamp.

        Args:
            customer_id: Customer's UUID

        Returns:
            True if update was successful
        """
        ...

    async def increment_interactions(self, customer_id: str) -> bool:
        """
        Increment customer's total interactions counter.

        Args:
            customer_id: Customer's UUID

        Returns:
            True if update was successful
        """
        ...

    async def get_or_create(
        self,
        phone_number: str,
        profile_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get existing customer or create new one.

        Handles race conditions internally.

        Args:
            phone_number: Customer's phone number
            profile_name: Optional profile/display name

        Returns:
            Customer data as dictionary, or None if operation fails
        """
        ...


__all__ = ["ICustomerRepository"]
