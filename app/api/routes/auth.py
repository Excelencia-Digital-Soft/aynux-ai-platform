from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.async_db import get_async_db
from app.models.auth import RefreshTokenRequest, TokenResponse, User, UserCreate
from app.models.db.tenancy import Organization, OrganizationUser
from app.models.db.user import UserDB
from app.services.token_service import TokenService
from app.services.user_service import UserService

router = APIRouter()
token_service = TokenService()
user_service = UserService()


class LoginRequest(BaseModel):
    """Schema for JSON login request."""

    email: str
    password: str


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
):
    """
    Endpoint para obtener un token de acceso (OAuth2 form data)
    """
    user = await user_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Obtener scopes del usuario
    scopes = await user_service.get_user_scopes(user.username)

    # Crear tokens
    access_token = token_service.create_access_token(data={"sub": user.username, "scopes": scopes})
    refresh_token = token_service.create_refresh_token(data={"sub": user.username, "scopes": scopes})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/login", response_model=TokenResponse)
async def login_with_json(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Endpoint para login con JSON (email y password).

    Usado por Streamlit y otras aplicaciones que no usan OAuth2 form.
    """
    # Find user by email
    stmt = select(UserDB).where(UserDB.email == login_data.email)
    result = await db.execute(stmt)
    user_db = result.scalar_one_or_none()

    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    # Verify password
    if not token_service.verify_password(login_data.password, user_db.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    if user_db.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario deshabilitado",
        )

    # Create tokens with user ID as sub (not username)
    token_data = {
        "sub": str(user_db.id),
        "username": user_db.username,
        "scopes": user_db.scopes or [],
    }

    access_token = token_service.create_access_token(data=token_data)
    refresh_token = token_service.create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(refresh_request: RefreshTokenRequest):
    """
    Endpoint para actualizar un token de acceso
    """
    # Verificar el refresh token
    if not token_service.verify_token(refresh_request.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de actualización inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decodificar el token
    payload = token_service.decode_token(refresh_request.refresh_token)

    # Verificar si es un token de actualización
    if payload.get("token_type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No es un token de actualización válido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    scopes = payload.get("scopes", [])

    # Crear nuevos tokens
    access_token = token_service.create_access_token(data={"sub": username, "scopes": scopes})
    refresh_token = token_service.create_refresh_token(data={"sub": username, "scopes": scopes})

    # Revocar el token de actualización anterior
    token_service.revoke_token(refresh_request.refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/register", response_model=User)
async def register_user(user_data: UserCreate):
    """
    Endpoint para registrar un nuevo usuario
    """
    try:
        user = await user_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear usuario: {str(e)}",
        ) from e


@router.post("/logout")
async def logout(token: str = Depends(token_service.oauth2_scheme)):
    """
    Endpoint para cerrar sesión (revoca el token)
    """
    success = token_service.revoke_token(token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al cerrar sesión",
        )

    return {"message": "Sesión cerrada correctamente"}


@router.get("/me")
async def get_current_user_info(
    token: str = Depends(token_service.oauth2_scheme),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get current user information with their organizations.

    Returns user data and list of organizations the user belongs to.
    """
    # Verify and decode token
    if not token_service.verify_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = token_service.decode_token(token)
    user_id_str = payload.get("sub")
    current_org_id = payload.get("org_id")

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: falta sub",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        # Legacy token with username as sub, try to find user by username
        stmt = select(UserDB).where(UserDB.username == user_id_str)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )
        user_id = user.id
    else:
        stmt = select(UserDB).where(UserDB.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado",
            )

    # Get user's organizations with their roles
    stmt = (
        select(OrganizationUser)
        .where(OrganizationUser.user_id == user.id)
        .options(selectinload(OrganizationUser.organization))
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    # Build organizations list
    organizations = []
    current_organization = None

    for membership in memberships:
        org = membership.organization
        if org:
            org_data = {
                "id": str(org.id),
                "slug": org.slug,
                "name": org.name,
                "display_name": org.display_name or org.name,
                "role": membership.role,
                "status": org.status,
            }
            organizations.append(org_data)

            # Check if this is the current organization from token
            if current_org_id and str(org.id) == current_org_id:
                current_organization = org_data

    # If no current org but user has organizations, default to first one
    if not current_organization and organizations:
        current_organization = organizations[0]

    return {
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "disabled": user.disabled,
            "scopes": user.scopes or [],
        },
        "organizations": organizations,
        "current_organization": current_organization,
    }
