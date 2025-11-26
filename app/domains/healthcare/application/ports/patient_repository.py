"""
Patient Repository Port

Interface for patient data access following Clean Architecture.
"""

from datetime import date
from typing import Protocol, runtime_checkable

from app.domains.healthcare.domain.entities.patient import Patient
from app.domains.healthcare.domain.value_objects.appointment_status import PatientStatus


@runtime_checkable
class IPatientRepository(Protocol):
    """
    Patient repository interface.

    Defines the contract for patient data access operations.
    Implementations can be SQLAlchemy, MongoDB, or any other data store.

    Example:
        ```python
        class SQLAlchemyPatientRepository(IPatientRepository):
            async def find_by_id(self, patient_id: int) -> Patient | None:
                # SQLAlchemy implementation
                pass
        ```
    """

    async def find_by_id(self, patient_id: int) -> Patient | None:
        """
        Find patient by ID.

        Args:
            patient_id: Unique patient identifier

        Returns:
            Patient if found, None otherwise
        """
        ...

    async def find_by_national_id(self, national_id: str) -> Patient | None:
        """
        Find patient by national ID (DNI).

        Args:
            national_id: National identification number

        Returns:
            Patient if found, None otherwise
        """
        ...

    async def find_by_medical_record_number(self, mrn: str) -> Patient | None:
        """
        Find patient by medical record number.

        Args:
            mrn: Medical record number (Historia Clinica)

        Returns:
            Patient if found, None otherwise
        """
        ...

    async def find_by_phone(self, phone: str) -> Patient | None:
        """
        Find patient by phone number.

        Args:
            phone: Phone number (normalized)

        Returns:
            Patient if found, None otherwise
        """
        ...

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Patient]:
        """
        Search patients by name or other fields.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            List of matching patients
        """
        ...

    async def filter_by_status(
        self,
        status: PatientStatus,
        limit: int = 100,
    ) -> list[Patient]:
        """
        Filter patients by status.

        Args:
            status: Patient status to filter by
            limit: Maximum results

        Returns:
            List of patients with given status
        """
        ...

    async def find_by_date_of_birth(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Patient]:
        """
        Find patients born within date range.

        Args:
            start_date: Start of date range
            end_date: End of date range

        Returns:
            List of patients
        """
        ...

    async def save(self, patient: Patient) -> Patient:
        """
        Save or update patient.

        Args:
            patient: Patient to save

        Returns:
            Saved patient with ID
        """
        ...

    async def delete(self, patient_id: int) -> bool:
        """
        Delete patient by ID.

        Args:
            patient_id: Patient ID to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    async def exists(self, patient_id: int) -> bool:
        """
        Check if patient exists.

        Args:
            patient_id: Patient ID

        Returns:
            True if exists
        """
        ...

    async def count(self) -> int:
        """
        Get total patient count.

        Returns:
            Total number of patients
        """
        ...

    async def count_by_status(self, status: PatientStatus) -> int:
        """
        Count patients by status.

        Args:
            status: Patient status

        Returns:
            Count of patients with status
        """
        ...
