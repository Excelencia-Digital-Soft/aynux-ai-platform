"""
Doctor Repository Interface

Protocol definition for doctor data access.
"""

from typing import Protocol, runtime_checkable

from app.domains.healthcare.domain.entities.doctor import Doctor
from app.domains.healthcare.domain.value_objects.appointment_status import DoctorSpecialty


@runtime_checkable
class IDoctorRepository(Protocol):
    """
    Interface for doctor repository.

    Defines the contract for doctor data access.
    """

    async def find_by_id(self, doctor_id: int) -> Doctor | None:
        """Find doctor by ID."""
        ...

    async def find_by_license(self, license_number: str) -> Doctor | None:
        """Find doctor by license number."""
        ...

    async def find_by_specialty(
        self,
        specialty: DoctorSpecialty,
        limit: int = 20,
    ) -> list[Doctor]:
        """Find doctors by specialty."""
        ...

    async def search(self, query: str, limit: int = 10) -> list[Doctor]:
        """Search doctors by name or specialty."""
        ...

    async def get_active(self, accepting_patients: bool = True) -> list[Doctor]:
        """Get active doctors, optionally filtering by accepting patients."""
        ...

    async def save(self, doctor: Doctor) -> Doctor:
        """Save a doctor (create or update)."""
        ...

    async def delete(self, doctor_id: int) -> bool:
        """Delete a doctor."""
        ...


__all__ = ["IDoctorRepository"]
