"""
PostgreSQL Integration (Deprecated)

This module is deprecated. Use postgres_integration.py instead
or app.database.async_db for SQLAlchemy async sessions.
"""

# Re-export from postgres_integration for backwards compatibility
from app.integrations.databases.postgres_integration import (
    PostgresIntegration,
)

__all__ = [
    "PostgresIntegration",
]
