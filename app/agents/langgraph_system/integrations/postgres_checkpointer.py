"""
PostgreSQL Checkpointer para LangGraph usando la API oficial
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class PostgresCheckpointerManager:
    """Gestor de checkpointer PostgreSQL usando la API oficial de LangGraph"""

    def __init__(self, db_uri: Optional[str] = None):
        settings = get_settings()
        self.db_uri = db_uri or settings.database_url
        self._setup_done = False

    @asynccontextmanager
    async def get_async_checkpointer_context(self) -> AsyncGenerator[AsyncPostgresSaver, None]:
        """Context manager para checkpointer asíncrono usando la API oficial"""
        async with AsyncPostgresSaver.from_conn_string(self.db_uri) as checkpointer:
            # Hacer setup si es necesario
            if not self._setup_done:
                try:
                    await checkpointer.setup()
                    self._setup_done = True
                    logger.info("PostgreSQL checkpointer setup completed using official API")
                except Exception as e:
                    logger.warning(f"Setup warning (tables may exist): {e}")
                    self._setup_done = True

            yield checkpointer

    async def health_check(self) -> bool:
        """Verificar salud de la conexión y checkpointer"""
        try:
            async with AsyncPostgresSaver.from_conn_string(self.db_uri) as checkpointer:
                # Hacer un test básico
                config = {"configurable": {"thread_id": "health_check_test", "checkpoint_ns": "default"}}
                result = await checkpointer.aget_tuple(config)
                logger.debug("PostgreSQL checkpointer health check passed", result)
                return True
        except Exception as e:
            logger.error(f"PostgreSQL checkpointer health check failed: {e}")
            return False


# Instancia global para reutilización
_global_checkpointer_manager = None


def get_checkpointer_manager() -> PostgresCheckpointerManager:
    """Obtener instancia global del checkpointer manager"""
    global _global_checkpointer_manager

    if _global_checkpointer_manager is None:
        _global_checkpointer_manager = PostgresCheckpointerManager()

    return _global_checkpointer_manager


async def initialize_checkpointer():
    """Inicializar checkpointer al arrancar la aplicación"""
    manager = get_checkpointer_manager()

    # Verificar salud
    health_ok = await manager.health_check()

    if health_ok:
        logger.info("PostgreSQL checkpointer initialized and healthy")
    else:
        logger.warning("PostgreSQL checkpointer health check failed - using fallback")

    return health_ok

