"""Protocol interfaces for PersonResolution dependency injection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from app.models.db.tenancy.registered_person import RegisteredPerson


@runtime_checkable
class IPersonIdentificationService(Protocol):
    """Port for person identification operations."""

    async def search_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Search PLEX for customer by phone."""
        ...

    async def search_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        """Search PLEX for customer by DNI/client number."""
        ...

    def normalize_identifier(self, value: str) -> str | None:
        """Normalize and validate identifier format."""
        ...

    def find_self_registration(
        self,
        registrations: list[RegisteredPerson],
        plex_customer: dict[str, Any] | None,
    ) -> RegisteredPerson | None:
        """Find self-registration from list."""
        ...

    def only_self_registered(
        self,
        registrations: list[RegisteredPerson],
        self_registration: RegisteredPerson | None,
    ) -> bool:
        """Check if only self is registered."""
        ...

    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        ...

    def normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        ...


@runtime_checkable
class IStateManagementService(Protocol):
    """Port for state extraction and management."""

    def extract_phone(self, state_dict: dict[str, Any]) -> str | None:
        """Extract phone number from state."""
        ...

    def get_organization_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract organization_id from state."""
        ...

    def get_pharmacy_id(self, state_dict: dict[str, Any]) -> UUID | None:
        """Extract pharmacy_id from state."""
        ...

    async def ensure_pharmacy_config(
        self, state_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Ensure pharmacy config is loaded into state."""
        ...


@runtime_checkable
class IPaymentStateService(Protocol):
    """Port for payment state management."""

    async def check_zombie_payment(
        self, state_dict: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check for stale payment state on session resume."""
        ...


@runtime_checkable
class IFlowHandler(Protocol):
    """Base protocol for flow step handlers."""

    async def handle(
        self, message: str, state_dict: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle a flow step and return state updates."""
        ...


@runtime_checkable
class IEscalationHandler(Protocol):
    """Port for escalation handling."""

    async def escalate_identification_failure(
        self, state_dict: dict[str, Any], retries: int
    ) -> dict[str, Any]:
        """Escalate when identification fails after max retries."""
        ...

    async def escalate_name_verification_failure(
        self, state_dict: dict[str, Any], mismatch_count: int
    ) -> dict[str, Any]:
        """Escalate when name verification fails after max retries."""
        ...


__all__ = [
    "IPersonIdentificationService",
    "IStateManagementService",
    "IPaymentStateService",
    "IFlowHandler",
    "IEscalationHandler",
]
