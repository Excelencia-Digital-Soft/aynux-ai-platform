"""
Customer Use Cases

Use cases for customer management following Clean Architecture.
"""

import logging
from typing import Any

from app.domains.shared.application.ports.customer_repository import ICustomerRepository

logger = logging.getLogger(__name__)


class GetOrCreateCustomerUseCase:
    """
    Use Case: Get or Create Customer

    Handles the business logic for getting an existing customer or creating a new one.
    This is the most common operation in customer management.

    Responsibilities:
    - Check if customer exists
    - Create new customer if needed
    - Update last contact timestamp
    - Handle race conditions safely

    Now follows Clean Architecture with proper dependency injection.
    """

    def __init__(self, customer_repository: ICustomerRepository):
        """
        Initialize use case with dependencies.

        Args:
            customer_repository: Repository for customer data access
        """
        self.customer_repository = customer_repository

    async def execute(
        self,
        phone_number: str,
        profile_name: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get or create a customer by phone number.

        Args:
            phone_number: Customer's phone number (unique identifier)
            profile_name: Optional profile/display name

        Returns:
            Customer data as dictionary, or None if operation fails

        Example:
            use_case = GetOrCreateCustomerUseCase(repository)
            customer = await use_case.execute("+5491123456789", "John Doe")
        """
        try:
            customer = await self.customer_repository.get_or_create(
                phone_number=phone_number,
                profile_name=profile_name,
            )
            return customer

        except Exception as e:
            logger.error(f"Error in GetOrCreateCustomerUseCase: {e}")
            return None


__all__ = ["GetOrCreateCustomerUseCase"]
