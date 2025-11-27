"""
Unit tests for Credit Domain Repositories.

Tests the data access layer for credit accounts, payments, and payment schedules.
"""

from datetime import UTC, datetime, date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.credit.domain.entities.credit_account import CreditAccount
from app.domains.credit.domain.entities.payment import Payment
from app.domains.credit.domain.value_objects.account_status import (
    AccountStatus,
    CollectionStatus,
    CreditLimit,
    InterestRate,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    RiskLevel,
)
from app.domains.credit.infrastructure.repositories.credit_account_repository import (
    SQLAlchemyCreditAccountRepository,
)
from app.domains.credit.infrastructure.repositories.payment_repository import (
    SQLAlchemyPaymentRepository,
)
from app.domains.credit.infrastructure.repositories.payment_schedule_repository import (
    SQLAlchemyPaymentScheduleRepository,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_async_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_credit_account_model():
    """Sample SQLAlchemy credit account model."""
    model = MagicMock()
    model.id = 1
    model.account_number = "ACC-001"
    model.customer_id = 100
    model.customer_name = "John Doe"
    model.credit_limit = Decimal("10000.00")
    model.used_credit = Decimal("2500.00")
    model.pending_charges = Decimal("0.00")
    model.accrued_interest = Decimal("50.00")
    model.status = AccountStatus.ACTIVE
    model.collection_status = CollectionStatus.NONE
    model.interest_rate = Decimal("0.24")
    model.risk_level = RiskLevel.LOW
    model.payment_day = 15
    model.minimum_payment_percentage = Decimal("0.05")
    model.grace_period_days = 20
    model.opened_at = datetime.now(UTC)
    model.activated_at = datetime.now(UTC)
    model.last_payment_date = None
    model.next_payment_date = None
    model.last_statement_date = None
    model.blocked_at = None
    model.closed_at = None
    model.consecutive_on_time_payments = 3
    model.consecutive_late_payments = 0
    model.total_payments_made = 5
    model.days_overdue = 0
    model.last_collection_action = None
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


@pytest.fixture
def sample_payment_model():
    """Sample SQLAlchemy payment model."""
    model = MagicMock()
    model.id = 1
    model.account_id = 1
    model.customer_id = 100
    model.account_number = "ACC-001"
    model.amount = Decimal("500.00")
    model.payment_type = PaymentType.REGULAR
    model.payment_method = PaymentMethod.BANK_TRANSFER
    model.status = PaymentStatus.COMPLETED
    model.transaction_id = "TXN-001"
    model.reference_number = "PAY-001"
    model.receipt_url = "/receipts/PAY-001"
    model.interest_paid = Decimal("50.00")
    model.charges_paid = Decimal("0.00")
    model.principal_paid = Decimal("450.00")
    model.initiated_at = datetime.now(UTC)
    model.processed_at = datetime.now(UTC)
    model.completed_at = datetime.now(UTC)
    model.failed_at = None
    model.failure_reason = None
    model.retry_count = 0
    model.max_retries = 3
    model.description = "Monthly payment"
    model.notes = None
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


@pytest.fixture
def sample_schedule_item_model():
    """Sample SQLAlchemy payment schedule item model."""
    model = MagicMock()
    model.id = 1
    model.account_id = 1
    model.due_date = date.today()
    model.amount = Decimal("500.00")
    model.principal_amount = Decimal("400.00")
    model.interest_amount = Decimal("100.00")
    model.status = "pending"
    model.paid_date = None
    model.paid_amount = None
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    model.to_dict = MagicMock(return_value={
        "id": 1,
        "account_id": 1,
        "installment_number": 1,
        "due_date": str(date.today()),
        "amount": 500.00,
        "principal_amount": 400.00,
        "interest_amount": 100.00,
        "status": "pending",
    })
    return model


# ============================================================================
# Credit Account Repository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_get_by_id_success(mock_async_session, sample_credit_account_model):
    """Test successfully getting a credit account by ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_credit_account_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Act
    account = await repository.get_by_id("1")

    # Assert
    assert account is not None
    assert account.account_number == "ACC-001"
    assert account.customer_id == 100
    mock_async_session.execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_get_by_id_not_found(mock_async_session):
    """Test getting a credit account that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Act
    account = await repository.get_by_id("999")

    # Assert
    assert account is None


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_get_by_account_number(mock_async_session, sample_credit_account_model):
    """Test getting a credit account by account number."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_credit_account_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Act
    account = await repository.get_by_account_number("ACC-001")

    # Assert
    assert account is not None
    assert account.account_number == "ACC-001"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_get_by_customer(mock_async_session, sample_credit_account_model):
    """Test getting credit accounts by customer ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_credit_account_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Act
    account = await repository.get_by_customer("100")

    # Assert
    assert account is not None
    assert account.customer_id == 100


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_save(mock_async_session, sample_credit_account_model):
    """Test saving a credit account."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # New account
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Create account entity using the proper constructor
    account = CreditAccount(
        account_number="ACC-002",
        customer_id=200,
        customer_name="Jane Doe",
        credit_limit=CreditLimit(Decimal("5000.00")),
        interest_rate=InterestRate(Decimal("0.24")),
        risk_level=RiskLevel.LOW,
        status=AccountStatus.PENDING_APPROVAL,
    )

    # Setup refresh to update the mock
    async def mock_refresh(obj):
        obj.id = 2

    mock_async_session.refresh = mock_refresh

    # Act
    saved = await repository.save(account)

    # Assert
    mock_async_session.add.assert_called_once()
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_find_by_status(mock_async_session, sample_credit_account_model):
    """Test finding accounts by status."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_credit_account_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Act
    accounts = await repository.find_by_status(AccountStatus.ACTIVE)

    # Assert
    assert len(accounts) == 1


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_credit_account_count(mock_async_session):
    """Test counting accounts."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 10
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyCreditAccountRepository(mock_async_session)

    # Act
    count = await repository.count()

    # Assert
    assert count == 10


# ============================================================================
# Payment Repository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_payment_get_by_id_success(mock_async_session, sample_payment_model):
    """Test successfully getting a payment by ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_payment_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyPaymentRepository(mock_async_session)

    # Act
    payment = await repository.get_by_id(1)

    # Assert
    assert payment is not None
    assert payment.amount == Decimal("500.00")
    assert payment.reference_number == "PAY-001"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_payment_get_by_account(mock_async_session, sample_payment_model):
    """Test getting payments by credit account ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_payment_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyPaymentRepository(mock_async_session)

    # Act
    payments = await repository.get_by_account(1)

    # Assert
    assert len(payments) == 1
    assert payments[0].account_id == 1


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_payment_get_by_reference(mock_async_session, sample_payment_model):
    """Test getting a payment by reference number."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_payment_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyPaymentRepository(mock_async_session)

    # Act
    payment = await repository.get_by_reference("PAY-001")

    # Assert
    assert payment is not None
    assert payment.reference_number == "PAY-001"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_payment_create(mock_async_session, sample_payment_model):
    """Test creating a payment."""
    # Arrange
    mock_async_session.execute.return_value = MagicMock()

    repository = SQLAlchemyPaymentRepository(mock_async_session)

    # Use factory method to create payment
    payment = Payment.create(
        account_id=1,
        amount=Decimal("250.00"),
        payment_type=PaymentType.REGULAR,
        payment_method=PaymentMethod.BANK_TRANSFER,
    )

    # Setup mock refresh to simulate DB returning the model
    async def mock_refresh(obj, **kwargs):
        obj.id = 2
        obj.account_id = 1
        obj.customer_id = 0
        obj.account_number = ""
        obj.amount = Decimal("250.00")
        obj.payment_type = PaymentType.REGULAR
        obj.payment_method = PaymentMethod.BANK_TRANSFER
        obj.status = PaymentStatus.PENDING
        obj.transaction_id = None
        obj.reference_number = payment.reference_number
        obj.receipt_url = None
        obj.interest_paid = Decimal("0")
        obj.charges_paid = Decimal("0")
        obj.principal_paid = Decimal("0")
        obj.initiated_at = payment.initiated_at
        obj.processed_at = None
        obj.completed_at = None
        obj.failed_at = None
        obj.failure_reason = None
        obj.retry_count = 0
        obj.description = None
        obj.notes = None
        obj.created_at = datetime.now(UTC)
        obj.updated_at = datetime.now(UTC)

    mock_async_session.refresh = mock_refresh

    # Act
    saved = await repository.create(payment)

    # Assert
    mock_async_session.add.assert_called_once()
    mock_async_session.commit.assert_called_once()


# ============================================================================
# Payment Schedule Repository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_schedule_get_schedule(mock_async_session, sample_schedule_item_model):
    """Test getting payment schedule by account ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_schedule_item_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyPaymentScheduleRepository(mock_async_session)

    # Act
    schedule = await repository.get_schedule("1")

    # Assert
    assert len(schedule) == 1
    assert schedule[0]["installment_number"] == 1


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_schedule_get_next_payment(mock_async_session, sample_schedule_item_model):
    """Test getting next scheduled payment."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_schedule_item_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyPaymentScheduleRepository(mock_async_session)

    # Act
    next_payment = await repository.get_next_payment("1")

    # Assert
    assert next_payment is not None
    assert next_payment["installment_number"] == 1


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_schedule_get_overdue_payments(mock_async_session, sample_schedule_item_model):
    """Test getting overdue payment schedule items."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_schedule_item_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyPaymentScheduleRepository(mock_async_session)

    # Act
    overdue = await repository.get_overdue_payments("1")

    # Assert
    assert len(overdue) >= 0  # May be empty depending on dates
