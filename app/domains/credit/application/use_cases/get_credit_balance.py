"""
Get Credit Balance Use Case

Use case for retrieving credit account balance and status information.
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from app.core.interfaces.repository import IRepository

logger = logging.getLogger(__name__)


@dataclass
class GetCreditBalanceRequest:
    """Request for getting credit balance"""

    account_id: str
    user_id: Optional[str] = None  # For authorization


@dataclass
class GetCreditBalanceResponse:
    """Response with credit balance information"""

    account_id: str
    credit_limit: Decimal
    used_credit: Decimal
    available_credit: Decimal
    next_payment_date: Optional[date]
    next_payment_amount: Optional[Decimal]
    interest_rate: Decimal
    status: str  # 'active', 'blocked', 'overdue', 'closed'
    success: bool
    error: Optional[str] = None


class GetCreditBalanceUseCase:
    """
    Use case for getting credit balance.

    Single Responsibility: Only handles credit balance retrieval
    Dependency Inversion: Depends on IRepository interface
    """

    def __init__(self, credit_account_repository: IRepository):
        """
        Initialize use case.

        Args:
            credit_account_repository: Repository for credit account data access
        """
        self.account_repo = credit_account_repository

    async def execute(self, request: GetCreditBalanceRequest) -> GetCreditBalanceResponse:
        """
        Execute use case to get credit balance.

        Args:
            request: Request parameters

        Returns:
            Response with balance information
        """
        try:
            # Get account from repository
            account = await self.account_repo.find_by_id(request.account_id)

            if not account:
                return GetCreditBalanceResponse(
                    account_id=request.account_id,
                    credit_limit=Decimal("0"),
                    used_credit=Decimal("0"),
                    available_credit=Decimal("0"),
                    next_payment_date=None,
                    next_payment_amount=None,
                    interest_rate=Decimal("0"),
                    status="not_found",
                    success=False,
                    error="Account not found",
                )

            # Calculate available credit
            available_credit = account.credit_limit - account.used_credit

            return GetCreditBalanceResponse(
                account_id=account.account_id,
                credit_limit=account.credit_limit,
                used_credit=account.used_credit,
                available_credit=available_credit,
                next_payment_date=getattr(account, "next_payment_date", None),
                next_payment_amount=getattr(account, "next_payment_amount", None),
                interest_rate=getattr(account, "interest_rate", Decimal("0")),
                status=getattr(account, "status", "active"),
                success=True,
            )

        except Exception as e:
            logger.error(f"Error getting credit balance: {e}", exc_info=True)
            return GetCreditBalanceResponse(
                account_id=request.account_id,
                credit_limit=Decimal("0"),
                used_credit=Decimal("0"),
                available_credit=Decimal("0"),
                next_payment_date=None,
                next_payment_amount=None,
                interest_rate=Decimal("0"),
                status="error",
                success=False,
                error=str(e),
            )
