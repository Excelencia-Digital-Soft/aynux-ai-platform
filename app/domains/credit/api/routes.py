"""
Credit API Routes

FastAPI router for credit domain endpoints.
"""

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
    result = await use_case.execute(account_id=account_id)

    if not result.success:
        raise HTTPException(status_code=404, detail=result.message)

    return [
        PaymentScheduleResponse(
            installment_number=item.installment_number,
            due_date=item.due_date,
            amount=item.amount,
            principal=item.principal,
            interest=item.interest,
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
    result = await use_case.execute(
        account_id=request.account_id,
        amount=request.amount,
        payment_method=request.payment_method,
        reference=request.reference,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return PaymentResponse(
        id=result.payment.id,
        account_id=result.payment.account_id,
        amount=result.payment.amount,
        payment_date=result.payment.payment_date,
        status=result.payment.status.value,
        reference=result.payment.reference,
    )


__all__ = ["router"]
