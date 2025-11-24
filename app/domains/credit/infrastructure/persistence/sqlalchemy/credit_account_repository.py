"""
Credit Account Repository Implementation

Repository implementation for CreditAccount entity following Repository Pattern.
Implements IRepository interface for dependency inversion.

Note: This implementation uses mock data until CreditAccount model is created in database.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.interfaces.repository import IRepository

logger = logging.getLogger(__name__)


# Temporary mock CreditAccount class until DB model is created
class CreditAccount:
    """Mock Credit Account entity"""

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.account_id = kwargs.get("account_id")
        self.user_id = kwargs.get("user_id")
        self.credit_limit = kwargs.get("credit_limit", Decimal("50000.00"))
        self.used_credit = kwargs.get("used_credit", Decimal("15000.00"))
        self.available_credit = kwargs.get("available_credit", Decimal("35000.00"))
        self.next_payment_date = kwargs.get("next_payment_date")
        self.next_payment_amount = kwargs.get("next_payment_amount")
        self.minimum_payment = kwargs.get("minimum_payment", Decimal("2500.00"))
        self.interest_rate = kwargs.get("interest_rate", Decimal("18.5"))
        self.status = kwargs.get("status", "active")
        self.created_at = kwargs.get("created_at")
        self.updated_at = kwargs.get("updated_at")


class CreditAccountRepository(IRepository[CreditAccount, str]):
    """
    Credit Account Repository implementation.

    Single Responsibility: Data access for CreditAccount entity only
    Dependency Inversion: Implements IRepository interface

    Note: Currently uses in-memory mock data. Will be replaced with
    actual SQLAlchemy implementation when DB model is ready.
    """

    def __init__(self):
        """Initialize repository with mock data"""
        # Mock data storage (will be replaced with DB)
        self._mock_accounts: Dict[str, CreditAccount] = self._init_mock_data()

    def _init_mock_data(self) -> Dict[str, CreditAccount]:
        """Initialize mock credit accounts"""
        return {
            "ACC001": CreditAccount(
                id=1,
                account_id="ACC001",
                user_id="USER001",
                credit_limit=Decimal("50000.00"),
                used_credit=Decimal("15000.00"),
                available_credit=Decimal("35000.00"),
                next_payment_date=date.today() + timedelta(days=15),
                next_payment_amount=Decimal("2500.00"),
                minimum_payment=Decimal("2500.00"),
                interest_rate=Decimal("18.5"),
                status="active",
            ),
            "ACC002": CreditAccount(
                id=2,
                account_id="ACC002",
                user_id="USER002",
                credit_limit=Decimal("30000.00"),
                used_credit=Decimal("25000.00"),
                available_credit=Decimal("5000.00"),
                next_payment_date=date.today() + timedelta(days=5),
                next_payment_amount=Decimal("3500.00"),
                minimum_payment=Decimal("3500.00"),
                interest_rate=Decimal("20.0"),
                status="active",
            ),
        }

    async def find_by_id(self, id: str) -> Optional[CreditAccount]:
        """
        Find credit account by ID.

        Args:
            id: Account ID

        Returns:
            CreditAccount or None if not found
        """
        try:
            # TODO: Replace with actual database query
            # with get_db_context() as db:
            #     return db.query(CreditAccount).filter(CreditAccount.account_id == id).first()

            return self._mock_accounts.get(id)

        except Exception as e:
            logger.error(f"Error finding credit account by ID {id}: {e}", exc_info=True)
            return None

    async def find_all(self, skip: int = 0, limit: int = 100) -> List[CreditAccount]:
        """
        Find all credit accounts with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of credit accounts
        """
        try:
            # TODO: Replace with actual database query
            accounts = list(self._mock_accounts.values())
            return accounts[skip : skip + limit]

        except Exception as e:
            logger.error(f"Error finding all credit accounts: {e}", exc_info=True)
            return []

    async def save(self, entity: CreditAccount) -> CreditAccount:
        """
        Save (create or update) credit account.

        Args:
            entity: CreditAccount to save

        Returns:
            Saved credit account
        """
        try:
            # TODO: Replace with actual database save
            # with get_db_context() as db:
            #     db.add(entity)
            #     db.commit()
            #     db.refresh(entity)
            #     return entity

            self._mock_accounts[entity.account_id] = entity
            logger.info(f"Saved credit account: {entity.account_id}")
            return entity

        except Exception as e:
            logger.error(f"Error saving credit account: {e}", exc_info=True)
            raise

    async def delete(self, id: str) -> bool:
        """
        Delete credit account by ID (soft delete - set status=closed).

        Args:
            id: Account ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            # TODO: Replace with actual database delete
            account = self._mock_accounts.get(id)
            if account:
                account.status = "closed"
                logger.info(f"Closed credit account: {id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting credit account {id}: {e}", exc_info=True)
            return False

    async def exists(self, id: str) -> bool:
        """
        Check if credit account exists.

        Args:
            id: Account ID

        Returns:
            True if exists, False otherwise
        """
        try:
            return id in self._mock_accounts

        except Exception as e:
            logger.error(f"Error checking credit account exists {id}: {e}", exc_info=True)
            return False

    async def count(self) -> int:
        """
        Count total credit accounts.

        Returns:
            Total count of active accounts
        """
        try:
            # TODO: Replace with actual database count
            return len([a for a in self._mock_accounts.values() if a.status == "active"])

        except Exception as e:
            logger.error(f"Error counting credit accounts: {e}", exc_info=True)
            return 0

    # Additional methods specific to Credit domain

    async def find_by_user_id(self, user_id: str) -> Optional[CreditAccount]:
        """
        Find credit account by user ID.

        Args:
            user_id: User ID

        Returns:
            CreditAccount or None
        """
        try:
            for account in self._mock_accounts.values():
                if account.user_id == user_id:
                    return account
            return None

        except Exception as e:
            logger.error(f"Error finding account by user ID {user_id}: {e}", exc_info=True)
            return None

    async def find_overdue_accounts(self) -> List[CreditAccount]:
        """
        Find all overdue accounts.

        Returns:
            List of overdue accounts
        """
        try:
            # TODO: Replace with actual database query
            today = date.today()
            overdue = []

            for account in self._mock_accounts.values():
                if account.status == "active" and account.next_payment_date:
                    if account.next_payment_date < today:
                        overdue.append(account)

            return overdue

        except Exception as e:
            logger.error(f"Error finding overdue accounts: {e}", exc_info=True)
            return []
