"""
Payment Schedule Repository Implementation

SQLAlchemy implementation of IPaymentScheduleRepository.
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.credit.application.ports import IPaymentScheduleRepository
from app.domains.credit.infrastructure.persistence.sqlalchemy.models import PaymentScheduleItemModel

logger = logging.getLogger(__name__)


class SQLAlchemyPaymentScheduleRepository(IPaymentScheduleRepository):
    """
    SQLAlchemy implementation of payment schedule repository.

    Handles all payment schedule data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_schedule(self, account_id: str) -> list[dict]:
        """Get payment schedule for account."""
        try:
            account_id_int = int(account_id)
            result = await self.session.execute(
                select(PaymentScheduleItemModel)
                .where(PaymentScheduleItemModel.account_id == account_id_int)
                .order_by(PaymentScheduleItemModel.due_date.asc())  # type: ignore[union-attr]
            )
            models = result.scalars().all()
            return [m.to_dict() for m in models]
        except ValueError:
            logger.warning(f"Invalid account_id format: {account_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting schedule for account {account_id}: {e}")
            raise

    async def get_next_payment(self, account_id: str) -> dict | None:
        """Get next scheduled payment."""
        try:
            account_id_int = int(account_id)
            today = date.today()
            result = await self.session.execute(
                select(PaymentScheduleItemModel)
                .where(
                    PaymentScheduleItemModel.account_id == account_id_int,
                    PaymentScheduleItemModel.due_date >= today,  # type: ignore[operator]
                    PaymentScheduleItemModel.status == "pending",
                )
                .order_by(PaymentScheduleItemModel.due_date.asc())  # type: ignore[union-attr]
                .limit(1)
            )
            model = result.scalar_one_or_none()
            return model.to_dict() if model else None
        except ValueError:
            logger.warning(f"Invalid account_id format: {account_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting next payment for account {account_id}: {e}")
            raise

    async def get_overdue_payments(self, account_id: str) -> list[dict]:
        """Get overdue payments."""
        try:
            account_id_int = int(account_id)
            today = date.today()
            result = await self.session.execute(
                select(PaymentScheduleItemModel)
                .where(
                    PaymentScheduleItemModel.account_id == account_id_int,
                    PaymentScheduleItemModel.due_date < today,  # type: ignore[operator]
                    PaymentScheduleItemModel.status == "pending",
                )
                .order_by(PaymentScheduleItemModel.due_date.asc())  # type: ignore[union-attr]
            )
            models = result.scalars().all()
            return [m.to_dict() for m in models]
        except ValueError:
            logger.warning(f"Invalid account_id format: {account_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting overdue payments for account {account_id}: {e}")
            raise

    async def update_schedule_item(self, schedule_item_id: str, status: str) -> dict | None:
        """Update schedule item status."""
        try:
            item_id_int = int(schedule_item_id)
            result = await self.session.execute(
                select(PaymentScheduleItemModel).where(PaymentScheduleItemModel.id == item_id_int)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            model.status = status
            if status == "paid":
                model.paid_date = date.today()

            await self.session.commit()
            await self.session.refresh(model)
            return model.to_dict()
        except ValueError:
            logger.warning(f"Invalid schedule_item_id format: {schedule_item_id}")
            return None
        except Exception as e:
            logger.error(f"Error updating schedule item {schedule_item_id}: {e}")
            await self.session.rollback()
            raise

    # Additional useful methods

    async def create_schedule_item(
        self,
        account_id: int,
        due_date: date,
        amount: float,
        principal_amount: float | None = None,
        interest_amount: float | None = None,
    ) -> dict:
        """Create a new schedule item."""
        model = PaymentScheduleItemModel(
            account_id=account_id,
            due_date=due_date,
            amount=amount,
            principal_amount=principal_amount,
            interest_amount=interest_amount,
            status="pending",
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_dict()

    async def mark_as_paid(
        self,
        schedule_item_id: int,
        paid_amount: float,
        paid_date: date | None = None,
    ) -> dict | None:
        """Mark schedule item as paid."""
        from decimal import Decimal

        result = await self.session.execute(
            select(PaymentScheduleItemModel).where(PaymentScheduleItemModel.id == schedule_item_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        model.status = "paid"
        model.paid_date = paid_date or date.today()
        model.paid_amount = Decimal(str(paid_amount))

        await self.session.commit()
        await self.session.refresh(model)
        return model.to_dict()

    async def delete_schedule(self, account_id: int) -> int:
        """Delete all schedule items for an account. Returns count deleted."""
        result = await self.session.execute(
            select(PaymentScheduleItemModel).where(PaymentScheduleItemModel.account_id == account_id)
        )
        models = result.scalars().all()
        count = len(models)
        for model in models:
            await self.session.delete(model)
        await self.session.commit()
        return count

    async def get_upcoming(self, account_id: int, days: int = 30) -> list[dict]:
        """Get upcoming payments within days."""
        from datetime import timedelta

        today = date.today()
        end_date = today + timedelta(days=days)

        result = await self.session.execute(
            select(PaymentScheduleItemModel)
            .where(
                PaymentScheduleItemModel.account_id == account_id,
                PaymentScheduleItemModel.due_date >= today,  # type: ignore[operator]
                PaymentScheduleItemModel.due_date <= end_date,  # type: ignore[operator]
                PaymentScheduleItemModel.status == "pending",
            )
            .order_by(PaymentScheduleItemModel.due_date.asc())  # type: ignore[union-attr]
        )
        models = result.scalars().all()
        return [m.to_dict() for m in models]
