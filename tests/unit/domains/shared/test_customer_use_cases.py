"""
Unit tests for Customer Use Cases (Shared Domain).

Tests:
- GetOrCreateCustomerUseCase
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from app.domains.shared.application.use_cases.customer_use_cases import (
    GetOrCreateCustomerUseCase,
)
from app.models.db import Customer


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def sample_customer():
    """Sample customer object."""
    customer = Customer(
        id=1,
        phone_number="+5491234567890",
        profile_name="John Doe",
        first_contact=datetime.now(timezone.utc),
        last_contact=datetime.now(timezone.utc),
        total_interactions=5,
    )
    return customer


# ============================================================================
# GetOrCreateCustomerUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_existing_customer(mock_db_session, sample_customer):
    """Test getting an existing customer."""
    # Arrange
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = sample_customer
    mock_db_session.query.return_value = mock_query

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name="John Doe"
        )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"
    assert result["profile_name"] == "John Doe"
    assert result["total_interactions"] == 6  # Should increment

    # Verify customer was updated (last_contact, total_interactions)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_create_new_customer(mock_db_session):
    """Test creating a new customer."""
    # Arrange
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None  # No existing customer
    mock_db_session.query.return_value = mock_query

    # Mock the newly created customer
    new_customer = Customer(
        id=1,
        phone_number="+5491234567890",
        profile_name="Jane Doe",
        first_contact=datetime.now(timezone.utc),
        last_contact=datetime.now(timezone.utc),
        total_interactions=1,
    )

    def add_customer(customer):
        # Simulate adding customer to session
        pass

    def commit_side_effect():
        # Simulate commit assigning ID
        pass

    def refresh_side_effect(customer):
        # Copy data from new_customer
        for key, value in new_customer.__dict__.items():
            if not key.startswith("_"):
                setattr(customer, key, value)

    mock_db_session.add.side_effect = add_customer
    mock_db_session.commit.side_effect = commit_side_effect
    mock_db_session.refresh.side_effect = refresh_side_effect

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name="Jane Doe"
        )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"
    assert result["profile_name"] == "Jane Doe"
    assert result["total_interactions"] == 1

    # Verify customer was created
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_race_condition_handled(mock_db_session, sample_customer):
    """Test handling race condition when creating customer."""
    # Arrange
    mock_query = MagicMock()

    # First call: no customer found
    # Second call (after race condition): customer found
    mock_query.filter.return_value.first.side_effect = [None, sample_customer]
    mock_db_session.query.return_value = mock_query

    # Simulate unique constraint violation on commit
    unique_constraint_error = Exception("unique constraint failed")

    def commit_side_effect():
        raise unique_constraint_error

    mock_db_session.commit.side_effect = commit_side_effect

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name="John Doe"
        )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"

    # Verify rollback was called
    mock_db_session.rollback.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_update_profile_name(mock_db_session):
    """Test updating profile name when customer exists without one."""
    # Arrange
    existing_customer = Customer(
        id=1,
        phone_number="+5491234567890",
        profile_name=None,  # No profile name
        first_contact=datetime.now(timezone.utc),
        last_contact=datetime.now(timezone.utc),
        total_interactions=3,
    )

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = existing_customer
    mock_db_session.query.return_value = mock_query

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name="New Name"
        )

    # Assert
    assert result is not None
    # Profile name should be updated since it was None
    assert existing_customer.profile_name == "New Name"
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_keep_existing_profile_name(mock_db_session, sample_customer):
    """Test keeping existing profile name when customer already has one."""
    # Arrange
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = sample_customer
    mock_db_session.query.return_value = mock_query

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name="Different Name"  # Try to change
        )

    # Assert
    assert result is not None
    # Profile name should remain "John Doe" (original)
    assert sample_customer.profile_name == "John Doe"


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_database_error(mock_db_session):
    """Test handling general database error."""
    # Arrange
    mock_query = MagicMock()
    mock_query.filter.side_effect = Exception("Database connection lost")
    mock_db_session.query.return_value = mock_query

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name="John Doe"
        )

    # Assert
    assert result is None  # Should return None on error


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_without_profile_name(mock_db_session):
    """Test creating customer without providing profile name."""
    # Arrange
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_db_session.query.return_value = mock_query

    new_customer = Customer(
        id=1,
        phone_number="+5491234567890",
        profile_name=None,
        first_contact=datetime.now(timezone.utc),
        last_contact=datetime.now(timezone.utc),
        total_interactions=1,
    )

    def refresh_side_effect(customer):
        for key, value in new_customer.__dict__.items():
            if not key.startswith("_"):
                setattr(customer, key, value)

    mock_db_session.refresh.side_effect = refresh_side_effect

    use_case = GetOrCreateCustomerUseCase()

    # Act
    with patch("app.domains.shared.application.use_cases.customer_use_cases.get_db_context") as mock_context:
        mock_context.return_value.__enter__.return_value = mock_db_session

        result = await use_case.execute(
            phone_number="+5491234567890",
            profile_name=None
        )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"
    assert result.get("profile_name") is None or result.get("profile_name") == ""
