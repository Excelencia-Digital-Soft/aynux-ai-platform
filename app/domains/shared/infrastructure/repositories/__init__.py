"""
Shared Infrastructure Repositories

Repository implementations for the Shared domain.
"""

from app.domains.shared.infrastructure.repositories.customer_repository import (
    SQLAlchemyCustomerRepository,
)

__all__ = ["SQLAlchemyCustomerRepository"]
