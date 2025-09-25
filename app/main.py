import asyncio
import logging

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.auth_middleware import authenticate_request
from app.api.router import api_router
from app.config.langsmith_init import get_langsmith_status, initialize_langsmith
from app.config.settings import get_settings

sentry_sdk.init(
    dsn="https://d44f9586fda96f0cb06a8e8bda42a3bb@o4509520816963584.ingest.us.sentry.io/4509520843243520",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
)

# Configuración del logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)
settings = get_settings()


def create_app() -> FastAPI:
    """
    Crea y configura la aplicación FastAPI
    """
    # Inicialización de la aplicación
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
    )

    # Configuración de CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware de autenticación
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        try:
            # Autenticar solicitud
            await authenticate_request(request)
            # Continuar con la solicitud
            response = await call_next(request)
            return response
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={"detail": str(e)},
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Manejador de excepciones global
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception handler caught: {str(exc)}", exc_info=True)
        return JSONResponse(status_code=500, content={"message": "Internal Server Error"})

    # Registro de routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Ruta de health check
    @app.get("/health", tags=["health"])
    async def health_check():
        """
        Verifica el estado de la aplicación
        """
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    @app.get("/")
    async def root():  # pyright: ignore
        return {
            "message": "Bienvenido a la API",
            "version": settings.VERSION,
            "documentation_urls": {"swagger": app.docs_url, "redoc": app.redoc_url},
        }

    # Background task management
    _background_tasks = set()

    async def _run_background_initial_sync(sync_service):
        """Ejecuta sincronización inicial en background sin bloquear el startup."""
        try:
            logger.info("Starting background initial sync check...")
            sync_executed = await sync_service.force_sync_if_needed()
            if sync_executed:
                logger.info("✅ Background initial sync completed successfully")
            else:
                logger.info("ℹ️ Background initial sync not needed (data is recent)")
        except Exception as e:
            logger.error(f"❌ Background initial sync failed: {e}", exc_info=True)
        finally:
            logger.info("Background initial sync task finished")

    # Startup event - iniciar servicios de background
    @app.on_event("startup")
    async def startup_event():
        """Inicia servicios de background al arrancar la aplicación."""
        logger.info("Starting background services...")

        # Initialize LangSmith tracing
        try:
            langsmith_initialized = initialize_langsmith(force=True)
            if langsmith_initialized:
                logger.info("✅ LangSmith tracing initialized successfully")
                status = get_langsmith_status()
                logger.info(f"   Project: {status.get('project')}")
                logger.info(f"   Tracing enabled: {status.get('tracing_enabled')}")
            else:
                logger.warning("⚠️ LangSmith tracing not initialized (may be disabled or misconfigured)")
        except Exception as e:
            logger.error(f"Error initializing LangSmith: {e}")

        # Verificar configuraciones críticas
        try:
            # Verificar configuración DUX
            if not settings.DUX_API_KEY:
                logger.warning("DUX_API_KEY not configured - DUX sync will be disabled")
            
            # Iniciar sincronización programada DUX si está habilitada
            if settings.DUX_SYNC_ENABLED and settings.DUX_API_KEY:
                from app.services.scheduled_sync_service import get_scheduled_sync_service

                # Usar sincronización RAG integrada por defecto
                sync_service = get_scheduled_sync_service(use_rag_sync=True)
                await sync_service.start()
                
                # Verificar estado inicial
                initial_status = await sync_service.get_sync_status()
                logger.info(
                    f"DUX scheduled sync service started - Mode: {initial_status['sync_mode']}, "
                    f"Next sync: {initial_status['next_scheduled_sync']}"
                )
                
                # Ejecutar sincronización inicial en background (no bloquear startup)
                background_sync_task = asyncio.create_task(
                    _run_background_initial_sync(sync_service)
                )
                _background_tasks.add(background_sync_task)
                background_sync_task.add_done_callback(_background_tasks.discard)
                logger.info("Background initial sync task created and will run asynchronously")
                    
            elif not settings.DUX_SYNC_ENABLED:
                logger.info("DUX sync is disabled via DUX_SYNC_ENABLED=False")
                
            # Verificar conectividad con servicios externos
            await _verify_external_services()
            
            logger.info("Background services startup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during startup: {e}", exc_info=True)
            # No detener la aplicación por errores en servicios background
            logger.warning("Application will continue despite background service errors")

    # Shutdown event - detener servicios de background
    @app.on_event("shutdown")
    async def shutdown_event():
        """Detiene servicios de background al cerrar la aplicación."""
        logger.info("Stopping background services...")

        try:
            # Detener sincronización programada DUX
            if settings.DUX_SYNC_ENABLED:
                from app.services.scheduled_sync_service import get_scheduled_sync_service

                sync_service = get_scheduled_sync_service()
                await sync_service.stop()
                logger.info("DUX scheduled sync service stopped")
                
            # Cerrar conexiones de base de datos si es necesario
            # (SQLAlchemy async sessions se manejan automáticamente)
            
            logger.info("Background services shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            
    async def _verify_external_services():
        """Verifica conectividad con servicios externos críticos"""
        try:
            # Verificar conectividad DUX API
            if settings.DUX_API_KEY:
                from app.clients.dux_api_client import DuxApiClientFactory
                
                async with DuxApiClientFactory.create_client() as client:
                    if await client.test_connection():
                        logger.info("✓ DUX API connectivity verified")
                    else:
                        logger.warning("⚠ DUX API connectivity failed")
            
            # Verificar Ollama (para embeddings)
            try:
                from app.services.embedding_update_service import EmbeddingUpdateService
                embedding_service = EmbeddingUpdateService()
                
                # Test simple para verificar si Ollama responde
                stats = embedding_service.get_collection_stats()
                logger.info(f"✓ ChromaDB/Ollama connectivity verified - Collections: {len(stats)}")
                
            except Exception as e:
                logger.warning(f"⚠ ChromaDB/Ollama connectivity failed: {e}")
                
        except Exception as e:
            logger.error(f"Error verifying external services: {e}")

    return app


# Instancia principal de la aplicación
app = create_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting application in {settings.ENVIRONMENT} mode")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=settings.DEBUG)
