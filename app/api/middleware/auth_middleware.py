from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer

from app.config.settings import get_settings
from app.services.token_service import TokenService

# Use settings instead of os.getenv for consistency
_settings = get_settings()
API_V1_STR = _settings.API_V1_STR

token_service = TokenService()
security = HTTPBearer()


async def authenticate_request(request: Request) -> Optional[Dict[str, Any]]:
    """
    Middleware para autenticar solicitudes

    Args:
        request: Solicitud FastAPI

    Returns:
        Payload del token si la autenticación es exitosa
    """
    # Rutas públicas que no requieren autenticación
    public_paths = [
        f"{API_V1_STR}/auth/token",
        f"{API_V1_STR}/auth/refresh",
        f"{API_V1_STR}/webhook",
        "/health",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    # Verificar si la ruta es pública
    path = request.url.path
    for public_path in public_paths:
        if path.startswith(public_path):
            return None

    try:
        # Obtener el token del encabezado
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Se requiere autenticación",
                headers={"WWW-Authenticate": "Bearer"},
            )

        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Se espera un esquema de autenticación Bearer",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verificar token
        if not token_service.verify_token(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Decodificar token
        payload = token_service.decode_token(token)
        return payload

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error de autenticación: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
