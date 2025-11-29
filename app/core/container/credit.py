"""
Credit Domain Container.

Single Responsibility: Wire all credit domain dependencies.
"""

import logging
from typing import TYPE_CHECKING

from app.core.interfaces.repository import IRepository
from app.domains.credit.application.use_cases import (
    GetCreditBalanceUseCase,
    GetPaymentScheduleUseCase,
    ProcessPaymentUseCase,
)
from app.domains.credit.infrastructure.persistence.sqlalchemy import CreditAccountRepository
from app.domains.credit.infrastructure.repositories import (
    SQLAlchemyCreditAccountRepository,
    SQLAlchemyPaymentRepository,
    SQLAlchemyPaymentScheduleRepository,
)

if TYPE_CHECKING:
    from app.core.container.base import BaseContainer

logger = logging.getLogger(__name__)


class CreditContainer:
    """
    Credit domain container.

    Single Responsibility: Create credit repositories and use cases.
    """

    def __init__(self, base: "BaseContainer"):
        """
        Initialize credit container.

        Args:
            base: BaseContainer with shared singletons
        """
        self._base = base

    # ==================== REPOSITORIES ====================

    def create_credit_account_repository(self) -> IRepository:
        """Create Credit Account Repository (legacy)."""
        return CreditAccountRepository()

    def create_payment_repository(self) -> IRepository:
        """
        Create Payment Repository.

        Note: Currently returns CreditAccountRepository as placeholder.
        TODO: Implement separate PaymentRepository when Payment model is ready.
        """
        return CreditAccountRepository()

    def create_credit_account_repository_sqlalchemy(self, db) -> SQLAlchemyCreditAccountRepository:
        """Create Credit Account Repository (SQLAlchemy)."""
        return SQLAlchemyCreditAccountRepository(session=db)

    def create_payment_repository_sqlalchemy(self, db) -> SQLAlchemyPaymentRepository:
        """Create Payment Repository (SQLAlchemy)."""
        return SQLAlchemyPaymentRepository(session=db)

    def create_payment_schedule_repository(self, db) -> SQLAlchemyPaymentScheduleRepository:
        """Create Payment Schedule Repository."""
        return SQLAlchemyPaymentScheduleRepository(session=db)

    # ==================== USE CASES ====================

    def create_get_credit_balance_use_case(self) -> GetCreditBalanceUseCase:
        """Create GetCreditBalanceUseCase with dependencies."""
        return GetCreditBalanceUseCase(credit_account_repository=self.create_credit_account_repository())

    def create_process_payment_use_case(self) -> ProcessPaymentUseCase:
        """Create ProcessPaymentUseCase with dependencies."""
        return ProcessPaymentUseCase(
            credit_account_repository=self.create_credit_account_repository(),
            payment_repository=self.create_payment_repository(),
        )

    def create_get_payment_schedule_use_case(self) -> GetPaymentScheduleUseCase:
        """Create GetPaymentScheduleUseCase with dependencies."""
        return GetPaymentScheduleUseCase(credit_account_repository=self.create_credit_account_repository())
