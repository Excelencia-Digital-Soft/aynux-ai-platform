"""
Unit tests for Credit Domain Use Cases.

Tests:
- GetCreditBalanceUseCase
- GetPaymentScheduleUseCase
- ProcessPaymentUseCase
"""

import pytest
from datetime import date, datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.domains.credit.application.use_cases.get_credit_balance import (
    GetCreditBalanceUseCase,
    GetCreditBalanceRequest,
    GetCreditBalanceResponse,
)
from app.domains.credit.application.use_cases.get_payment_schedule import (
    GetPaymentScheduleUseCase,
    GetPaymentScheduleRequest,
    GetPaymentScheduleResponse,
    PaymentScheduleItem,
)
from app.domains.credit.application.use_cases.process_payment import (
    ProcessPaymentUseCase,
    ProcessPaymentRequest,
    ProcessPaymentResponse,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_credit_account_repository():
    """Create a mock credit account repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_payment_repository():
    """Create a mock payment repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def sample_credit_account():
    """Sample credit account object."""
    account = MagicMock()
    account.account_id = "ACC-12345"
    account.credit_limit = Decimal("50000.00")
    account.used_credit = Decimal("15000.00")
    account.next_payment_date = date(2025, 12, 15)
    account.next_payment_amount = Decimal("2500.00")
    account.interest_rate = Decimal("45.0")
    account.status = "active"
    account.minimum_payment = Decimal("2500.00")
    return account


# ============================================================================
# GetCreditBalanceUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_credit_balance_success(
    mock_credit_account_repository,
    sample_credit_account,
):
    """Test successfully getting credit balance."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = GetCreditBalanceUseCase(
        credit_account_repository=mock_credit_account_repository
    )

    request = GetCreditBalanceRequest(account_id="ACC-12345")

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is True
    assert response.account_id == "ACC-12345"
    assert response.credit_limit == Decimal("50000.00")
    assert response.used_credit == Decimal("15000.00")
    assert response.available_credit == Decimal("35000.00")
    assert response.next_payment_date == date(2025, 12, 15)
    assert response.next_payment_amount == Decimal("2500.00")
    assert response.interest_rate == Decimal("45.0")
    assert response.status == "active"
    assert response.error is None

    # Verify repository called
    mock_credit_account_repository.find_by_id.assert_called_once_with("ACC-12345")


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_credit_balance_account_not_found(
    mock_credit_account_repository,
):
    """Test getting balance for non-existent account."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = None

    use_case = GetCreditBalanceUseCase(
        credit_account_repository=mock_credit_account_repository
    )

    request = GetCreditBalanceRequest(account_id="INVALID-ACC")

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.account_id == "INVALID-ACC"
    assert response.status == "not_found"
    assert response.error == "Account not found"
    assert response.credit_limit == Decimal("0")


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_credit_balance_repository_error(
    mock_credit_account_repository,
):
    """Test handling repository error."""
    # Arrange
    mock_credit_account_repository.find_by_id.side_effect = Exception(
        "Database connection failed"
    )

    use_case = GetCreditBalanceUseCase(
        credit_account_repository=mock_credit_account_repository
    )

    request = GetCreditBalanceRequest(account_id="ACC-12345")

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.status == "error"
    assert "Database connection failed" in response.error


