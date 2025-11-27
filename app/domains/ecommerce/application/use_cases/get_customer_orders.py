"""
Get Customer Orders Use Case

Business logic for retrieving customer order history.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.domains.ecommerce.application.ports import IOrderRepository

logger = logging.getLogger(__name__)


@dataclass
class GetCustomerOrdersRequest:
    """Request for getting customer orders."""

    customer_id: str
    limit: int = 10


@dataclass
class GetCustomerOrdersResponse:
    """Response from getting customer orders."""

    orders: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    success: bool = False
    error: str | None = None


class GetCustomerOrdersUseCase:
    """
    Use Case: Get Customer Orders

    Retrieves order history for a customer.

    Responsibilities:
    - Find orders by customer ID
    - Return order summaries
    - Support pagination via limit
    """

    def __init__(self, order_repository: IOrderRepository):
        """
        Initialize use case with dependencies.

        Args:
            order_repository: Repository for order data access
        """
        self.order_repository = order_repository

    async def execute(self, request: GetCustomerOrdersRequest) -> GetCustomerOrdersResponse:
        """
        Get orders for a customer.

        Args:
            request: Get customer orders request

        Returns:
            GetCustomerOrdersResponse with order list or error
        """
        try:
            if not request.customer_id:
                return GetCustomerOrdersResponse(
                    success=False,
                    error="Customer ID is required",
                )

            # Get orders from repository
            orders = await self.order_repository.get_by_customer(
                customer_id=request.customer_id,
                limit=request.limit,
            )

            # Convert to summaries
            order_summaries = [order.to_summary_dict() for order in orders]

            logger.info(f"Retrieved {len(orders)} orders for customer {request.customer_id}")

            return GetCustomerOrdersResponse(
                orders=order_summaries,
                total_count=len(orders),
                success=True,
            )

        except Exception as e:
            logger.error(f"Error getting orders for customer {request.customer_id}: {e}")
            return GetCustomerOrdersResponse(
                success=False,
                error=str(e),
            )


__all__ = ["GetCustomerOrdersUseCase", "GetCustomerOrdersRequest", "GetCustomerOrdersResponse"]
