"""
Get Payment Schedule Use Case

Use case for retrieving payment schedule for a credit account.
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.interfaces.repository import IRepository

logger = logging.getLogger(__name__)


@dataclass
class PaymentScheduleItem:
    """Single payment in the schedule"""

    payment_number: int
    due_date: date
    amount: Decimal
    status: str  # 'pending', 'current', 'overdue', 'paid'


@dataclass
class GetPaymentScheduleRequest:
    """Request for getting payment schedule"""

    account_id: str
    months_ahead: int = 6  # How many months to include


@dataclass
class GetPaymentScheduleResponse:
    """Response with payment schedule"""

    account_id: str
    schedule: List[PaymentScheduleItem]
    total_payments: int
    total_amount: Decimal
    success: bool
    error: Optional[str] = None


class GetPaymentScheduleUseCase:
    """
    Use case for getting payment schedule.

    Single Responsibility: Only handles payment schedule retrieval
    """

    def __init__(self, credit_account_repository: IRepository):
        """
        Initialize use case.

        Args:
            credit_account_repository: Repository for credit accounts
        """
        self.account_repo = credit_account_repository

    async def execute(self, request: GetPaymentScheduleRequest) -> GetPaymentScheduleResponse:
        """
        Execute use case to get payment schedule.

        Args:
            request: Request parameters

        Returns:
            Response with payment schedule
        """
        try:
            # Get account
            account = await self.account_repo.find_by_id(request.account_id)

            if not account:
                return GetPaymentScheduleResponse(
                    account_id=request.account_id,
                    schedule=[],
                    total_payments=0,
                    total_amount=Decimal("0"),
                    success=False,
                    error="Account not found",
                )

            # Generate payment schedule
            schedule = self._generate_schedule(account, request.months_ahead)

            # Calculate totals
            total_amount = sum(item.amount for item in schedule)

            return GetPaymentScheduleResponse(
                account_id=request.account_id,
                schedule=schedule,
                total_payments=len(schedule),
                total_amount=total_amount,
                success=True,
            )

        except Exception as e:
            logger.error(f"Error getting payment schedule: {e}", exc_info=True)
            return GetPaymentScheduleResponse(
                account_id=request.account_id,
                schedule=[],
                total_payments=0,
                total_amount=Decimal("0"),
                success=False,
                error=str(e),
            )

    def _generate_schedule(self, account: Any, months_ahead: int) -> List[PaymentScheduleItem]:
        """
        Generate payment schedule for account.

        Args:
            account: Credit account
            months_ahead: Number of months to project

        Returns:
            List of payment schedule items
        """
        schedule = []

        # Get next payment date from account
        current_date = getattr(account, "next_payment_date", date.today())
        minimum_payment = getattr(account, "minimum_payment", Decimal("2500.00"))

        for i in range(months_ahead):
            # Calculate payment date (add 30 days for each month)
            payment_date = (
                date(current_date.year, current_date.month + i, current_date.day)
                if current_date.month + i <= 12
                else date(
                    current_date.year + (current_date.month + i - 1) // 12,
                    (current_date.month + i - 1) % 12 + 1,
                    current_date.day,
                )
            )

            # Determine status
            if i == 0:
                status = "current"
            elif payment_date < date.today():
                status = "overdue"
            else:
                status = "pending"

            schedule.append(
                PaymentScheduleItem(
                    payment_number=i + 1,
                    due_date=payment_date,
                    amount=minimum_payment,
                    status=status,
                )
            )

        return schedule
