"""
PostgreSQL Checkpointer mejorado para LangGraph basado en ejemplos oficiales
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from psycopg_pool import AsyncConnectionPool, ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class PostgresCheckpointerManager:
    """Gestor de checkpointer PostgreSQL optimizado para producción"""
    
    def __init__(self, db_uri: Optional[str] = None, pool_size: int = 20):
        settings = get_settings()
        self.db_uri = db_uri or settings.database_url
        self.pool_size = pool_size
        self._sync_pool = None
        self._sync_checkpointer = None
        self._async_pool = None
        self._setup_done = False
        
    @asynccontextmanager
    async def get_async_checkpointer(self) -> AsyncGenerator[AsyncPostgresSaver, None]:
        """Context manager para checkpointer asíncrono con pool de conexiones"""
        if self._async_pool is None:
            self._async_pool = AsyncConnectionPool(
                conninfo=self.db_uri,
                max_size=self.pool_size,
                min_size=5,
                timeout=30.0
            )
            await self._async_pool.open()
            logger.info(f"Created async connection pool with size {self.pool_size}")
        
        checkpointer = AsyncPostgresSaver(self._async_pool)
        
        # Setup solo la primera vez con manejo especial de índices
        if not self._setup_done:
            try:
                # Hacer setup sin índices concurrentes
                await self._safe_setup(checkpointer)
                self._setup_done = True
                logger.info("PostgreSQL checkpointer setup completed")
            except Exception as e:
                logger.error(f"Error setting up checkpointer: {e}")
                raise
        
        try:
            yield checkpointer
        except Exception as e:
            logger.error(f"Error using async checkpointer: {e}")
            raise
    
    async def _safe_setup(self, checkpointer: AsyncPostgresSaver):
        """Setup seguro que maneja problemas de índices concurrentes"""
        try:
            # Primero intentar setup normal
            await checkpointer.setup()
        except Exception as e:
            if "CONCURRENTLY" in str(e) and "transaction block" in str(e):
                logger.warning("Concurrent index creation failed, will use simple tables")
                # No intentar manual setup, simplemente continuar sin índices optimizados
                logger.info("Continuing without concurrent indexes (they can be added manually later)")
            else:
                raise
    
    async def _manual_setup(self, checkpointer: AsyncPostgresSaver):
        """Setup manual sin índices concurrentes"""
        async with self._async_pool.connection() as conn:
            # Usar el SQL exacto de LangGraph para compatibilidad
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    type TEXT,
                    checkpoint JSONB NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}',
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                );
            """)
            
            # Tabla de blobs con el esquema correcto
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    version TEXT NOT NULL,
                    type TEXT NOT NULL,
                    blob BYTEA,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, channel, version)
                );
            """)
            
            # Tabla de checkpoint_writes para LangGraph
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
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                );
            """)
            
            # Crear índices normales (no concurrentes)
            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS ix_checkpoints_thread_id_ns 
                    ON checkpoints (thread_id, checkpoint_ns);
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS ix_checkpoint_blobs_thread_id_ns 
                    ON checkpoint_blobs (thread_id, checkpoint_ns);
                """)
                
                logger.info("Manual setup completed successfully")
            except Exception as idx_error:
                logger.warning(f"Index creation warning: {idx_error}")
                # Continuar sin índices si es necesario
    
    def get_sync_checkpointer(self) -> PostgresSaver:
        """Checkpointer síncrono con pool de conexiones"""
        if self._sync_pool is None:
            self._sync_pool = ConnectionPool(
                conninfo=self.db_uri,
                max_size=self.pool_size,
                min_size=5,
                timeout=30.0
            )
            self._sync_pool.open(wait=True)
            logger.info(f"Created sync connection pool with size {self.pool_size}")
            
        if self._sync_checkpointer is None:
            self._sync_checkpointer = PostgresSaver(self._sync_pool)
            
            # Setup solo la primera vez con manejo seguro
            if not self._setup_done:
                try:
                    self._safe_sync_setup(self._sync_checkpointer)
                    self._setup_done = True
                    logger.info("PostgreSQL checkpointer setup completed")
                except Exception as e:
                    logger.error(f"Error setting up checkpointer: {e}")
                    raise
                
        return self._sync_checkpointer
    
    def _safe_sync_setup(self, checkpointer: PostgresSaver):
        """Setup seguro síncrono"""
        try:
            # Intentar setup normal
            checkpointer.setup()
        except Exception as e:
            if "CONCURRENTLY" in str(e) and "transaction block" in str(e):
                logger.warning("Concurrent index creation failed, will use simple tables")
                # No intentar manual setup, simplemente continuar sin índices optimizados
                logger.info("Continuing without concurrent indexes (they can be added manually later)")
            else:
                raise
    
    def _manual_sync_setup(self):
        """Setup manual síncrono"""
        with self._sync_pool.connection() as conn:
            with conn.cursor() as cursor:
                # Crear tablas básicas con esquema correcto
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        thread_id TEXT NOT NULL,
                        checkpoint_ns TEXT NOT NULL DEFAULT '',
                        checkpoint_id TEXT NOT NULL,
                        parent_checkpoint_id TEXT,
                        type TEXT,
                        checkpoint JSONB NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}',
                        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_blobs (
                        thread_id TEXT NOT NULL,
                        checkpoint_ns TEXT NOT NULL DEFAULT '',
                        checkpoint_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        version TEXT NOT NULL,
                        type TEXT NOT NULL,
                        blob BYTEA,
                        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, channel, version)
                    );
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_writes (
                        thread_id TEXT NOT NULL,
                        checkpoint_ns TEXT NOT NULL DEFAULT '',
                        checkpoint_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        idx INTEGER NOT NULL,
                        channel TEXT NOT NULL,
                        type TEXT,
                        blob BYTEA,
                        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                    );
                """)
                
                # Crear índices normales
                try:
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS ix_checkpoints_thread_id_ns 
                        ON checkpoints (thread_id, checkpoint_ns);
                    """)
                    
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS ix_checkpoint_blobs_thread_id_ns 
                        ON checkpoint_blobs (thread_id, checkpoint_ns);
                    """)
                    
                    logger.info("Manual sync setup completed successfully")
                except Exception as idx_error:
                    logger.warning(f"Sync index creation warning: {idx_error}")
                    # Continuar sin índices si es necesario
    
    async def health_check(self) -> bool:
        """Verificar salud de la conexión y checkpointer"""
        try:
            async with self.get_async_checkpointer() as checkpointer:
                # Intentar operación simple
                config = {"configurable": {"thread_id": "health_check_test"}}
                await checkpointer.aget_tuple(config)
                logger.debug("PostgreSQL checkpointer health check passed")
                return True
        except Exception as e:
            logger.error(f"PostgreSQL checkpointer health check failed: {e}")
            return False
    
    async def close(self):
        """Cerrar pools de conexiones"""
        if self._async_pool:
            await self._async_pool.close()
            logger.info("Closed async connection pool")
            
        if self._sync_pool:
            self._sync_pool.close()
            logger.info("Closed sync connection pool")
    
    def __enter__(self):
        """Soporte para context manager síncrono"""
        return self.get_sync_checkpointer()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup al salir del context manager"""
        if self._sync_pool:
            self._sync_pool.close()


class MonitoredAsyncPostgresSaver(AsyncPostgresSaver):
    """Checkpointer con monitoreo y logging para debugging"""
    
    def __init__(self, pool):
        super().__init__(pool)
        self.logger = logging.getLogger(f"{__name__}.MonitoredSaver")
    
    async def aput(self, config, checkpoint, metadata, new_versions):
        """Override con logging de operaciones de escritura"""
        thread_id = config["configurable"].get("thread_id", "unknown")
        
        try:
            self.logger.debug(f"Saving checkpoint for thread: {thread_id}")
            result = await super().aput(config, checkpoint, metadata, new_versions)
            self.logger.info(f"Checkpoint saved successfully for thread: {thread_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error saving checkpoint for thread {thread_id}: {e}")
            raise
    
    async def aget_tuple(self, config):
        """Override con logging de operaciones de lectura"""
        thread_id = config["configurable"].get("thread_id", "unknown")
        
        try:
            self.logger.debug(f"Loading checkpoint for thread: {thread_id}")
            result = await super().aget_tuple(config)
            
            if result and result.checkpoint:
                self.logger.debug(f"Checkpoint loaded for thread: {thread_id}")
            else:
                self.logger.debug(f"No checkpoint found for thread: {thread_id}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Error loading checkpoint for thread {thread_id}: {e}")
            raise


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