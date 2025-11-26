"""
Credit Application Ports

Interface definitions (ports) for the Credit domain.
Uses Protocol for structural typing.
"""

from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.domains.credit.domain.entities.credit_account import CreditAccount
from app.domains.credit.domain.entities.payment import Payment


@runtime_checkable
class ICreditAccountRepository(Protocol):
    """
    Interface for credit account repository.

    Defines the contract for credit account data access.
    """

    async def get_by_id(self, account_id: str) -> CreditAccount | None:
        """Get account by ID"""
        ...

    async def get_by_customer(self, customer_id: str) -> CreditAccount | None:
        """Get account by customer ID"""
        ...

    async def get_by_account_number(self, account_number: str) -> CreditAccount | None:
        """Get account by account number"""
        ...

    async def update_balance(self, account_id: str, new_balance: Decimal) -> CreditAccount | None:
        """Update account balance"""
        ...

    async def save(self, account: CreditAccount) -> CreditAccount:
        """Save a credit account"""
        ...


@runtime_checkable
class IPaymentRepository(Protocol):
    """
    Interface for payment repository.

    Defines the contract for payment data access.
    """

    async def create(self, payment: Payment) -> Payment:
        """Create a new payment"""
        ...

    async def get_by_id(self, payment_id: str) -> Payment | None:
        """Get payment by ID"""
        ...

    async def get_by_account(
        self,
        account_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 20,
    ) -> list[Payment]:
        """Get payments by account"""
        ...

    async def get_total_paid(self, account_id: str) -> Decimal:
        """Get total amount paid for account"""
        ...


@runtime_checkable
class IPaymentScheduleRepository(Protocol):
    """
    Interface for payment schedule repository.

    Defines the contract for payment schedule data access.
    """

    async def get_schedule(self, account_id: str) -> list[dict]:
        """Get payment schedule for account"""
        ...

    async def get_next_payment(self, account_id: str) -> dict | None:
        """Get next scheduled payment"""
        ...

    async def get_overdue_payments(self, account_id: str) -> list[dict]:
        """Get overdue payments"""
        ...

    async def update_schedule_item(self, schedule_item_id: str, status: str) -> dict | None:
        """Update schedule item status"""
        ...


__all__ = [
    "ICreditAccountRepository",
    "IPaymentRepository",
    "IPaymentScheduleRepository",
]
