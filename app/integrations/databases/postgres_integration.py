"""
Integración con PostgreSQL para checkpointing y datos
"""

import logging
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class PostgreSQLIntegration:
    """Gestiona la integración con PostgreSQL para LangGraph y datos"""

    def __init__(self, connection_string: str | None = None):
        self.settings = get_settings()
        self.connection_string = connection_string or self.settings.database_url

        # Para checkpointing de LangGraph (usa psycopg internamente)
        self._checkpointer: AsyncPostgresSaver | None = None
        self._checkpointer_context = None  # Context manager for cleanup

        # Para queries regulares
        self.engine = None
        self.async_session = None

    async def initialize(self):
        """Inicializa las conexiones de PostgreSQL"""
        await self._setup_regular_connection()
        await self._setup_checkpoint_connection()

    async def _setup_regular_connection(self):
        """Configura conexión regular para queries"""
        try:
            # Convertir URL para usar driver async
            async_url = self.connection_string.replace("postgresql://", "postgresql+asyncpg://")

            # Crear engine asíncrono
            self.engine = create_async_engine(
                async_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False,  # Cambiar a True para debug SQL
            )

            # Crear session maker
            self.async_session = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

            logger.info("PostgreSQL regular connection initialized")

        except Exception as e:
            logger.error(f"Error initializing PostgreSQL regular connection: {e}")
            raise

    async def _setup_checkpoint_connection(self):
        """Configura conexión para checkpointing de LangGraph (async con psycopg)"""
        try:
            # Asegurar URL sin driver específico (psycopg usa postgresql://)
            db_url = self.connection_string.replace("postgresql+asyncpg://", "postgresql://")

            # AsyncPostgresSaver.from_conn_string usa psycopg internamente
            # Guardamos el context manager para cleanup posterior
            self._checkpointer_context = AsyncPostgresSaver.from_conn_string(db_url)

            # Entrar al context manager manualmente (se cierra en close())
            self._checkpointer = await self._checkpointer_context.__aenter__()

            # Crear tablas de checkpointing si no existen
            await self._checkpointer.setup()

            logger.info("PostgreSQL async checkpoint connection initialized (psycopg)")

        except Exception as e:
            logger.error(f"Error initializing PostgreSQL checkpoint connection: {e}")
            raise

    def get_checkpointer(self) -> AsyncPostgresSaver:
        """
        Obtiene el checkpointer para LangGraph

        Returns:
            Instancia de AsyncPostgresSaver configurada
        """
        if self._checkpointer is None:
            raise RuntimeError("Checkpointer not initialized. Call initialize() first.")

        return self._checkpointer

    async def get_session(self) -> AsyncSession:
        """
        Obtiene una sesión de base de datos asíncrona

        Returns:
            Sesión de SQLAlchemy asíncrona
        """
        if self.async_session is None:
            raise RuntimeError("Database session not initialized. Call initialize() first.")

        return self.async_session()

    async def health_check(self) -> bool:
        """
        Verifica el estado de las conexiones PostgreSQL

        Returns:
            True si todas las conexiones están funcionando
        """
        try:
            # Verificar conexión regular
            regular_ok = await self._check_regular_connection()

            # Verificar conexión de checkpointing
            checkpoint_ok = await self._check_checkpoint_connection()

            return regular_ok and checkpoint_ok

        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")
            return False

    async def _check_regular_connection(self) -> bool:
        """Verifica la conexión regular"""
        try:
            if self.async_session is None:
                return False

            async with self.async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1

        except Exception as e:
            logger.error(f"Regular connection check failed: {e}")
            return False

    async def _check_checkpoint_connection(self) -> bool:
        """Verifica la conexión de checkpointing"""
        try:
            # Verificar que el checkpointer existe y tiene conexión
            if self._checkpointer is None:
                return False

            # Intentar una query simple via SQLAlchemy para verificar tablas
            if self.async_session:
                async with self.async_session() as session:
                    result = await session.execute(
                        text("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'checkpoints')")
                    )
                    return bool(result.scalar())
            return True

        except Exception as e:
            logger.error(f"Checkpoint connection check failed: {e}")
            return False

    async def execute_query(self, query: str, params: dict[str, object] | None = None) -> list:
        """
        Ejecuta una query SQL y retorna resultados

        Args:
            query: Query SQL a ejecutar
            params: Parámetros para la query

        Returns:
            Lista de resultados
        """
        if self.async_session is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        try:
            async with self.async_session() as session:
                if params:
                    result = await session.execute(text(query), params)
                else:
                    result = await session.execute(text(query))

                return list(result.fetchall())

        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    async def get_conversation_checkpoints(self, thread_id: str, limit: int = 10) -> list:
        """
        Obtiene checkpoints de conversación

        Args:
            thread_id: ID del hilo de conversación
            limit: Número máximo de checkpoints

        Returns:
            Lista de checkpoints
        """
        try:
            if self._checkpointer is None:
                return []

            # Usar el checkpointer para obtener historial
            checkpoints = []
            async for checkpoint in self._checkpointer.alist({"configurable": {"thread_id": thread_id}}, limit=limit):
                checkpoints.append(checkpoint)

            return checkpoints

        except Exception as e:
            logger.error(f"Error getting conversation checkpoints: {e}")
            return []

    async def cleanup_old_checkpoints(self, days_old: int = 30) -> int:
        """
        Limpia checkpoints antiguos

        Args:
            days_old: Días de antigüedad para limpiar

        Returns:
            Número de checkpoints eliminados
        """
        try:
            if self.async_session is None:
                return 0

            async with self.async_session() as session:
                # Query para eliminar checkpoints antiguos (usa SQLAlchemy)
                result = await session.execute(
                    text("DELETE FROM checkpoints WHERE created_at < NOW() - INTERVAL :days DAY"),
                    {"days": days_old},
                )
                await session.commit()
                deleted_count = result.rowcount

                logger.info(f"Cleaned up {deleted_count} old checkpoints")
                return deleted_count

        except Exception as e:
            logger.error(f"Error cleaning up old checkpoints: {e}")
            return 0

    async def get_checkpoint_stats(self) -> dict:
        """
        Obtiene estadísticas de checkpoints

        Returns:
            Diccionario con estadísticas
        """
        try:
            if self.async_session is None:
                return {}

            async with self.async_session() as session:
                # Contar checkpoints totales
                total_result = await session.execute(text("SELECT COUNT(*) FROM checkpoints"))
                total = total_result.scalar()

                # Contar por thread_id
                threads_result = await session.execute(text("SELECT COUNT(DISTINCT thread_id) FROM checkpoints"))
                threads = threads_result.scalar()

                return {
                    "total_checkpoints": total,
                    "unique_threads": threads,
                    "checkpointer_type": "AsyncPostgresSaver",
                }

        except Exception as e:
            logger.error(f"Error getting checkpoint stats: {e}")
            return {}

    async def backup_checkpoints(self, backup_path: str) -> bool:
        """
        Crea backup de los checkpoints

        Args:
            backup_path: Ruta del archivo de backup

        Returns:
            True si el backup fue exitoso
        """
        try:
            if self.async_session is None:
                return False

            async with self.async_session() as session:
                # Obtener todos los checkpoints
                result = await session.execute(text("SELECT * FROM checkpoints"))
                checkpoints = result.fetchall()

                # Guardar en archivo
                import pickle

                with open(backup_path, "wb") as f:
                    pickle.dump(checkpoints, f)

                logger.info(f"Checkpoints backed up to {backup_path}")
                return True

        except Exception as e:
            logger.error(f"Error backing up checkpoints: {e}")
            return False

    async def get_connection_info(self) -> dict:
        """
        Obtiene información sobre las conexiones

        Returns:
            Información de conexiones
        """
        try:
            info = {
                "regular_connection": {
                    "status": "initialized" if self.engine else "not_initialized",
                    "pool_size": getattr(self.engine.pool, "size", 0) if self.engine else 0,
                    "checked_out": getattr(self.engine.pool, "checkedout", 0) if self.engine else 0,
                },
                "checkpoint_connection": {
                    "status": "initialized" if self._checkpointer else "not_initialized",
                    "type": "AsyncPostgresSaver (psycopg)",
                },
            }

            return info

        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            return {}

    async def close(self):
        """Cierra todas las conexiones"""
        try:
            # Cerrar engine regular
            if self.engine:
                await self.engine.dispose()
                logger.info("Regular PostgreSQL connection closed")

            # Cerrar checkpointer context manager (psycopg pool)
            if self._checkpointer_context:
                await self._checkpointer_context.__aexit__(None, None, None)
                logger.info("Checkpoint PostgreSQL connection closed")

        except Exception as e:
            logger.error(f"Error closing PostgreSQL connections: {e}")

    async def __aenter__(self):
        """Context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        print("Closing PostgreSQL connection", exc_type, exc_val, exc_tb)
        await self.close()

    # Métodos de conveniencia para operaciones comunes
    async def save_conversation_metadata(self, thread_id: str, metadata: dict) -> bool:
        """
        Guarda metadatos de conversación

        Args:
            thread_id: ID del hilo
            metadata: Metadatos a guardar

        Returns:
            True si se guardó correctamente
        """
        if self.async_session is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        try:
            async with self.async_session() as session:
                # Usar raw SQL para hacer upsert correctamente
                query = text(
                    """
                INSERT INTO conversation_metadata (thread_id, metadata, updated_at)
                VALUES (:thread_id, :metadata, NOW())
                ON CONFLICT (thread_id)
                DO UPDATE SET metadata = :metadata, updated_at = NOW()
                """
                )

                await session.execute(query, {"thread_id": thread_id, "metadata": metadata})
                await session.commit()

                return True

        except Exception as e:
            logger.error(f"Error saving conversation metadata: {e}")
            return False

    async def get_conversation_metadata(self, thread_id: str) -> Optional[dict]:
        """
        Obtiene metadatos de conversación

        Args:
            thread_id: ID del hilo

        Returns:
            Metadatos si existen
        """
        if self.async_session is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        try:
            async with self.async_session() as session:
                query = text(
                    """
                SELECT metadata FROM conversation_metadata
                WHERE thread_id = :thread_id
                """
                )

                result = await session.execute(query, {"thread_id": thread_id})
                row = result.fetchone()

                return row[0] if row else None

        except Exception as e:
            logger.error(f"Error getting conversation metadata: {e}")
            return None
