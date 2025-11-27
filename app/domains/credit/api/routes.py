"""
Credit API Routes

FastAPI router for credit domain endpoints.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from app.domains.credit.api.dependencies import (
    get_payment_schedule_use_case,
    get_process_payment_use_case,
)
from app.domains.credit.api.schemas import (
    PaymentRequest,
    PaymentResponse,
    PaymentScheduleResponse,
)
from app.domains.credit.application.use_cases import (
    GetPaymentScheduleUseCase,
    ProcessPaymentUseCase,
)

router = APIRouter(prefix="/credit", tags=["Credit"])


@router.get("/accounts/{account_id}/schedule", response_model=list[PaymentScheduleResponse])
async def get_payment_schedule(
    account_id: int,
    use_case: GetPaymentScheduleUseCase = Depends(get_payment_schedule_use_case),
):
    """Get payment schedule for an account."""
    from app.domains.credit.application.use_cases.get_payment_schedule import (
        GetPaymentScheduleRequest,
    )

    request = GetPaymentScheduleRequest(account_id=str(account_id))
    result = await use_case.execute(request)

    if not result.success:
        raise HTTPException(status_code=404, detail=result.error or "Unknown error")

    return [
        PaymentScheduleResponse(
            installment_number=item.payment_number,
            due_date=item.due_date,
            amount=item.amount,
            principal=item.amount,  # Simplified - full breakdown not in current DTO
            interest=Decimal("0"),  # Simplified - full breakdown not in current DTO
            status=item.status,
        )
        for item in result.schedule
    ]


@router.post("/payments", response_model=PaymentResponse)
async def process_payment(
    request: PaymentRequest,
    use_case: ProcessPaymentUseCase = Depends(get_process_payment_use_case),
):
    """Process a payment."""
    from app.domains.credit.application.use_cases.process_payment import (
        ProcessPaymentRequest,
    )

    payment_request = ProcessPaymentRequest(
        account_id=str(request.account_id),
        amount=request.amount,
        payment_method=request.payment_method,
    )
    result = await use_case.execute(payment_request)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Unknown error")

    return PaymentResponse(
        id=result.payment_id,  # UUID string from use case
        account_id=int(result.account_id),
        amount=result.amount,
        payment_date=result.transaction_date,
        status=result.status,
        reference=result.receipt_url,
    )


__all__ = ["router"]
