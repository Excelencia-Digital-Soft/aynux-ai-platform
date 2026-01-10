"""
Entry Validation Node - First node in pharmacy flow.

Handles CASO 0 validations from docs/pharmacy_flujo_mejorado_v2.md:
1. Message deduplication (already handled by webhook, tracked here)
2. Rate limiting (10 msg/min, 100 msg/hour)
3. Business hours checking

If any validation fails, returns appropriate message and stops processing.
Otherwise, passes through to person resolution node.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.agents import BaseAgent
from app.domains.pharmacy.services.business_hours_service import (
    BusinessHoursService,
    get_business_hours_service,
)
from app.domains.pharmacy.services.rate_limiter_service import (
    PharmacyRateLimiter,
    get_rate_limiter,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EntryValidationNode(BaseAgent):
    """
    Entry validation node for pharmacy flow.

    Validates incoming messages before processing:
    1. Rate limiting - prevents message flooding
    2. Business hours - optional service hours enforcement

    This node is the first in the pharmacy graph and gates
    all subsequent processing.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        config: dict[str, Any] | None = None,
        rate_limiter: PharmacyRateLimiter | None = None,
        business_hours_service: BusinessHoursService | None = None,
    ):
        """
        Initialize entry validation node.

        Args:
            db_session: SQLAlchemy async session for DB access
            config: Node configuration
            rate_limiter: PharmacyRateLimiter instance
            business_hours_service: BusinessHoursService instance
        """
        super().__init__("entry_validation_node", config or {})
        self._db_session = db_session
        self._rate_limiter = rate_limiter
        self._business_hours_service = business_hours_service

    def _get_rate_limiter(self) -> PharmacyRateLimiter:
        """Get or create rate limiter."""
        if self._rate_limiter is None:
            self._rate_limiter = get_rate_limiter()
        return self._rate_limiter

    def _get_business_hours_service(self) -> BusinessHoursService:
        """Get or create business hours service."""
        if self._business_hours_service is None:
            self._business_hours_service = get_business_hours_service()
        return self._business_hours_service

    async def _process_internal(
        self,
        message: str,
        state_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate incoming message.

        Args:
            message: User's message
            state_dict: Current pharmacy state

        Returns:
            Updated state with validation results
        """
        phone = state_dict.get("customer_id") or state_dict.get("whatsapp_phone")
        pharmacy_id = state_dict.get("pharmacy_id")

        if not phone:
            logger.warning("EntryValidationNode: No phone number in state")
            return {
                "validation_passed": False,
                "validation_error": "No se pudo identificar el número de teléfono.",
            }

        # Track message for this session
        updates: dict[str, Any] = {
            "validation_passed": True,
            "rate_limited": False,
            "rate_limit_reason": None,
        }

        # 1. Check rate limiting
        rate_check = await self._check_rate_limit(phone)
        if not rate_check["allowed"]:
            updates.update({
                "validation_passed": False,
                "rate_limited": True,
                "rate_limit_reason": rate_check["reason"],
            })
            return updates

        # 2. Check business hours (optional - only if pharmacy configured)
        if pharmacy_id:
            hours_check = await self._check_business_hours(pharmacy_id)
            if not hours_check["is_open"]:
                # Business hours check failed, but this is informational
                # We still allow messages but include the warning
                updates.update({
                    "is_within_service_hours": False,
                    "service_hours_message": hours_check.get("message"),
                    "emergency_phone": hours_check.get("emergency_phone"),
                })
                # Note: We don't block here, just inform
                # The router can decide to show a warning

        # Record message for rate limiting
        await self._record_message(phone)

        return updates

    async def _check_rate_limit(self, phone: str) -> dict[str, Any]:
        """
        Check if phone is rate limited.

        Args:
            phone: User's phone number

        Returns:
            Dictionary with 'allowed', 'reason', 'retry_after'
        """
        rate_limiter = self._get_rate_limiter()

        try:
            result = await rate_limiter.check_message_rate(phone)
            return {
                "allowed": result.allowed,
                "reason": result.reason,
                "retry_after": result.retry_after_seconds,
            }
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow message if check fails
            return {"allowed": True, "reason": None, "retry_after": None}

    async def _check_business_hours(self, pharmacy_id: str) -> dict[str, Any]:
        """
        Check if bot is within service hours.

        Args:
            pharmacy_id: Pharmacy UUID

        Returns:
            Dictionary with 'is_open', 'message', 'emergency_phone'
        """
        service = self._get_business_hours_service()

        try:
            result = await service.check_service_hours(pharmacy_id=pharmacy_id)
            return {
                "is_open": result.is_open,
                "message": result.message if not result.is_open else None,
                "emergency_phone": result.emergency_phone,
            }
        except Exception as e:
            logger.error(f"Business hours check failed: {e}")
            # Fail open - assume open if check fails
            return {"is_open": True, "message": None, "emergency_phone": None}

    async def _record_message(self, phone: str) -> None:
        """
        Record message for rate limiting counters.

        Args:
            phone: User's phone number
        """
        rate_limiter = self._get_rate_limiter()

        try:
            await rate_limiter.record_message(phone)
        except Exception as e:
            logger.error(f"Failed to record message for rate limiting: {e}")


# Factory function for dependency injection
def create_entry_validation_node(
    db_session: AsyncSession | None = None,
    config: dict[str, Any] | None = None,
) -> EntryValidationNode:
    """
    Create EntryValidationNode with dependencies.

    Args:
        db_session: SQLAlchemy async session
        config: Node configuration

    Returns:
        Configured EntryValidationNode instance
    """
    return EntryValidationNode(
        db_session=db_session,
        config=config,
    )


__all__ = [
    "EntryValidationNode",
    "create_entry_validation_node",
]
