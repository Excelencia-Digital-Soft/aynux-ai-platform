"""
Shared Infrastructure Layer

Infrastructure implementations for the Shared domain.
"""

from app.domains.shared.infrastructure.repositories import (
    SQLAlchemyCustomerRepository,
)

__all__ = ["SQLAlchemyCustomerRepository"]
