"""
Save Pending Ticket Use Case.

Creates or updates pending tickets for the multi-step incident creation flow.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.soporte import PendingTicket

logger = logging.getLogger(__name__)


class SavePendingTicketUseCase:
    """
    Use Case: Save Pending Ticket

    Creates or updates a pending ticket for the conversational flow.
    Handles state transitions and data collection.

    Responsibilities:
    - Create new pending tickets
    - Update existing pending tickets
    - Manage flow state transitions
    - Handle cancellation and completion
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize use case with database session.

        Args:
            db: Async database session
        """
        self.db = db

    async def create(
        self,
        conversation_id: str,
        user_phone: str,
        current_step: str = "description",
        collected_data: dict[str, Any] | None = None,
    ) -> PendingTicket:
        """
        Create a new pending ticket.

        Args:
            conversation_id: WhatsApp conversation ID
            user_phone: User's phone number
            current_step: Initial step (default: description)
            collected_data: Initial collected data

        Returns:
            Created PendingTicket

        Example:
            use_case = SavePendingTicketUseCase(db)
            pending = await use_case.create(
                conversation_id="conv_123",
                user_phone="+521234567890"
            )
        """
        try:
            # First, deactivate any existing pending tickets for this conversation
            await self._deactivate_existing(conversation_id)

            # Create new pending ticket
            pending = PendingTicket(
                conversation_id=conversation_id,
                user_phone=user_phone,
                current_step=current_step,
                collected_data=collected_data or {},
                started_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=30),
                is_active=True,
            )

            self.db.add(pending)
            await self.db.commit()
            await self.db.refresh(pending)

            logger.info(f"Created pending ticket for conversation {conversation_id}")
            return pending

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating pending ticket: {e}")
            raise

    async def update_step(
        self,
        conversation_id: str,
        new_step: str,
        collected_data: dict[str, Any] | None = None,
    ) -> PendingTicket | None:
        """
        Update the current step and collected data.

        Args:
            conversation_id: WhatsApp conversation ID
            new_step: New step to transition to
            collected_data: Updated collected data (merged with existing)

        Returns:
            Updated PendingTicket or None if not found
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

            # Update step
            pending.current_step = new_step

            # Merge collected data
            if collected_data:
                existing_data = pending.collected_data or {}
                existing_data.update(collected_data)
                pending.collected_data = existing_data

            # Extend expiration
            pending.extend_expiration(30)

            await self.db.commit()
            await self.db.refresh(pending)

            logger.info(f"Updated pending ticket to step {new_step}")
            return pending

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating pending ticket: {e}")
            return None

    async def set_description(
        self,
        conversation_id: str,
        description: str,
    ) -> PendingTicket | None:
        """
        Set the description and advance to priority step.

        Args:
            conversation_id: WhatsApp conversation ID
            description: User's problem description

        Returns:
            Updated PendingTicket or None
        """
        return await self.update_step(
            conversation_id,
            new_step="priority",
            collected_data={"description": description},
        )

    async def set_priority(
        self,
        conversation_id: str,
        priority: str,
    ) -> PendingTicket | None:
        """
        Set the priority and advance to confirmation step.

        Args:
            conversation_id: WhatsApp conversation ID
            priority: Selected priority (1-4 or text)

        Returns:
            Updated PendingTicket or None
        """
        return await self.update_step(
            conversation_id,
            new_step="confirmation",
            collected_data={"priority": priority},
        )

    async def deactivate(self, conversation_id: str) -> bool:
        """
        Deactivate (cancel or complete) a pending ticket.

        Args:
            conversation_id: WhatsApp conversation ID

        Returns:
            True if deactivated, False if not found
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
                return False

            pending.deactivate()
            await self.db.commit()

            logger.info(f"Deactivated pending ticket for conversation {conversation_id}")
            return True

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deactivating pending ticket: {e}")
            return False

    async def reset_to_description(self, conversation_id: str) -> PendingTicket | None:
        """
        Reset the flow back to description step.

        Called when user says NO during confirmation.

        Args:
            conversation_id: WhatsApp conversation ID

        Returns:
            Reset PendingTicket or None
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

            pending.reset_to_description()
            pending.extend_expiration(30)
            await self.db.commit()
            await self.db.refresh(pending)

            logger.info("Reset pending ticket to description step")
            return pending

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error resetting pending ticket: {e}")
            return None

    async def reset_to_priority(self, conversation_id: str) -> PendingTicket | None:
        """
        Reset the flow back to priority step (keep description).

        Called when user wants to change only the priority during confirmation.

        Args:
            conversation_id: WhatsApp conversation ID

        Returns:
            Reset PendingTicket or None
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

            # Reset only the step and priority, keep description
            pending.current_step = "priority"
            if pending.collected_data and "priority" in pending.collected_data:
                # Create new dict without priority to avoid Column mutation issues
                new_data = {k: v for k, v in pending.collected_data.items() if k != "priority"}
                pending.collected_data = new_data

            pending.extend_expiration(30)
            await self.db.commit()
            await self.db.refresh(pending)

            logger.info("Reset pending ticket to priority step (kept description)")
            return pending

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error resetting pending ticket to priority: {e}")
            return None

    async def _deactivate_existing(self, conversation_id: str) -> None:
        """
        Deactivate any existing active pending tickets for this conversation.

        Args:
            conversation_id: WhatsApp conversation ID
        """
        result = await self.db.execute(
            select(PendingTicket).where(
                PendingTicket.conversation_id == conversation_id,
                PendingTicket.is_active == True,  # noqa: E712
            )
        )
        existing = result.scalars().all()

        for pending in existing:
            pending.deactivate()
