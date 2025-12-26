"""
Get Pending Ticket Use Case.

Retrieves active pending tickets for a conversation to continue
the multi-step incident creation flow.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.soporte import PendingTicket

logger = logging.getLogger(__name__)


class GetPendingTicketUseCase:
    """
    Use Case: Get Pending Ticket

    Retrieves an active pending ticket for a given conversation ID.
    Used to check if there's an ongoing incident creation flow.

    Responsibilities:
    - Find active pending ticket by conversation ID
    - Check if ticket is expired
    - Return None if no active ticket found
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize use case with database session.

        Args:
            db: Async database session
        """
        self.db = db

    async def execute(self, conversation_id: str) -> PendingTicket | None:
        """
        Get active pending ticket for conversation.

        Args:
            conversation_id: WhatsApp conversation ID

        Returns:
            PendingTicket if found and active, None otherwise

        Example:
            use_case = GetPendingTicketUseCase(db)
            pending = await use_case.execute("conv_123")
            if pending:
                print(f"Current step: {pending.current_step}")
        """
        try:
            result = await self.db.execute(
                select(PendingTicket).where(
                    PendingTicket.conversation_id == conversation_id,
                    PendingTicket.is_active == True,  # noqa: E712
                )
            )
            pending = result.scalar_one_or_none()

            if pending is None:
                return None

            # Check if expired
            if pending.is_expired:
                logger.info(f"Pending ticket {pending.id} expired, deactivating")
                pending.deactivate()
                await self.db.commit()
                return None

            return pending

        except Exception as e:
            logger.error(f"Error getting pending ticket: {e}")
            return None

    async def execute_by_phone(self, user_phone: str) -> PendingTicket | None:
        """
        Get active pending ticket by phone number.

        Alternative lookup method when conversation_id is not available.

        Args:
            user_phone: User's phone number

        Returns:
            PendingTicket if found and active, None otherwise
        """
        try:
            result = await self.db.execute(
                select(PendingTicket).where(
                    PendingTicket.user_phone == user_phone,
                    PendingTicket.is_active == True,  # noqa: E712
                ).order_by(PendingTicket.started_at.desc())
            )
            pending = result.scalar_one_or_none()

            if pending is None:
                return None

            # Check if expired
            if pending.is_expired:
                logger.info(f"Pending ticket {pending.id} expired, deactivating")
                pending.deactivate()
                await self.db.commit()
                return None

            return pending

        except Exception as e:
            logger.error(f"Error getting pending ticket by phone: {e}")
            return None
