"""
Credit Use Cases

Business use cases for the credit domain.
Each use case represents a single business operation.
"""

from .get_credit_balance import (
    GetCreditBalanceUseCase,
    GetCreditBalanceRequest,
    GetCreditBalanceResponse,
)
from .process_payment import (
    ProcessPaymentUseCase,
    ProcessPaymentRequest,
    ProcessPaymentResponse,
)
from .get_payment_schedule import (
    GetPaymentScheduleUseCase,
    GetPaymentScheduleRequest,
    GetPaymentScheduleResponse,
    PaymentScheduleItem,
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
