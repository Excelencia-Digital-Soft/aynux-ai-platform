"""
Base Domain Event Classes for Domain-Driven Design

Domain Events represent significant business occurrences that domain experts
care about. They are used to communicate between aggregates and bounded contexts.
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DomainEvent(ABC):
    """
    Base class for all domain events.

    Domain events are immutable records of something that happened
    in the domain. They capture the fact that something occurred.

    Example:
        ```python
        @dataclass(frozen=True)
        class OrderCreated(DomainEvent):
            order_id: int
            customer_id: int
            total_amount: Decimal
        ```
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = field(default=1)

    @property
    def event_type(self) -> str:
        """Get the event type name (class name)."""
        return self.__class__.__name__

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        result = {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "version": self.version,
        }
        # Add all other fields
        for key, value in self.__dict__.items():
            if key not in result:
                if isinstance(value, (datetime,)):
                    result[key] = value.isoformat()
                elif isinstance(value, UUID):
                    result[key] = str(value)
                else:
                    result[key] = value
        return result


@dataclass(frozen=True)
class IntegrationEvent(DomainEvent):
    """
    Integration event for cross-bounded-context communication.

    These events are published outside the bounded context
    and consumed by other services.
    """

    source_context: str = ""
    correlation_id: UUID = field(default_factory=uuid4)


# Type aliases for event handlers
EventHandler = Callable[[DomainEvent], Coroutine[Any, Any, None]]


class DomainEventPublisher:
    """
    Simple in-memory domain event publisher.

    For production use, consider using a message broker
    like RabbitMQ, Kafka, or Redis Streams.
    """

    _handlers: dict[str, list[EventHandler]] = {}

    @classmethod
    def subscribe(cls, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async handler function
        """
        event_name = event_type.__name__
        if event_name not in cls._handlers:
            cls._handlers[event_name] = []
        cls._handlers[event_name].append(handler)

    @classmethod
    async def publish(cls, event: DomainEvent) -> None:
        """
        Publish a domain event to all subscribers.

        Args:
            event: Event to publish
        """
        event_name = event.event_type
        handlers = cls._handlers.get(event_name, [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                # Log error but don't fail other handlers
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Error in event handler for {event_name}: {e}")

    @classmethod
    async def publish_all(cls, events: list[DomainEvent]) -> None:
        """
        Publish multiple events.

        Args:
            events: List of events to publish
        """
        for event in events:
            await cls.publish(event)

    @classmethod
    def clear_handlers(cls) -> None:
        """Clear all event handlers (useful for testing)."""
        cls._handlers.clear()


class EventStore:
    """
    Simple in-memory event store for event sourcing.

    For production, use a persistent store like EventStoreDB
    or a database-backed implementation.
    """

    _events: list[DomainEvent] = []

    @classmethod
    def append(cls, event: DomainEvent) -> None:
        """Append an event to the store."""
        cls._events.append(event)

    @classmethod
    def append_all(cls, events: list[DomainEvent]) -> None:
        """Append multiple events."""
        cls._events.extend(events)

    @classmethod
    def get_events_for_aggregate(cls, aggregate_id: Any, aggregate_type: str | None = None) -> list[DomainEvent]:
        """Get all events for an aggregate."""
        result = []
        for event in cls._events:
            event_dict = event.to_dict()
            # Check common ID fields
            if (
                event_dict.get("aggregate_id") == aggregate_id
                or event_dict.get("order_id") == aggregate_id
                or event_dict.get("product_id") == aggregate_id
            ):
                if aggregate_type is None or event_dict.get("aggregate_type") == aggregate_type:
                    result.append(event)
        return result

    @classmethod
    def get_all_events(cls) -> list[DomainEvent]:
        """Get all stored events."""
        return list(cls._events)

    @classmethod
    def clear(cls) -> None:
        """Clear all events (useful for testing)."""
        cls._events.clear()


# Decorator for event handlers
def event_handler(event_type: type[DomainEvent]):
    """
    Decorator to register a function as an event handler.

    Example:
        ```python
        @event_handler(OrderCreated)
        async def handle_order_created(event: OrderCreated):
            # Send confirmation email
            await send_email(event.customer_id)
        ```
    """

    def decorator(func: EventHandler) -> EventHandler:
        DomainEventPublisher.subscribe(event_type, func)
        return func

    return decorator
