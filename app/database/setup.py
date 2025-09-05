"""
Database Setup - Scripts de inicialización y configuración de la base de datos.

Este módulo contiene todas las funciones necesarias para configurar, inicializar
y poblar la base de datos con datos de ejemplo.
"""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.models.db.base import Base

logger = logging.getLogger(__name__)


def create_search_trigger() -> str:
    """Crea el trigger para actualización automática del search_vector."""
    return """
    CREATE OR REPLACE FUNCTION update_search_vector() RETURNS TRIGGER AS $$
    BEGIN
        NEW.search_vector := setweight(to_tsvector('spanish', coalesce(NEW.name, '')), 'A') ||
                           setweight(to_tsvector('spanish', coalesce(NEW.description, '')), 'B') ||
                           setweight(to_tsvector('spanish', coalesce(NEW.short_description, '')), 'C');
        RETURN NEW;
    END
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS tsvector_update_trigger ON products;
    CREATE TRIGGER tsvector_update_trigger
        BEFORE INSERT OR UPDATE ON products
        FOR EACH ROW EXECUTE FUNCTION update_search_vector();
    """


def create_indexes() -> str:
    """Crea índices adicionales para mejorar el rendimiento."""
    return """
    CREATE INDEX IF NOT EXISTS idx_products_search_gin ON products USING gin(search_vector);
    CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin(name gin_trgm_ops);
    CREATE INDEX IF NOT EXISTS idx_products_description_trgm ON products USING gin(description gin_trgm_ops);
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """


class DatabaseSetup:
    """Clase para manejar la configuración de la base de datos."""

    def __init__(self):
        self.settings = get_settings()
        self.engine = create_async_engine(self.settings.database_config)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def create_tables(self) -> None:
        """Crea todas las tablas en la base de datos."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Creando tablas...")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Tablas creadas exitosamente")
        except Exception as e:
            logger.error(f"Error creando tablas: {e}")
            raise

    async def drop_tables(self) -> None:
        """Elimina todas las tablas de la base de datos."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Eliminando tablas...")
                await conn.run_sync(Base.metadata.drop_all)
                logger.info("Tablas eliminadas exitosamente")
        except Exception as e:
            logger.error(f"Error eliminando tablas: {e}")
            raise

    async def setup_extensions(self) -> None:
        """Configura extensiones de PostgreSQL necesarias."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Configurando extensiones de PostgreSQL...")

                extensions = [
                    "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
                    "CREATE EXTENSION IF NOT EXISTS btree_gin;",
                    "CREATE EXTENSION IF NOT EXISTS uuid-ossp;",
                ]

                for extension in extensions:
                    await conn.execute(text(extension))

                logger.info("Extensiones configuradas exitosamente")
        except Exception as e:
            logger.error(f"Error configurando extensiones: {e}")
            raise

    async def setup_search_features(self) -> None:
        """Configura funciones de búsqueda full-text."""
        try:
            async with self.engine.begin() as conn:
                logger.info("Configurando funciones de búsqueda...")

                # Crear trigger de búsqueda
                await conn.execute(text(create_search_trigger()))

                # Crear índices adicionales
                await conn.execute(text(create_indexes()))

                logger.info("Funciones de búsqueda configuradas exitosamente")
        except Exception as e:
            logger.error(f"Error configurando búsqueda: {e}")
            raise


# Funciones principales para uso externo


async def initialize_database():
    """Inicializa completamente la base de datos."""
    setup = DatabaseSetup()

    try:
        logger.info("Iniciando configuración de base de datos...")

        # Configurar extensiones
        await setup.setup_extensions()

        # Crear tablas
        await setup.create_tables()

        # Configurar búsqueda
        await setup.setup_search_features()

        logger.info("Base de datos inicializada exitosamente")

    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        raise


async def reset_database():
    """Resetea completamente la base de datos."""
    setup = DatabaseSetup()

    try:
        logger.info("Reseteando base de datos...")

        # Eliminar tablas existentes
        await setup.drop_tables()

        # Inicializar desde cero
        await initialize_database()

        logger.info("Base de datos reseteada exitosamente")

    except Exception as e:
        logger.error(f"Error reseteando base de datos: {e}")
        raise


if __name__ == "__main__":
    # Script principal para ejecutar desde línea de comandos
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "init":
            asyncio.run(initialize_database())
        elif command == "reset":
            asyncio.run(reset_database())
        else:
            print("Comandos disponibles: init, reset")
    else:
        print("Uso: python database_setup.py [init|reset]")
