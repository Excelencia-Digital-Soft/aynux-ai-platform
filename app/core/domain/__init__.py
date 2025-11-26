"""
Domain Layer - Core DDD building blocks

This module provides base classes for Domain-Driven Design:
- Entities: Objects with identity and lifecycle
- Value Objects: Immutable objects compared by value
- Events: Domain events for communication
- Exceptions: Domain-specific error handling
"""

from app.core.domain.entities import (
    AggregateRoot,
    AuditableEntity,
    Entity,
    SoftDeletableEntity,
    generate_uuid,
    generate_uuid_str,
)
from app.core.domain.events import (
    DomainEvent,
    DomainEventPublisher,
    EventStore,
    IntegrationEvent,
    event_handler,
)
from app.core.domain.exceptions import (
    AppointmentConflictException,
    AuthorizationException,
    BusinessRuleViolationException,
    ConcurrencyException,
    CreditLimitExceededException,
    DomainException,
    DuplicateEntityException,
    EntityNotFoundException,
    InsufficientStockException,
    IntegrationException,
    InvalidOperationException,
    PaymentException,
    ValidationException,
)
from app.core.domain.value_objects import (
    Address,
    Email,
    Money,
    Percentage,
    PhoneNumber,
    Quantity,
    StatusEnum,
    ValueObject,
)

__all__ = [
    # Entities
    "Entity",
    "AggregateRoot",
    "AuditableEntity",
    "SoftDeletableEntity",
    "generate_uuid",
    "generate_uuid_str",
    # Value Objects
    "ValueObject",
    "Money",
    "Percentage",
    "Quantity",
    "Email",
    "PhoneNumber",
    "Address",
    "StatusEnum",
    # Events
    "DomainEvent",
    "IntegrationEvent",
    "DomainEventPublisher",
    "EventStore",
    "event_handler",
    # Exceptions
    "DomainException",
    "ValidationException",
    "EntityNotFoundException",
    "BusinessRuleViolationException",
    "InsufficientStockException",
    "InvalidOperationException",
    "ConcurrencyException",
    "AuthorizationException",
    "DuplicateEntityException",
    "PaymentException",
    "IntegrationException",
    "AppointmentConflictException",
    "CreditLimitExceededException",
]
