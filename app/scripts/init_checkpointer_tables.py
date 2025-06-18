"""
Script para crear las tablas del checkpointer de LangGraph en PostgreSQL
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import asyncpg

from app.config.settings import get_settings

# Agregar el directorio raíz al path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_checkpointer_tables(db_url: Optional[str] = None):
    """Crea las tablas necesarias para el checkpointer de LangGraph"""

    settings = get_settings()
    database_url = db_url or settings.database_url

    # Convertir database url de SQLAlchemy a asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgres://", 1)

    conn = None
    try:
        logger.info("Conectando a la base de datos...")
        conn = await asyncpg.connect(database_url)

        # Crear tabla checkpoints
        logger.info("Creando tabla checkpoints...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );
        """)

        # Crear tabla checkpoint_blobs
        logger.info("Creando tabla checkpoint_blobs...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                version TEXT NOT NULL,
                type TEXT NOT NULL,
                blob BYTEA,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, channel, version)
            );
        """)

        # Crear tabla checkpoint_writes
        logger.info("Creando tabla checkpoint_writes...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                blob BYTEA,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
        """)

        # Crear índices para mejorar el rendimiento
        logger.info("Creando índices...")

        # Índices para checkpoints
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
            ON checkpoints (thread_id);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id_ns 
            ON checkpoints (thread_id, checkpoint_ns);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
            ON checkpoints (created_at DESC);
        """)

        # Índices para checkpoint_blobs
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoint_blobs_thread_id 
            ON checkpoint_blobs (thread_id);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoint_blobs_thread_id_ns 
            ON checkpoint_blobs (thread_id, checkpoint_ns);
        """)

        # Índices para checkpoint_writes
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id 
            ON checkpoint_writes (thread_id);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id_ns 
            ON checkpoint_writes (thread_id, checkpoint_ns);
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_checkpoint_id 
            ON checkpoint_writes (checkpoint_id);
        """)

        logger.info("✅ Tablas del checkpointer creadas exitosamente!")

        # Verificar las tablas creadas
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes')
            ORDER BY tablename;
        """)

        logger.info("\nTablas creadas:")
        for table in tables:
            logger.info(f"  - {table['tablename']}")

        # Mostrar información sobre los índices
        indexes = await conn.fetch("""
            SELECT indexname, tablename 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes')
            ORDER BY tablename, indexname;
        """)

        logger.info("\nÍndices creados:")
        for idx in indexes:
            logger.info(f"  - {idx['indexname']} en tabla {idx['tablename']}")

    except Exception as e:
        logger.error(f"Error al crear las tablas del checkpointer: {e}")
        raise
    finally:
        if conn:
            await conn.close()
            logger.info("Conexión cerrada")


async def verify_tables():
    """Verifica que las tablas del checkpointer existan y muestra su estructura"""

    settings = get_settings()
    database_url = settings.database_url

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgres://", 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)

        # Verificar estructura de cada tabla
        tables = ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]

        logger.info("\n📊 Estructura de las tablas del checkpointer:")

        for table_name in tables:
            logger.info(f"\n🔸 Tabla: {table_name}")

            # Obtener columnas
            columns = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position;
            """,
                table_name,
            )

            if columns:
                logger.info("  Columnas:")
                for col in columns:
                    nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col["column_default"] else ""
                    logger.info(f"    - {col['column_name']}: {col['data_type']} {nullable}{default}")
            else:
                logger.warning(f"  ⚠️  La tabla {table_name} no existe")

    except Exception as e:
        logger.error(f"Error al verificar las tablas: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def cleanup_old_checkpoints(days: int = 7):
    """Limpia checkpoints antiguos (opcional)"""

    settings = get_settings()
    database_url = settings.database_url

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgres://", 1)

    conn = None
    try:
        conn = await asyncpg.connect(database_url)

        # Contar checkpoints antes de limpiar
        count_before = await conn.fetchval(
            """
            SELECT COUNT(*) FROM checkpoints 
            WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
        """,
            days,
        )

        if count_before > 0:
            logger.info(f"Encontrados {count_before} checkpoints antiguos (más de {days} días)")

            # Limpiar checkpoints antiguos
            deleted = await conn.execute(
                """
                DELETE FROM checkpoints 
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            """,
                days,
            )

            # También limpiar las tablas relacionadas
            await conn.execute("""
                DELETE FROM checkpoint_blobs 
                WHERE (thread_id, checkpoint_ns, checkpoint_id) NOT IN 
                (SELECT thread_id, checkpoint_ns, checkpoint_id FROM checkpoints)
            """)

            await conn.execute("""
                DELETE FROM checkpoint_writes 
                WHERE (thread_id, checkpoint_ns, checkpoint_id) NOT IN 
                (SELECT thread_id, checkpoint_ns, checkpoint_id FROM checkpoints)
            """)

            logger.info(f"✅ Limpieza completada: {deleted}")
        else:
            logger.info("No hay checkpoints antiguos para limpiar")

    except Exception as e:
        logger.error(f"Error al limpiar checkpoints: {e}")
        raise
    finally:
        if conn:
            await conn.close()


async def main():
    """Función principal"""

    import argparse

    parser = argparse.ArgumentParser(description="Gestionar tablas del checkpointer de LangGraph")
    parser.add_argument("--verify", action="store_true", help="Verificar estructura de las tablas")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Limpiar checkpoints más antiguos que N días")

    args = parser.parse_args()

    try:
        if args.verify:
            await verify_tables()
        elif args.cleanup:
            await cleanup_old_checkpoints(args.cleanup)
        else:
            # Por defecto, crear las tablas
            await create_checkpointer_tables()
            await verify_tables()

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

