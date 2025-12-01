"""
Credit Account Repository Implementation

SQLAlchemy implementation of ICreditAccountRepository.
"""

import logging
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.credit.application.ports import ICreditAccountRepository
from app.domains.credit.domain.entities.credit_account import CreditAccount
from app.domains.credit.domain.value_objects.account_status import (
    AccountStatus,
    CollectionStatus,
    CreditLimit,
    InterestRate,
    RiskLevel,
)
from app.domains.credit.infrastructure.persistence.sqlalchemy.models import CreditAccountModel

logger = logging.getLogger(__name__)


class SQLAlchemyCreditAccountRepository(ICreditAccountRepository):
    """
    SQLAlchemy implementation of credit account repository.

    Handles all credit account data persistence operations.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, account_id: str) -> CreditAccount | None:
        """Get account by ID."""
        try:
            # Try to parse as integer first
            account_id_int = int(account_id)
            result = await self.session.execute(
                select(CreditAccountModel).where(CreditAccountModel.id == account_id_int)
            )
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None
        except ValueError:
            # If not a valid integer, return None
            logger.warning(f"Invalid account_id format: {account_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting account by ID {account_id}: {e}")
            raise

    async def get_by_customer(self, customer_id: str) -> CreditAccount | None:
        """Get account by customer ID."""
        try:
            customer_id_int = int(customer_id)
            result = await self.session.execute(
                select(CreditAccountModel).where(CreditAccountModel.customer_id == customer_id_int)
            )
            model = result.scalar_one_or_none()
            return self._to_entity(model) if model else None
        except ValueError:
            logger.warning(f"Invalid customer_id format: {customer_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting account by customer {customer_id}: {e}")
            raise

    async def get_by_account_number(self, account_number: str) -> CreditAccount | None:
        """Get account by account number."""
        result = await self.session.execute(
            select(CreditAccountModel).where(CreditAccountModel.account_number == account_number)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update_balance(self, account_id: str, new_balance: Decimal) -> CreditAccount | None:
        """Update account balance (used_credit)."""
        try:
            account_id_int = int(account_id)
            result = await self.session.execute(
                select(CreditAccountModel).where(CreditAccountModel.id == account_id_int)
            )
            model = result.scalar_one_or_none()
            if not model:
                return None

            model.used_credit = new_balance
            await self.session.commit()
            await self.session.refresh(model)
            return self._to_entity(model)
        except ValueError:
            logger.warning(f"Invalid account_id format: {account_id}")
            return None
        except Exception as e:
            logger.error(f"Error updating balance for account {account_id}: {e}")
            await self.session.rollback()
            raise

    async def save(self, account: CreditAccount) -> CreditAccount:
        """Save or update credit account."""
        if account.id:
            # Update existing
            result = await self.session.execute(
                select(CreditAccountModel).where(CreditAccountModel.id == account.id)
            )
            model = result.scalar_one_or_none()
            if model:
                self._update_model(model, account)
            else:
                model = self._to_model(account)
                self.session.add(model)
        else:
            # Create new
            model = self._to_model(account)
            self.session.add(model)

        await self.session.commit()
        await self.session.refresh(model)

        return self._to_entity(model)

    # Additional useful methods

    async def find_by_status(self, status: AccountStatus, limit: int = 100) -> list[CreditAccount]:
        """Find accounts by status."""
        result = await self.session.execute(
            select(CreditAccountModel)
            .where(CreditAccountModel.status == status)
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def find_overdue(self, min_days: int = 1, limit: int = 100) -> list[CreditAccount]:
        """Find overdue accounts."""
        result = await self.session.execute(
            select(CreditAccountModel)
            .where(CreditAccountModel.days_overdue >= min_days)  # type: ignore[operator]
            .order_by(CreditAccountModel.days_overdue.desc())  # type: ignore[union-attr]
            .limit(limit)
        )
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    async def count(self) -> int:
        """Get total account count."""
        result = await self.session.execute(
            select(func.count()).select_from(CreditAccountModel)
        )
        return result.scalar_one()

    async def count_by_status(self, status: AccountStatus) -> int:
        """Count accounts by status."""
        result = await self.session.execute(
            select(func.count()).where(CreditAccountModel.status == status)
        )
        return result.scalar_one()

    async def exists(self, account_id: int) -> bool:
        """Check if account exists."""
        result = await self.session.execute(
            select(func.count()).where(CreditAccountModel.id == account_id)
        )
        return result.scalar_one() > 0

    async def delete(self, account_id: int) -> bool:
        """Delete account."""
        result = await self.session.execute(
            select(CreditAccountModel).where(CreditAccountModel.id == account_id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self.session.delete(model)
            await self.session.commit()
            return True
        return False

    # Mapping methods

    def _to_entity(self, model: CreditAccountModel) -> CreditAccount:
        """Convert model to entity."""
        # Extract values with proper type handling for SQLAlchemy 2.0 Mapped types
        credit_limit_val = Decimal(str(model.credit_limit)) if model.credit_limit is not None else Decimal("0")
        interest_rate_val = Decimal(str(model.interest_rate)) if model.interest_rate is not None else Decimal("0.24")
        used_credit_val = Decimal(str(model.used_credit)) if model.used_credit is not None else Decimal("0")
        pending_charges_val = Decimal(str(model.pending_charges)) if model.pending_charges is not None else Decimal("0")
        accrued_interest_val = (
            Decimal(str(model.accrued_interest)) if model.accrued_interest is not None else Decimal("0")
        )
        min_payment_pct_val = (
            Decimal(str(model.minimum_payment_percentage))
            if model.minimum_payment_percentage is not None
            else Decimal("0.05")
        )

        account = CreditAccount(
            id=model.id,
            account_number=model.account_number or "",
            customer_id=model.customer_id or 0,
            customer_name=model.customer_name or "",
            credit_limit=CreditLimit(credit_limit_val),
            interest_rate=InterestRate(interest_rate_val),
            risk_level=model.risk_level if model.risk_level is not None else RiskLevel.LOW,
            used_credit=used_credit_val,
            pending_charges=pending_charges_val,
            accrued_interest=accrued_interest_val,
            payment_day=model.payment_day if model.payment_day is not None else 10,
            minimum_payment_percentage=min_payment_pct_val,
            grace_period_days=model.grace_period_days if model.grace_period_days is not None else 20,
            status=model.status if model.status is not None else AccountStatus.PENDING_APPROVAL,
            collection_status=model.collection_status if model.collection_status is not None else CollectionStatus.NONE,
            opened_at=model.opened_at,
            activated_at=model.activated_at,
            last_payment_date=model.last_payment_date,
            next_payment_date=model.next_payment_date,
            last_statement_date=model.last_statement_date,
            blocked_at=model.blocked_at,
            closed_at=model.closed_at,
            consecutive_on_time_payments=(
                model.consecutive_on_time_payments if model.consecutive_on_time_payments is not None else 0
            ),
            consecutive_late_payments=(
                model.consecutive_late_payments if model.consecutive_late_payments is not None else 0
            ),
            total_payments_made=model.total_payments_made if model.total_payments_made is not None else 0,
            days_overdue=model.days_overdue if model.days_overdue is not None else 0,
            last_collection_action=model.last_collection_action,
        )

        if model.created_at is not None:
            account.created_at = model.created_at
        if model.updated_at is not None:
            account.updated_at = model.updated_at

        return account

    def _to_model(self, account: CreditAccount) -> CreditAccountModel:
        """Convert entity to model."""
        return CreditAccountModel(
            account_number=account.account_number,
            customer_id=account.customer_id,
            customer_name=account.customer_name,
            credit_limit=account.credit_limit.amount,
            interest_rate=account.interest_rate.annual_rate,
            risk_level=account.risk_level,
            used_credit=account.used_credit,
            pending_charges=account.pending_charges,
            accrued_interest=account.accrued_interest,
            payment_day=account.payment_day,
            minimum_payment_percentage=account.minimum_payment_percentage,
            grace_period_days=account.grace_period_days,
            status=account.status,
            collection_status=account.collection_status,
            opened_at=account.opened_at,
            activated_at=account.activated_at,
            last_payment_date=account.last_payment_date,
            next_payment_date=account.next_payment_date,
            last_statement_date=account.last_statement_date,
            blocked_at=account.blocked_at,
            closed_at=account.closed_at,
            consecutive_on_time_payments=account.consecutive_on_time_payments,
            consecutive_late_payments=account.consecutive_late_payments,
            total_payments_made=account.total_payments_made,
            days_overdue=account.days_overdue,
            last_collection_action=account.last_collection_action,
        )

    def _update_model(self, model: CreditAccountModel, account: CreditAccount) -> None:
        """Update model from entity."""
        model.account_number = account.account_number
        model.customer_id = account.customer_id
        model.customer_name = account.customer_name
        model.credit_limit = account.credit_limit.amount
        model.interest_rate = account.interest_rate.annual_rate
        model.risk_level = account.risk_level
        model.used_credit = account.used_credit
        model.pending_charges = account.pending_charges
        model.accrued_interest = account.accrued_interest
        model.payment_day = account.payment_day
        model.minimum_payment_percentage = account.minimum_payment_percentage
        model.grace_period_days = account.grace_period_days
        model.status = account.status
        model.collection_status = account.collection_status
        model.opened_at = account.opened_at
        model.activated_at = account.activated_at
        model.last_payment_date = account.last_payment_date
        model.next_payment_date = account.next_payment_date
        model.last_statement_date = account.last_statement_date
        model.blocked_at = account.blocked_at
        model.closed_at = account.closed_at
        model.consecutive_on_time_payments = account.consecutive_on_time_payments
        model.consecutive_late_payments = account.consecutive_late_payments
        model.total_payments_made = account.total_payments_made
        model.days_overdue = account.days_overdue
        model.last_collection_action = account.last_collection_action
