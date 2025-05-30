import logging
from contextlib import contextmanager
from typing import Generator, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from app.config.settings import get_settings
from app.models.database import Brand, Category, Conversation, Customer, Product

logger = logging.getLogger(__name__)

# Configuración
settings = get_settings()


# URL de conexión con mejor manejo de errores
def get_database_url() -> str:
    """Construye la URL de la base de datos con validación (password opcional)"""
    # Valores requeridos
    host = settings.DB_HOST or "localhost"
    port = settings.DB_PORT or 5432
    user = settings.DB_USER or "postgres"
    database = settings.DB_NAME
    password = settings.DB_PASSWORD

    print("--> DB Connection Config:")
    print(f"    Host: {host}")
    print(f"    Port: {port}")
    print(f"    User: {user}")
    print(f"    Database: {database}")
    print(f"    Password: {'Set' if password else 'None'}")

    # Validar database name (obligatorio)
    if not database:
        raise ValueError("Database name is required (DB_NAME)")

    # Escapar caracteres especiales en credenciales
    encoded_user = quote_plus(user)

    # Construir URL según si hay password o no
    if password:
        encoded_password = quote_plus(password)
        url = f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
    else:
        url = f"postgresql://{encoded_user}@{host}:{port}/{database}"
    return url


def create_database_engine():
    """Crea el engine de base de datos con configuración optimizada"""
    try:
        database_url = get_database_url()

        # Configuración base común
        base_config = {
            "echo": settings.DB_ECHO,
            "future": True,
            "pool_pre_ping": True,
        }

        # Configuración específica según el entorno
        if settings.DEBUG:
            # Para desarrollo: usar NullPool (sin pooling)
            logger.info("Creating database engine for DEVELOPMENT (NullPool)")
            engine_config = {
                **base_config,
                "poolclass": NullPool,
                # NullPool no acepta parámetros de pool
            }
        else:
            # Para producción: usar pool completo
            logger.info("Creating database engine for PRODUCTION (QueuePool)")
            engine_config = {
                **base_config,
                "poolclass": QueuePool,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_recycle": settings.DB_POOL_RECYCLE,
                "pool_timeout": 30,  # Timeout para obtener conexión del pool
            }

        engine = create_engine(database_url, **engine_config)

        # Test de conexión inicial
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database engine created and tested successfully")

        return engine

    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise


# Crear el engine
try:
    engine = create_database_engine()
except Exception as e:
    logger.error(f"Database initialization failed: {e}")
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
            db.execute(text("SELECT 1"))
            logger.debug("Database connection test successful")

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
            result = db.execute(text("SELECT 1")).scalar()
            logger.info(f"Database connection check: OK = {result}")
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
        logger.info("All database tables created")

    async def drop_tables(self):
        """Elimina todas las tablas (¡CUIDADO!)"""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("All database tables dropped")

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
                    logger.debug(f"Table {model.__tablename__}: {count} records")
                except Exception as e:
                    logger.error(f"Error getting stats for {model.__tablename__}: {e}")
                    stats[model.__tablename__] = 0

            return stats


# Event listeners para logging y debugging
@event.listens_for(Engine, "connect")
def set_postgres_pragma(dbapi_connection, connection_record):
    """Configuraciones específicas de PostgreSQL al conectar"""
    if settings.DEBUG:
        logger.debug("New PostgreSQL connection established")


@event.listens_for(Engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log cuando se obtiene una conexión del pool"""
    if settings.DEBUG:
        logger.debug("Connection checked out from pool")


@event.listens_for(Engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Log cuando se devuelve una conexión al pool"""
    if settings.DEBUG:
        logger.debug("Connection checked in to pool")


# Configuración de logging para SQLAlchemy
if settings.DEBUG:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.DEBUG)
else:
    # En producción, solo errores
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
