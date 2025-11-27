"""
Track Order Use Case

Business logic for tracking order status and shipping.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from app.domains.ecommerce.application.ports import IOrderRepository

logger = logging.getLogger(__name__)


@dataclass
class TrackOrderRequest:
    """Request for tracking an order."""

    order_id: str


@dataclass
class TrackOrderResponse:
    """Response from order tracking."""

    order_id: str | None = None
    order_number: str | None = None
    status: str | None = None
    payment_status: str | None = None
    tracking_number: str | None = None
    shipping_method: str | None = None
    estimated_delivery: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    success: bool = False
    error: str | None = None


class TrackOrderUseCase:
    """
    Use Case: Track Order

    Retrieves tracking information for an order.

    Responsibilities:
    - Find order by ID or order number
    - Return tracking details
    - Return shipping status
    """

    def __init__(self, order_repository: IOrderRepository):
        """
        Initialize use case with dependencies.

        Args:
            order_repository: Repository for order data access
        """
        self.order_repository = order_repository

    async def execute(self, request: TrackOrderRequest) -> TrackOrderResponse:
        """
        Get tracking information for an order.

        Args:
            request: Track order request

        Returns:
            TrackOrderResponse with tracking details or error
        """
        try:
            if not request.order_id:
                return TrackOrderResponse(
                    success=False,
                    error="Order ID is required",
                )

            # Get tracking info from repository
            tracking_info = await self.order_repository.get_tracking_info(request.order_id)

            if not tracking_info:
                return TrackOrderResponse(
                    success=False,
                    error=f"Order not found: {request.order_id}",
                )

            # Parse dates if they're strings
            estimated_delivery = tracking_info.get("expected_delivery")
            delivered_at = tracking_info.get("delivered_at")

            if isinstance(estimated_delivery, str):
                try:
                    estimated_delivery = datetime.fromisoformat(estimated_delivery)
                except ValueError:
                    estimated_delivery = None

            if isinstance(delivered_at, str):
                try:
                    delivered_at = datetime.fromisoformat(delivered_at)
                except ValueError:
                    delivered_at = None

            logger.info(f"Order tracked: {request.order_id}")

            return TrackOrderResponse(
                order_id=tracking_info.get("order_id"),
                order_number=tracking_info.get("order_number"),
                status=tracking_info.get("status"),
                tracking_number=tracking_info.get("tracking_number"),
                shipping_method=tracking_info.get("shipping_method"),
                estimated_delivery=estimated_delivery,
                delivered_at=delivered_at,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error tracking order {request.order_id}: {e}")
            return TrackOrderResponse(
                success=False,
                error=str(e),
            )


__all__ = ["TrackOrderUseCase", "TrackOrderRequest", "TrackOrderResponse"]
