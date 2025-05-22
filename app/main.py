import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.auth_middleware import authenticate_request
from app.api.router import api_router
from app.config.settings import get_settings

# Configuración del logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

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
        return JSONResponse(
            status_code=500, content={"message": "Internal Server Error"}
        )

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

    return app


# Instancia principal de la aplicación
app = create_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting application in {settings.ENVIRONMENT} mode")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=settings.DEBUG)
