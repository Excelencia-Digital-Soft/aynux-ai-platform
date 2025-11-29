"""
Credit API Dependencies

FastAPI dependencies for the credit domain.
"""

from app.core.container import DependencyContainer
from app.domains.credit.application.use_cases import (
    GetPaymentScheduleUseCase,
    ProcessPaymentUseCase,
)


def get_container() -> DependencyContainer:
    """Get dependency container instance."""
    return DependencyContainer()


def get_payment_schedule_use_case() -> GetPaymentScheduleUseCase:
    """Get GetPaymentScheduleUseCase instance."""
    return get_container().create_get_payment_schedule_use_case()


def get_process_payment_use_case() -> ProcessPaymentUseCase:
    """Get ProcessPaymentUseCase instance."""
    return get_container().create_process_payment_use_case()


__all__ = [
    "get_container",
    "get_payment_schedule_use_case",
    "get_process_payment_use_case",
]
