"""
Unit tests for Customer Use Cases (Shared Domain).

Tests:
- GetOrCreateCustomerUseCase
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.domains.shared.application.use_cases.customer_use_cases import (
    GetOrCreateCustomerUseCase,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_customer_repository():
    """Create a mock customer repository."""
    repository = AsyncMock()
    return repository


@pytest.fixture
def sample_customer():
    """Sample customer data."""
    return {
        "id": "1",
        "phone_number": "+5491234567890",
        "profile_name": "John Doe",
        "first_contact": datetime.now(timezone.utc).isoformat(),
        "last_contact": datetime.now(timezone.utc).isoformat(),
        "total_interactions": 5,
    }


# ============================================================================
# GetOrCreateCustomerUseCase Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_existing_customer(mock_customer_repository, sample_customer):
    """Test getting an existing customer."""
    # Arrange
    mock_customer_repository.get_or_create.return_value = {
        **sample_customer,
        "total_interactions": sample_customer["total_interactions"] + 1,
    }

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name="John Doe"
    )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"
    assert result["profile_name"] == "John Doe"
    assert result["total_interactions"] == 6  # Incremented

    # Verify repository was called correctly
    mock_customer_repository.get_or_create.assert_called_once_with(
        phone_number="+5491234567890",
        profile_name="John Doe"
    )


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_create_new_customer(mock_customer_repository):
    """Test creating a new customer."""
    # Arrange
    new_customer = {
        "id": "1",
        "phone_number": "+5491234567890",
        "profile_name": "Jane Doe",
        "first_contact": datetime.now(timezone.utc).isoformat(),
        "last_contact": datetime.now(timezone.utc).isoformat(),
        "total_interactions": 1,
    }
    mock_customer_repository.get_or_create.return_value = new_customer

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name="Jane Doe"
    )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"
    assert result["profile_name"] == "Jane Doe"
    assert result["total_interactions"] == 1

    # Verify repository was called
    mock_customer_repository.get_or_create.assert_called_once()


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_race_condition_handled(mock_customer_repository, sample_customer):
    """Test handling race condition when creating customer - handled by repository."""
    # Arrange - repository handles race conditions internally
    mock_customer_repository.get_or_create.return_value = sample_customer

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name="John Doe"
    )

    # Assert - repository handles race condition, returns existing customer
    assert result is not None
    assert result["phone_number"] == "+5491234567890"


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_update_profile_name(mock_customer_repository):
    """Test updating profile name when customer exists without one."""
    # Arrange
    customer_with_updated_profile = {
        "id": "1",
        "phone_number": "+5491234567890",
        "profile_name": "New Name",  # Repository updated profile name
        "first_contact": datetime.now(timezone.utc).isoformat(),
        "last_contact": datetime.now(timezone.utc).isoformat(),
        "total_interactions": 4,
    }
    mock_customer_repository.get_or_create.return_value = customer_with_updated_profile

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name="New Name"
    )

    # Assert
    assert result is not None
    assert result["profile_name"] == "New Name"


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_keep_existing_profile_name(mock_customer_repository, sample_customer):
    """Test keeping existing profile name when customer already has one."""
    # Arrange - repository keeps existing profile name
    mock_customer_repository.get_or_create.return_value = sample_customer

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name="Different Name"  # Try to change
    )

    # Assert - profile name remains "John Doe" (original)
    assert result is not None
    assert result["profile_name"] == "John Doe"


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_database_error(mock_customer_repository):
    """Test handling general database error."""
    # Arrange - repository raises exception
    mock_customer_repository.get_or_create.side_effect = Exception("Database connection lost")

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name="John Doe"
    )

    # Assert - should return None on error
    assert result is None


@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_or_create_without_profile_name(mock_customer_repository):
    """Test creating customer without providing profile name."""
    # Arrange
    customer_without_profile = {
        "id": "1",
        "phone_number": "+5491234567890",
        "profile_name": None,
        "first_contact": datetime.now(timezone.utc).isoformat(),
        "last_contact": datetime.now(timezone.utc).isoformat(),
        "total_interactions": 1,
    }
    mock_customer_repository.get_or_create.return_value = customer_without_profile

    use_case = GetOrCreateCustomerUseCase(customer_repository=mock_customer_repository)

    # Act
    result = await use_case.execute(
        phone_number="+5491234567890",
        profile_name=None
    )

    # Assert
    assert result is not None
    assert result["phone_number"] == "+5491234567890"
    assert result.get("profile_name") is None
