"""
Domain Exceptions for Domain-Driven Design

These exceptions represent business rule violations and domain-specific errors.
They should be caught and translated to appropriate HTTP responses in the API layer.
"""

from typing import Any


class DomainException(Exception):
    """
    Base exception for all domain-related errors.

    Provides a standardized way to communicate business rule violations.
    """

    def __init__(self, message: str, code: str | None = None, details: dict[str, Any] | None = None):
        """
        Initialize domain exception.

        Args:
            message: Human-readable error message
            code: Machine-readable error code (e.g., "INSUFFICIENT_STOCK")
            details: Additional context about the error
        """
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__.upper()
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationException(DomainException):
    """
    Raised when domain validation fails.

    Use for invalid entity states, value object creation failures, etc.
    """

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, "VALIDATION_ERROR", details)
        self.field = field


class EntityNotFoundException(DomainException):
    """
    Raised when an entity is not found.
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: Any,
        message: str | None = None,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        msg = message or f"{entity_type} with ID {entity_id} not found"
        super().__init__(
            msg,
            "ENTITY_NOT_FOUND",
            {"entity_type": entity_type, "entity_id": str(entity_id)},
        )


class BusinessRuleViolationException(DomainException):
    """
    Raised when a business rule is violated.

    Use for invariant violations, precondition failures, etc.
    """

    def __init__(self, rule: str, message: str | None = None, details: dict[str, Any] | None = None):
        self.rule = rule
        msg = message or f"Business rule violated: {rule}"
        details = details or {}
        details["rule"] = rule
        super().__init__(msg, "BUSINESS_RULE_VIOLATION", details)


class InsufficientStockException(DomainException):
    """Raised when there's not enough stock for an operation."""

    def __init__(self, product_id: int, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for product {product_id}. Requested: {requested}, Available: {available}",
            "INSUFFICIENT_STOCK",
            {
                "product_id": product_id,
                "requested": requested,
                "available": available,
            },
        )


class InvalidOperationException(DomainException):
    """Raised when an operation is not valid in the current state."""

    def __init__(self, operation: str, current_state: str, message: str | None = None):
        self.operation = operation
        self.current_state = current_state
        msg = message or f"Cannot perform '{operation}' in state '{current_state}'"
        super().__init__(
            msg,
            "INVALID_OPERATION",
            {"operation": operation, "current_state": current_state},
        )


class ConcurrencyException(DomainException):
    """Raised when there's a concurrency conflict (optimistic locking)."""

    def __init__(self, entity_type: str, entity_id: Any, expected_version: int, actual_version: int):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Concurrency conflict for {entity_type} {entity_id}. Expected version {expected_version}, but found {actual_version}",
            "CONCURRENCY_CONFLICT",
            {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "expected_version": expected_version,
                "actual_version": actual_version,
            },
        )


class AuthorizationException(DomainException):
    """Raised when a user is not authorized to perform an operation."""

    def __init__(self, operation: str, resource: str | None = None, user_id: str | None = None):
        self.operation = operation
        self.resource = resource
        self.user_id = user_id
        msg = f"Not authorized to perform '{operation}'"
        if resource:
            msg += f" on '{resource}'"
        super().__init__(
            msg,
            "AUTHORIZATION_ERROR",
            {
                "operation": operation,
                "resource": resource,
            },
        )


class DuplicateEntityException(DomainException):
    """Raised when attempting to create a duplicate entity."""

    def __init__(self, entity_type: str, field: str, value: Any):
        self.entity_type = entity_type
        self.field = field
        self.value = value
        super().__init__(
            f"{entity_type} with {field}='{value}' already exists",
            "DUPLICATE_ENTITY",
            {
                "entity_type": entity_type,
                "field": field,
                "value": str(value),
            },
        )


class PaymentException(DomainException):
    """Raised when a payment operation fails."""

    def __init__(self, message: str, payment_id: str | None = None, reason: str | None = None):
        self.payment_id = payment_id
        self.reason = reason
        details: dict[str, Any] = {}
        if payment_id:
            details["payment_id"] = payment_id
        if reason:
            details["reason"] = reason
        super().__init__(message, "PAYMENT_ERROR", details)


class IntegrationException(DomainException):
    """Raised when an external integration fails."""

    def __init__(self, service: str, message: str, original_error: Exception | None = None):
        self.service = service
        self.original_error = original_error
        details: dict[str, Any] = {"service": service}
        if original_error:
            details["original_error"] = str(original_error)
        super().__init__(message, "INTEGRATION_ERROR", details)


class AppointmentConflictException(DomainException):
    """Raised when there's a scheduling conflict."""

    def __init__(
        self,
        doctor_id: int | None = None,
        time_slot: str | None = None,
        message: str | None = None,
    ):
        self.doctor_id = doctor_id
        self.time_slot = time_slot
        msg = message or "Appointment conflict: time slot not available"
        details: dict[str, Any] = {}
        if doctor_id:
            details["doctor_id"] = doctor_id
        if time_slot:
            details["time_slot"] = time_slot
        super().__init__(msg, "APPOINTMENT_CONFLICT", details)


class CreditLimitExceededException(DomainException):
    """Raised when a credit operation exceeds the limit."""

    def __init__(self, account_id: int, requested: float, available: float):
        self.account_id = account_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Credit limit exceeded for account {account_id}. Requested: ${requested:.2f}, Available: ${available:.2f}",
            "CREDIT_LIMIT_EXCEEDED",
            {
                "account_id": account_id,
                "requested": requested,
                "available": available,
            },
        )
