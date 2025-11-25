"""
Credit Use Cases

Business use cases for the credit domain.
Each use case represents a single business operation.
"""

from .get_credit_balance import (
    GetCreditBalanceRequest,
    GetCreditBalanceResponse,
    GetCreditBalanceUseCase,
)
from .get_payment_schedule import (
    GetPaymentScheduleRequest,
    GetPaymentScheduleResponse,
    GetPaymentScheduleUseCase,
    PaymentScheduleItem,
)
from .process_payment import (
    ProcessPaymentRequest,
    ProcessPaymentResponse,
    ProcessPaymentUseCase,
)

__all__ = [
    # Get credit balance
    "GetCreditBalanceUseCase",
    "GetCreditBalanceRequest",
    "GetCreditBalanceResponse",
    # Process payment
    "ProcessPaymentUseCase",
    "ProcessPaymentRequest",
    "ProcessPaymentResponse",
    # Get payment schedule
    "GetPaymentScheduleUseCase",
    "GetPaymentScheduleRequest",
    "GetPaymentScheduleResponse",
    "PaymentScheduleItem",
]
