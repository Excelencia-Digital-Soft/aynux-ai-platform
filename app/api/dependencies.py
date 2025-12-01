import hashlib
import hmac
import logging
import os
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Path, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import Settings, get_settings
from app.core.container import DependencyContainer, get_container
from app.database.async_db import get_async_db
from app.models.auth import User
from app.models.db.tenancy import Organization, OrganizationUser
from app.models.db.user import UserDB
from app.orchestration import SuperOrchestrator
from app.services.token_service import TokenService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

API_V1_STR = os.getenv("API_V1_STR", "/api/v1")

token_service = TokenService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_STR}/auth/token")


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


# ============================================================
# TENANCY AUTHENTICATION DEPENDENCIES
# ============================================================


async def get_current_user_db(
    token: str = Depends(oauth2_scheme),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> UserDB:
    """
    Get current authenticated user from database.

    Returns UserDB model instance with full user data.
    Supports both UUID-based tokens (new) and username-based tokens (legacy).
    """
    # Verify token
    if not token_service.verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = token_service.decode_token(token)
    user_id_str = payload.get("sub")

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta sub",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try to parse as UUID first (new format), fallback to username (legacy)
    try:
        user_id = UUID(user_id_str)
        stmt = select(UserDB).where(UserDB.id == user_id)
    except ValueError:
        # Legacy token with username as sub
        stmt = select(UserDB).where(UserDB.username == user_id_str)

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario deshabilitado",
        )

    return user


async def get_current_user_with_org(
    token: str = Depends(oauth2_scheme),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> tuple[UserDB, Organization | None, str | None]:
    """
    Get current user with organization context from JWT.

    Returns tuple of (UserDB, Organization or None, role or None).
    Organization and role come from JWT payload if present.
    """
    user = await get_current_user_db(token, db)

    # Extract org context from token
    payload = token_service.decode_token(token)
    org_id_str = payload.get("org_id")
    role = payload.get("role")

    org = None
    if org_id_str:
        try:
            org_id = UUID(org_id_str)
            stmt = select(Organization).where(Organization.id == org_id)
            result = await db.execute(stmt)
            org = result.scalar_one_or_none()
        except ValueError:
            pass

    return user, org, role


async def verify_org_membership(
    org_id: UUID = Path(..., description="Organization ID"),  # noqa: B008
    user: UserDB = Depends(get_current_user_db),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> OrganizationUser:
    """
    Verify that the current user is a member of the specified organization.

    Returns OrganizationUser membership record if user is a member.
    Raises 403 Forbidden if user is not a member.
    """
    stmt = select(OrganizationUser).where(
        OrganizationUser.organization_id == org_id,
        OrganizationUser.user_id == user.id,
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No eres miembro de esta organización",
        )

    return membership


async def require_admin(
    org_id: UUID = Path(..., description="Organization ID"),  # noqa: B008
    user: UserDB = Depends(get_current_user_db),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> OrganizationUser:
    """
    Require admin or owner role in the organization.

    Returns OrganizationUser membership record if user has admin access.
    Raises 403 Forbidden if user doesn't have admin privileges.
    """
    membership = await verify_org_membership(org_id, user, db)

    if not membership.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de administrador o propietario",
        )

    return membership


async def require_owner(
    org_id: UUID = Path(..., description="Organization ID"),  # noqa: B008
    user: UserDB = Depends(get_current_user_db),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> OrganizationUser:
    """
    Require owner role in the organization.

    Returns OrganizationUser membership record if user is the owner.
    Raises 403 Forbidden if user is not the owner.
    """
    membership = await verify_org_membership(org_id, user, db)

    if not membership.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere rol de propietario",
        )

    return membership


async def get_organization_by_id(
    org_id: UUID = Path(..., description="Organization ID"),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),  # noqa: B008
) -> Organization:
    """
    Get organization by ID.

    Returns Organization model if found.
    Raises 404 Not Found if organization doesn't exist.
    """
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organización no encontrada",
        )

    return org
