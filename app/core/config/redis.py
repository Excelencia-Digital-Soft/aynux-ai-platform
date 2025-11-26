"""
Redis Configuration

Provides Redis configuration and connection management.
"""

from dataclasses import dataclass

from app.config.settings import get_settings


@dataclass
class RedisConfig:
    """Redis configuration settings."""

    host: str
    port: int
    db: int
    password: str | None

    @property
    def url(self) -> str:
        """Build Redis URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"

    @property
    def connection_params(self) -> dict:
        """Get connection parameters for redis-py."""
        params = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "decode_responses": True,
        }
        if self.password:
            params["password"] = self.password
        return params


def get_redis_config() -> RedisConfig:
    """Get Redis configuration from settings."""
    settings = get_settings()
    return RedisConfig(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
    )


__all__ = [
    "RedisConfig",
    "get_redis_config",
]
