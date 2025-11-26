"""
Database Configuration

Provides database configuration and connection management.
"""

from dataclasses import dataclass
from typing import Any

from app.config.settings import get_settings


@dataclass
class DatabaseConfig:
    """Database configuration settings."""

    host: str
    port: int
    name: str
    user: str
    password: str | None
    pool_size: int
    max_overflow: int
    pool_recycle: int
    pool_timeout: int
    echo: bool

    @property
    def url(self) -> str:
        """Build database URL."""
        if self.password:
            return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        return f"postgresql://{self.user}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Build async database URL for asyncpg."""
        if self.password:
            return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        return f"postgresql+asyncpg://{self.user}@{self.host}:{self.port}/{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for SQLAlchemy engine creation."""
        return {
            "echo": self.echo,
            "future": True,
            "pool_pre_ping": True,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle": self.pool_recycle,
            "pool_timeout": self.pool_timeout,
        }


def get_database_config() -> DatabaseConfig:
    """Get database configuration from settings."""
    settings = get_settings()
    return DatabaseConfig(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        name=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        echo=settings.DB_ECHO,
    )


__all__ = [
    "DatabaseConfig",
    "get_database_config",
]