# ============================================================================
# GetPaymentScheduleUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_payment_schedule_success(
    mock_credit_account_repository,
    sample_credit_account,
):
    """Test successfully getting payment schedule."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = GetPaymentScheduleUseCase(
        credit_account_repository=mock_credit_account_repository
    )

    request = GetPaymentScheduleRequest(account_id="ACC-12345", months_ahead=3)

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is True
    assert response.account_id == "ACC-12345"
    assert response.total_payments == 3
    assert len(response.schedule) == 3
    assert response.total_amount == Decimal("2500.00") * 3

    # Check first payment
    first_payment = response.schedule[0]
    assert first_payment.payment_number == 1
    assert first_payment.amount == Decimal("2500.00")
    assert first_payment.status == "current"


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_payment_schedule_account_not_found(
    mock_credit_account_repository,
):
    """Test getting schedule for non-existent account."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = None

    use_case = GetPaymentScheduleUseCase(
        credit_account_repository=mock_credit_account_repository
    )

    request = GetPaymentScheduleRequest(account_id="INVALID-ACC")

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.account_id == "INVALID-ACC"
    assert response.error == "Account not found"
    assert len(response.schedule) == 0
    assert response.total_payments == 0


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_payment_schedule_with_default_months(
    mock_credit_account_repository,
    sample_credit_account,
):
    """Test getting schedule with default 6 months."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = GetPaymentScheduleUseCase(
        credit_account_repository=mock_credit_account_repository
    )

    request = GetPaymentScheduleRequest(account_id="ACC-12345")  # Default months_ahead=6

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is True
    assert response.total_payments == 6
    assert len(response.schedule) == 6


# ============================================================================
# ProcessPaymentUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_success(
    mock_credit_account_repository,
    mock_payment_repository,
    sample_credit_account,
):
    """Test successfully processing a payment."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account
    mock_credit_account_repository.save.return_value = sample_credit_account

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    request = ProcessPaymentRequest(
        account_id="ACC-12345",
        amount=Decimal("3000.00"),
        payment_type="regular",
        payment_method="transfer",
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is True
    assert response.account_id == "ACC-12345"
    assert response.amount == Decimal("3000.00")
    assert response.status == "success"
    assert response.remaining_balance == Decimal("12000.00")  # 15000 - 3000
    assert response.available_credit == Decimal("38000.00")  # 50000 - 12000
    assert response.payment_id != ""
    assert "/receipts/" in response.receipt_url

    # Verify repository interactions
    mock_credit_account_repository.find_by_id.assert_called_once()
    mock_credit_account_repository.save.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_account_not_found(
    mock_credit_account_repository,
    mock_payment_repository,
):
    """Test processing payment for non-existent account."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = None

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    request = ProcessPaymentRequest(
        account_id="INVALID-ACC",
        amount=Decimal("1000.00"),
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.status == "failed"
    assert response.error == "Account not found"


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_invalid_amount_zero(
    mock_credit_account_repository,
    mock_payment_repository,
    sample_credit_account,
):
    """Test processing payment with zero amount."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    request = ProcessPaymentRequest(
        account_id="ACC-12345",
        amount=Decimal("0.00"),
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.status == "failed"
    assert "greater than zero" in response.error


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_invalid_amount_negative(
    mock_credit_account_repository,
    mock_payment_repository,
    sample_credit_account,
):
    """Test processing payment with negative amount."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    request = ProcessPaymentRequest(
        account_id="ACC-12345",
        amount=Decimal("-100.00"),
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.status == "failed"
    assert "greater than zero" in response.error


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_exceeds_debt(
    mock_credit_account_repository,
    mock_payment_repository,
    sample_credit_account,
):
    """Test processing payment that exceeds total debt."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    # Try to pay more than 110% of debt
    request = ProcessPaymentRequest(
        account_id="ACC-12345",
        amount=Decimal("20000.00"),  # Debt is 15000, this exceeds 1.1x
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.status == "failed"
    assert "exceeds debt" in response.error


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_below_minimum(
    mock_credit_account_repository,
    mock_payment_repository,
    sample_credit_account,
):
    """Test processing payment below minimum payment threshold."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    # Minimum payment is 2500, threshold is 50% (1250)
    request = ProcessPaymentRequest(
        account_id="ACC-12345",
        amount=Decimal("1000.00"),  # Below threshold
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is False
    assert response.status == "failed"
    assert "at least" in response.error


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_process_payment_full_payment(
    mock_credit_account_repository,
    mock_payment_repository,
    sample_credit_account,
):
    """Test processing full payment to clear debt."""
    # Arrange
    mock_credit_account_repository.find_by_id.return_value = sample_credit_account
    mock_credit_account_repository.save.return_value = sample_credit_account

    use_case = ProcessPaymentUseCase(
        credit_account_repository=mock_credit_account_repository,
        payment_repository=mock_payment_repository,
    )

    request = ProcessPaymentRequest(
        account_id="ACC-12345",
        amount=Decimal("15000.00"),  # Full debt
        payment_type="full",
    )

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is True
    assert response.status == "success"
    assert response.remaining_balance == Decimal("0.00")
    assert response.available_credit == Decimal("50000.00")  # Full credit available
    assert response.payment_type == "full"
