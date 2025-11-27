"""
Payment Repository Implementation

SQLAlchemy implementation of IPaymentRepository.
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.credit.application.ports import IPaymentRepository
from app.domains.credit.domain.entities.payment import Payment
from app.domains.credit.domain.value_objects.account_status import (
    PaymentMethod,
    PaymentStatus,
    PaymentType,
)
from app.domains.credit.infrastructure.persistence.sqlalchemy.models import PaymentModel

logger = logging.getLogger(__name__)


class SQLAlchemyPaymentRepository(IPaymentRepository):
    """
    SQLAlchemy implementation of payment repository.

    Handles all payment data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def create(self, payment: Payment) -> Payment:
        """Create a new payment."""
        model = self._to_model(payment)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, payment_id: str) -> Payment | None:
        """Get payment by ID."""
        try:
            payment_id_int = int(payment_id)
            result = await self.session.execute(
                select(PaymentModel).where(PaymentModel.id == payment_id_int)
            )
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None
        except ValueError:
            logger.warning(f"Invalid payment_id format: {payment_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting payment by ID {payment_id}: {e}")
            raise

    async def get_by_account(
        self,
        account_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 20,
    ) -> list[Payment]:
        """Get payments by account."""
        try:
            account_id_int = int(account_id)
            query = select(PaymentModel).where(PaymentModel.account_id == account_id_int)

            if start_date:
                query = query.where(PaymentModel.initiated_at >= start_date)
            if end_date:
                query = query.where(PaymentModel.initiated_at <= end_date)

            query = query.order_by(PaymentModel.initiated_at.desc()).limit(limit)

            result = await self.session.execute(query)
            models = result.scalars().all()
            return [self._to_entity(m) for m in models]
        except ValueError:
            logger.warning(f"Invalid account_id format: {account_id}")
            return []
        except Exception as e:
            logger.error(f"Error getting payments for account {account_id}: {e}")
            raise

    async def get_total_paid(self, account_id: str) -> Decimal:
        """Get total amount paid for account."""
        try:
            account_id_int = int(account_id)
            result = await self.session.execute(
                select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                    PaymentModel.account_id == account_id_int,
                    PaymentModel.status == PaymentStatus.COMPLETED,
                )
            )
            total = result.scalar_one()
            return Decimal(str(total)) if total else Decimal("0")
        except ValueError:
            logger.warning(f"Invalid account_id format: {account_id}")
            return Decimal("0")
        except Exception as e:
            logger.error(f"Error getting total paid for account {account_id}: {e}")
            raise

    # Additional useful methods

    async def get_by_reference(self, reference_number: str) -> Payment | None:
        """Get payment by reference number."""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.reference_number == reference_number)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_status(self, status: PaymentStatus, limit: int = 100) -> list[Payment]:
        """Find payments by status."""
        result = await self.session.execute(
            select(PaymentModel)
            .where(PaymentModel.status == status)
            .order_by(PaymentModel.initiated_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_pending(self, limit: int = 100) -> list[Payment]:
        """Find pending payments."""
        return await self.find_by_status(PaymentStatus.PENDING, limit)

    async def update(self, payment: Payment) -> Payment | None:
        """Update an existing payment."""
        if not payment.id:
            return None

        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None

        self._update_model(model, payment)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def count_by_account(self, account_id: int) -> int:
        """Count payments for an account."""
        result = await self.session.execute(
            select(func.count()).where(PaymentModel.account_id == account_id)
        )
        return result.scalar_one()

    async def delete(self, payment_id: int) -> bool:
        """Delete a payment."""
        result = await self.session.execute(
            select(PaymentModel).where(PaymentModel.id == payment_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    # Mapping methods

    def _to_entity(self, model: PaymentModel) -> Payment:
        """Convert model to entity."""
        payment = Payment(
            id=model.id,
            account_id=model.account_id,
            customer_id=model.customer_id or 0,
            account_number=model.account_number or "",
            amount=Decimal(str(model.amount)) if model.amount else Decimal("0"),
            payment_type=model.payment_type or PaymentType.REGULAR,
            payment_method=model.payment_method or PaymentMethod.BANK_TRANSFER,
            status=model.status or PaymentStatus.PENDING,
            transaction_id=model.transaction_id,
            reference_number=model.reference_number,
            receipt_url=model.receipt_url,
            interest_paid=Decimal(str(model.interest_paid)) if model.interest_paid else Decimal("0"),
            charges_paid=Decimal(str(model.charges_paid)) if model.charges_paid else Decimal("0"),
            principal_paid=Decimal(str(model.principal_paid)) if model.principal_paid else Decimal("0"),
            initiated_at=model.initiated_at,
            processed_at=model.processed_at,
            completed_at=model.completed_at,
            failed_at=model.failed_at,
            failure_reason=model.failure_reason,
            retry_count=model.retry_count or 0,
            description=model.description,
            notes=model.notes,
        )

        if model.created_at:
            payment.created_at = model.created_at
        if model.updated_at:
            payment.updated_at = model.updated_at

        return payment

    def _to_model(self, payment: Payment) -> PaymentModel:
        """Convert entity to model."""
        return PaymentModel(
            account_id=payment.account_id,
            customer_id=payment.customer_id,
            account_number=payment.account_number,
            amount=payment.amount,
            payment_type=payment.payment_type,
            payment_method=payment.payment_method,
            status=payment.status,
            transaction_id=payment.transaction_id,
            reference_number=payment.reference_number,
            receipt_url=payment.receipt_url,
            interest_paid=payment.interest_paid,
            charges_paid=payment.charges_paid,
            principal_paid=payment.principal_paid,
            initiated_at=payment.initiated_at,
            processed_at=payment.processed_at,
            completed_at=payment.completed_at,
            failed_at=payment.failed_at,
            failure_reason=payment.failure_reason,
            retry_count=payment.retry_count,
            description=payment.description,
            notes=payment.notes,
        )

    def _update_model(self, model: PaymentModel, payment: Payment) -> None:
        """Update model from entity."""
        model.amount = payment.amount
        model.payment_type = payment.payment_type
        model.payment_method = payment.payment_method
        model.status = payment.status
        model.transaction_id = payment.transaction_id
        model.receipt_url = payment.receipt_url
        model.interest_paid = payment.interest_paid
        model.charges_paid = payment.charges_paid
        model.principal_paid = payment.principal_paid
        model.processed_at = payment.processed_at
        model.completed_at = payment.completed_at
        model.failed_at = payment.failed_at
        model.failure_reason = payment.failure_reason
        model.retry_count = payment.retry_count
        model.description = payment.description
        model.notes = payment.notes
