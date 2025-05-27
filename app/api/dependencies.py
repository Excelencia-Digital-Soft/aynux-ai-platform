import hashlib
import hmac
import logging
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config.settings import Settings, get_settings
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

token_service = TokenService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependencia para obtener el usuario actual
    """
    return token_service.get_current_user(token)


def require_scopes(required_scopes: List[str]):
    """
    Dependencia para requerir scopes específicos

    Args:
        required_scopes: Lista de scopes requeridos
    """

    def dependency(token: str = Depends(oauth2_scheme)) -> None:
        payload = token_service.decode_token(token)
        user_scopes = payload.get("scopes", [])

        # Verificar si el usuario tiene los scopes requeridos
        for scope in required_scopes:
            if scope not in user_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permiso insuficiente. Se requiere el scope: {scope}",
                )

    return dependency


async def verify_signature(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),  # noqa: B008
):
    """
    Verifica la firma de las solicitudes entrantes de WhatsApp

    Esta dependencia se usa para asegurar que las solicitudes
    vengan realmente de WhatsApp.
    """
    if not x_hub_signature_256:
        logger.warning("Missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=403, detail="Missing signature header")

    # Extraer la firma del encabezado (remover 'sha256=')
    signature = x_hub_signature_256[7:] if x_hub_signature_256.startswith("sha256=") else x_hub_signature_256

    # Leer el cuerpo de la solicitud
    body = await request.body()

    # Calcular la firma esperada
    expected_signature = hmac.new(
        bytes(settings.JWT_SECRET_KEY, "latin-1"), msg=body, digestmod=hashlib.sha256
    ).hexdigest()

    # Verificar si las firmas coinciden (usando comparación segura)
    if not hmac.compare_digest(expected_signature, signature):
        logger.warning("Signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Si la firma es válida, continuamos con la solicitud
    return True
