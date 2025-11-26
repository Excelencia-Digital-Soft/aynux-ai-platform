"""
Process Payment Use Case

Use case for processing credit account payments.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from app.core.interfaces.repository import IRepository

logger = logging.getLogger(__name__)


@dataclass
class ProcessPaymentRequest:
    """Request for processing payment"""

    account_id: str
    amount: Decimal
    payment_type: str = "regular"  # 'regular', 'minimum', 'full'
    payment_method: str = "transfer"  # 'transfer', 'card', 'cash'


@dataclass
class ProcessPaymentResponse:
    """Response from payment processing"""

    payment_id: str
    account_id: str
    amount: Decimal
    payment_type: str
    status: str  # 'success', 'failed', 'pending'
    transaction_date: datetime
    remaining_balance: Decimal
    available_credit: Decimal
    receipt_url: str
    success: bool
    error: Optional[str] = None


class ProcessPaymentUseCase:
    """
    Use case for processing payments.

    Single Responsibility: Only handles payment processing
    Dependency Inversion: Depends on repository interfaces
    """

    def __init__(
        self,
        credit_account_repository: IRepository,
        payment_repository: IRepository,
    ):
        """
        Initialize use case.

        Args:
            credit_account_repository: Repository for credit accounts
            payment_repository: Repository for payments
        """
        self.account_repo = credit_account_repository
        self.payment_repo = payment_repository

    async def execute(self, request: ProcessPaymentRequest) -> ProcessPaymentResponse:
        """
        Execute payment processing.

        Args:
            request: Payment request

        Returns:
            Payment response
        """
        try:
            # 1. Get account
            account = await self.account_repo.find_by_id(request.account_id)

            if not account:
                return self._error_response(request, "Account not found")

            # 2. Validate payment
            validation = self._validate_payment(request.amount, account)
            if not validation["valid"]:
                return self._error_response(request, validation["reason"])

            # 3. Calculate new balances
            new_used_credit = account.used_credit - request.amount
            new_available_credit = account.credit_limit - new_used_credit

            # 4. Create payment record
            payment_id = str(uuid.uuid4())
            # TODO: Save payment record when Payment entity is implemented
            # payment_data = {
            #     "payment_id": payment_id,
            #     "account_id": request.account_id,
            #     "amount": request.amount,
            #     "payment_type": request.payment_type,
            #     "payment_method": request.payment_method,
            #     "status": "success",
            #     "transaction_date": datetime.now(UTC),
            # }
            # await self.payment_repo.save(payment_data)

            # 6. Update account balance
            account.used_credit = new_used_credit
            await self.account_repo.save(account)

            return ProcessPaymentResponse(
                payment_id=payment_id,
                account_id=request.account_id,
                amount=request.amount,
                payment_type=request.payment_type,
                status="success",
                transaction_date=datetime.now(UTC),
                remaining_balance=new_used_credit,
                available_credit=new_available_credit,
                receipt_url=f"/receipts/{payment_id}",
                success=True,
            )

        except Exception as e:
            logger.error(f"Error processing payment: {e}", exc_info=True)
            return self._error_response(request, str(e))

    def _validate_payment(self, amount: Decimal, account: Any) -> Dict[str, Any]:
        """
        Validate payment amount.

        Args:
            amount: Payment amount
            account: Credit account

        Returns:
            Validation result
        """
        if amount <= 0:
            return {
                "valid": False,
                "reason": "Payment amount must be greater than zero",
            }

        minimum_payment = getattr(account, "minimum_payment", Decimal("0"))
        if minimum_payment and amount < minimum_payment * Decimal("0.5"):
            return {
                "valid": False,
                "reason": f"Payment must be at least ${minimum_payment * Decimal('0.5'):,.2f}",
            }

        if amount > account.used_credit * Decimal("1.1"):
            return {
                "valid": False,
                "reason": "Payment amount exceeds debt",
            }

        return {"valid": True}

    def _error_response(self, request: ProcessPaymentRequest, error: str) -> ProcessPaymentResponse:
        """Generate error response"""
        return ProcessPaymentResponse(
            payment_id="",
            account_id=request.account_id,
            amount=request.amount,
            payment_type=request.payment_type,
            status="failed",
            transaction_date=datetime.now(UTC),
            remaining_balance=Decimal("0"),
            available_credit=Decimal("0"),
            receipt_url="",
            success=False,
            error=error,
        )
