import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.models.database import Brand, Category, Conversation, Customer, Product

logger = logging.getLogger(__name__)

# Configuración
settings = get_settings()

# URL de conexión a PostgreSQL
DATABASE_URL = (
    f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# Engine con configuración optimizada para PostgreSQL
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DB_ECHO,  # Log SQL queries in debug mode
    future=True,
)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

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
        from app.models.database import Base

        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def check_db_connection():
    """
    Verifica la conexión a la base de datos
    """
    try:
        with get_db_context() as db:
            result = db.execute("SELECT 1")  # type: ignore
            logger.info("Database connection successful", result)
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
