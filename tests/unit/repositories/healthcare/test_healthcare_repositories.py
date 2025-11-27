"""
Unit tests for Healthcare Domain Repositories.

Tests the data access layer for doctors, patients, and appointments.
"""

from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.healthcare.domain.entities.doctor import Doctor, WeeklySchedule
from app.domains.healthcare.domain.value_objects.appointment_status import DoctorSpecialty, TimeSlot
from app.domains.healthcare.infrastructure.repositories.doctor_repository import (
    SQLAlchemyDoctorRepository,
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
def sample_doctor_model():
    """Sample SQLAlchemy doctor model."""
    model = MagicMock()
    model.id = 1
    model.first_name = "John"
    model.last_name = "Smith"
    model.email = "john.smith@hospital.com"
    model.phone = "+1234567890"
    model.license_number = "LIC-12345"
    model.specialty = DoctorSpecialty.GENERAL_PRACTICE
    model.secondary_specialties = []
    model.working_days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    model.working_hours_start = time(8, 0)
    model.working_hours_end = time(17, 0)
    model.appointment_duration_minutes = 30
    model.is_active = True
    model.created_at = datetime.now(UTC)
    model.updated_at = datetime.now(UTC)
    return model


# ============================================================================
# Doctor Repository Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_get_by_id_success(mock_async_session, sample_doctor_model):
    """Test successfully getting a doctor by ID."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_doctor_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    doctor = await repository.find_by_id(1)

    # Assert
    assert doctor is not None
    assert doctor.first_name == "John"
    assert doctor.last_name == "Smith"
    assert doctor.license_number == "LIC-12345"
    mock_async_session.execute.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_get_by_id_not_found(mock_async_session):
    """Test getting a doctor that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    doctor = await repository.find_by_id(999)

    # Assert
    assert doctor is None


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_get_by_license(mock_async_session, sample_doctor_model):
    """Test getting a doctor by license number."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_doctor_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    doctor = await repository.find_by_license("LIC-12345")

    # Assert
    assert doctor is not None
    assert doctor.license_number == "LIC-12345"


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_get_by_specialty(mock_async_session, sample_doctor_model):
    """Test getting doctors by specialty."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_doctor_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    doctors = await repository.find_by_specialty(DoctorSpecialty.GENERAL_PRACTICE)

    # Assert
    assert len(doctors) == 1
    assert doctors[0].specialty == DoctorSpecialty.GENERAL_PRACTICE


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_search(mock_async_session, sample_doctor_model):
    """Test searching doctors by name."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_doctor_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    doctors = await repository.search("Smith")

    # Assert
    assert len(doctors) == 1
    assert "Smith" in doctors[0].last_name


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_get_active(mock_async_session, sample_doctor_model):
    """Test getting active doctors."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_doctor_model]
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    doctors = await repository.get_active()

    # Assert
    assert len(doctors) == 1
    assert doctors[0].is_active is True


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_save_new(mock_async_session, sample_doctor_model):
    """Test saving a new doctor."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Create weekly schedule
    weekly_schedule = WeeklySchedule()
    slot = TimeSlot(
        start_time=time(8, 0),
        end_time=time(17, 0),
        duration_minutes=30
    )
    for day in range(5):  # Monday to Friday
        weekly_schedule.add_slot(day, slot)

    doctor = Doctor(
        first_name="Jane",
        last_name="Doe",
        license_number="LIC-99999",
        specialty=DoctorSpecialty.CARDIOLOGY,
        weekly_schedule=weekly_schedule,
    )

    # Setup mock to return proper model after refresh
    async def mock_refresh(obj):
        obj.id = 2

    mock_async_session.refresh = mock_refresh

    # Act
    saved = await repository.save(doctor)

    # Assert
    mock_async_session.add.assert_called_once()
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_delete_success(mock_async_session, sample_doctor_model):
    """Test deleting a doctor."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_doctor_model
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    success = await repository.delete(1)

    # Assert
    assert success is True
    mock_async_session.delete.assert_called_once_with(sample_doctor_model)
    mock_async_session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_delete_not_found(mock_async_session):
    """Test deleting a doctor that doesn't exist."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    success = await repository.delete(999)

    # Assert
    assert success is False
    mock_async_session.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_count(mock_async_session):
    """Test counting doctors."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 10
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    count = await repository.count()

    # Assert
    assert count == 10


@pytest.mark.unit
@pytest.mark.repository
@pytest.mark.asyncio
async def test_doctor_exists(mock_async_session):
    """Test checking if doctor exists."""
    # Arrange
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    mock_async_session.execute.return_value = mock_result

    repository = SQLAlchemyDoctorRepository(mock_async_session)

    # Act
    exists = await repository.exists(1)

    # Assert
    assert exists is True
