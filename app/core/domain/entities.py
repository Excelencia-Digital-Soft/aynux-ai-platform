"""
Base Entity Classes for Domain-Driven Design

Entities are domain objects with identity and lifecycle.
They maintain their identity regardless of their attributes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar
from uuid import UUID, uuid4

# Type variable for entity ID (int, str, UUID, etc.)
TId = TypeVar("TId")


@dataclass
class Entity(ABC, Generic[TId]):
    """
    Base class for all domain entities.

    An entity is a domain object that has a distinct identity
    that runs through time and different states.

    Type Parameters:
        TId: Type of entity identifier (int, str, UUID)

    Example:
        ```python
        @dataclass
        class Product(Entity[int]):
            name: str
            price: Price  # Value object

            def apply_discount(self, percentage: float) -> None:
                self.price = self.price.apply_discount(percentage)
        ```
    """

    id: TId | None = field(default=None)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __eq__(self, other: object) -> bool:
        """Entities are equal if they have the same ID."""
        if not isinstance(other, Entity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dicts."""
        return hash(self.id) if self.id is not None else id(self)

    def is_new(self) -> bool:
        """Check if entity is new (not yet persisted)."""
        return self.id is None

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)


@dataclass
class AggregateRoot(Entity[TId], Generic[TId]):
    """
    Base class for aggregate roots.

    An aggregate root is the entry point to an aggregate.
    It controls access to all members of the aggregate
    and ensures invariants are maintained.

    Example:
        ```python
        @dataclass
        class Order(AggregateRoot[int]):
            customer_id: int
            items: list[OrderItem] = field(default_factory=list)
            status: OrderStatus = OrderStatus.PENDING

            def add_item(self, item: OrderItem) -> None:
                self._validate_can_add_item()
                self.items.append(item)
                self._record_event(OrderItemAdded(order_id=self.id, item=item))
        ```
    """

    _domain_events: list[Any] = field(default_factory=list, repr=False, compare=False)
    version: int = field(default=0)

    def _record_event(self, event: Any) -> None:
        """Record a domain event to be published later."""
        self._domain_events.append(event)

    def get_domain_events(self) -> list[Any]:
        """Get all recorded domain events."""
        return list(self._domain_events)

    def clear_domain_events(self) -> None:
        """Clear all recorded domain events (after publishing)."""
        self._domain_events.clear()

    def increment_version(self) -> None:
        """Increment version for optimistic concurrency."""
        self.version += 1


@dataclass
class AuditableEntity(Entity[TId], Generic[TId]):
    """
    Entity with audit trail support.

    Tracks creation and modification metadata.
    """

    created_by: str | None = field(default=None)
    updated_by: str | None = field(default=None)

    def set_created_by(self, user_id: str) -> None:
        """Set the creator of this entity."""
        self.created_by = user_id

    def set_updated_by(self, user_id: str) -> None:
        """Set the last modifier and update timestamp."""
        self.updated_by = user_id
        self.touch()


@dataclass
class SoftDeletableEntity(Entity[TId], Generic[TId]):
    """
    Entity with soft delete support.

    Instead of physical deletion, marks entity as deleted.
    """

    deleted_at: datetime | None = field(default=None)
    is_active: bool = field(default=True)

    def soft_delete(self) -> None:
        """Mark entity as deleted."""
        self.deleted_at = datetime.now(UTC)
        self.is_active = False

    def restore(self) -> None:
        """Restore a soft-deleted entity."""
        self.deleted_at = None
        self.is_active = True

    def is_deleted(self) -> bool:
        """Check if entity is soft-deleted."""
        return not self.is_active or self.deleted_at is not None


# Helper functions for ID generation
def generate_uuid() -> UUID:
    """Generate a new UUID for entity identification."""
    return uuid4()


def generate_uuid_str() -> str:
    """Generate a new UUID as string."""
    return str(uuid4())
