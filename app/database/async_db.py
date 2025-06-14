import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # type: ignore[attr-defined]
from sqlalchemy.pool import NullPool, QueuePool

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# Configuración
settings = get_settings()


def get_async_database_url() -> str:
    """Construye la URL de la base de datos asíncrona"""
    # Valores requeridos
    host = settings.DB_HOST or "localhost"
    port = settings.DB_PORT or 5432
    user = settings.DB_USER or "postgres"
    database = settings.DB_NAME
    password = settings.DB_PASSWORD

    # Validar database name (obligatorio)
    if not database:
        raise ValueError("Database name is required (DB_NAME)")

    # Escapar caracteres especiales en credenciales
    encoded_user = quote_plus(user)

    # Construir URL según si hay password o no
    if password:
        encoded_password = quote_plus(password)
        url = f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
    else:
        url = f"postgresql+asyncpg://{encoded_user}@{host}:{port}/{database}"
    return url


def create_async_database_engine():
    """Crea el engine de base de datos asíncrono"""
    try:
        database_url = get_async_database_url()

        # Configuración base común
        base_config = {
            "echo": settings.DB_ECHO,
            "future": True,
            "pool_pre_ping": True,
        }

        # Configuración específica según el entorno
        if settings.DEBUG:
            # Para desarrollo: usar NullPool (sin pooling)
            logger.info("Creating async database engine for DEVELOPMENT (NullPool)")
            engine_config = {
                **base_config,
                "poolclass": NullPool,
            }
        else:
            # Para producción: usar pool completo
            logger.info("Creating async database engine for PRODUCTION (QueuePool)")
            engine_config = {
                **base_config,
                "poolclass": QueuePool,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_timeout": 30,
            }

        engine = create_async_engine(database_url, **engine_config)
        return engine

    except Exception as e:
        logger.error(f"Failed to create async database engine: {e}")
        raise


# Crear el engine asíncrono
async_engine = create_async_database_engine()

# Session maker asíncrono
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obtener la sesión de base de datos asíncrona
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Async database error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_db_context():
    """
    Context manager para operaciones de base de datos asíncronas
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Async database error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

