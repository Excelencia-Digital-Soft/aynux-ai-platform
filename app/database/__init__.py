import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config.settings import get_settings
from app.models.database import Brand, Category, Conversation, Customer, Product

logger = logging.getLogger(__name__)

# Configuración
settings = get_settings()


# URL de conexión con mejor manejo de errores
def get_database_url() -> str:
    """Construye la URL de la base de datos con validación (password opcional)"""
    print(f"--> Settings DB_HOST: {settings.DB_HOST}")
    print(f"--> Settings DB_USER: {settings.DB_USER}")
    print(f"--> Settings DB_PASSWORD: {'***' if settings.DB_PASSWORD else 'None'}")
    print(f"--> Settings DB_NAME: {settings.DB_NAME}")

    # Validar solo los campos obligatorios (password es opcional)
    required_vars = [settings.DB_HOST, settings.DB_USER, settings.DB_NAME]
    if not all(var for var in required_vars):
        raise ValueError("Missing required database configuration (host, user, database)")

    # Construir URL con o sin password
    if settings.DB_PASSWORD:
        # Con password
        url = (
            f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}"
            f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        )
    else:
        # Sin password
        url = f"postgresql://{settings.DB_USER}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

    print(f"--> Database URL: {url.replace(settings.DB_PASSWORD or '', '***')}")
    return url


# Engine con configuración optimizada para PostgreSQL
try:
    DATABASE_URL = get_database_url()
    engine = create_engine(
        DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=settings.DB_POOL_RECYCLE,
        echo=settings.DB_ECHO,
        future=True,
        # Para desarrollo, usar NullPool para evitar problemas de conexión
        poolclass=NullPool if settings.DEBUG else None,
    )

    # Test de conexión
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if settings.DEBUG:
            logger.info("Database connection established")

except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obtener la sesión de base de datos
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager para operaciones de base de datos
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


async def init_db():
    """
    Inicializa la base de datos creando todas las tablas
    """
    try:
        # Test de conexión primero
        with get_db_context() as db:
            db.execute("SELECT 1")
            logger.info("Database connection test successful")

        # Crear tablas
        from app.models.database import Base

        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def check_db_connection() -> bool:
    """Verifica la conexión a la base de datos"""
    try:
        with get_db_context() as db:
            result = db.execute("SELECT 1").scalar()
            logger.info("Database connection check: OK = ", result)
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


class DatabaseManager:
    """
    Manager para operaciones avanzadas de base de datos
    """

    def __init__(self):
        self.engine = engine
        self.session_maker = SessionLocal

    async def create_tables(self):
        """Crea todas las tablas"""
        Base.metadata.create_all(bind=self.engine)

    async def drop_tables(self):
        """Elimina todas las tablas (¡CUIDADO!)"""
        Base.metadata.drop_all(bind=self.engine)

    async def backup_data(self, table_name: Optional[str] = None):
        """Crea backup de datos (implementar según necesidades)"""
        print(f"Creando backup de {table_name}")
        # TODO: Implementar backup logic
        pass

    async def get_table_stats(self):
        """Obtiene estadísticas de las tablas"""
        with get_db_context() as db:
            stats = {}

            models = [Product, Customer, Conversation, Brand, Category]

            for model in models:
                try:
                    count = db.query(model).count()
                    stats[model.__tablename__] = count
                except Exception as e:
                    logger.error(f"Error getting stats for {model.__tablename__}: {e}")
                    stats[model.__tablename__] = 0

            return stats


# Configuración de logging para SQLAlchemy
if settings.DEBUG:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.DEBUG)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
