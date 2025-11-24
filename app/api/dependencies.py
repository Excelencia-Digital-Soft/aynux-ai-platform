import hashlib
import hmac
import logging
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config.settings import Settings, get_settings
from app.core.container import DependencyContainer, get_container
from app.models.auth import User
from app.orchestration import SuperOrchestrator
from app.services.token_service import TokenService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

token_service = TokenService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ============================================================
# NEW ARCHITECTURE DEPENDENCIES
# ============================================================


def get_di_container() -> DependencyContainer:
    """
    Get Dependency Injection Container.

    This provides access to all domain services, agents, and dependencies
    following Clean Architecture and SOLID principles.

    Returns:
        DependencyContainer instance
    """
    return get_container()


def get_super_orchestrator(
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
) -> SuperOrchestrator:
    """
    Get Super Orchestrator instance.

    The SuperOrchestrator routes messages to appropriate domain agents
    based on detected intent and business domain.

    Args:
        container: Dependency injection container

    Returns:
        SuperOrchestrator instance configured with all domain agents
    """
    return container.create_super_orchestrator()


# ============================================================
# ADMIN USE CASES DEPENDENCIES
# ============================================================


def get_list_domains_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get ListDomainsUseCase instance"""
    return container.create_list_domains_use_case(db)


def get_enable_domain_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get EnableDomainUseCase instance"""
    return container.create_enable_domain_use_case(db)


def get_disable_domain_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get DisableDomainUseCase instance"""
    return container.create_disable_domain_use_case(db)


def get_update_domain_config_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get UpdateDomainConfigUseCase instance"""
    return container.create_update_domain_config_use_case(db)


def get_get_contact_domain_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get GetContactDomainUseCase instance"""
    return container.create_get_contact_domain_use_case(db)


def get_assign_contact_domain_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get AssignContactDomainUseCase instance"""
    return container.create_assign_contact_domain_use_case(db)


def get_remove_contact_domain_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get RemoveContactDomainUseCase instance"""
    return container.create_remove_contact_domain_use_case(db)


def get_clear_domain_assignments_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get ClearDomainAssignmentsUseCase instance"""
    return container.create_clear_domain_assignments_use_case(db)


def get_get_domain_stats_use_case(
    db,
    container: DependencyContainer = Depends(get_di_container),  # noqa: B008
):
    """Get GetDomainStatsUseCase instance"""
    return container.create_get_domain_stats_use_case(db)


# ============================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:  # noqa: B008
    """
    Dependencia para obtener el usuario actual completo

    Returns:
        User: Objeto User completo con todos sus datos
    """
    # 1. Validar token y obtener username
    username = token_service.get_current_user(token)

    # 2. Obtener objeto User completo desde UserService
    user_service = UserService()
    user = await user_service.get_user_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_scopes(required_scopes: List[str]):
    """
    Dependencia para requerir scopes específicos

    Args:
        required_scopes: Lista de scopes requeridos
    """

    def dependency(token: str = Depends(oauth2_scheme)) -> None:  # noqa: B008
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
