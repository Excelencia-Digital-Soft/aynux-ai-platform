from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.models.auth import RefreshTokenRequest, TokenResponse, User, UserCreate
from app.services.token_service import TokenService
from app.services.user_service import UserService

router = APIRouter()
token_service = TokenService()
user_service = UserService()


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Endpoint para obtener un token de acceso
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
    access_token = token_service.create_access_token(
        data={"sub": user.username, "scopes": scopes}
    )
    refresh_token = token_service.create_refresh_token(
        data={"sub": user.username, "scopes": scopes}
    )

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
    access_token = token_service.create_access_token(
        data={"sub": username, "scopes": scopes}
    )
    refresh_token = token_service.create_refresh_token(
        data={"sub": username, "scopes": scopes}
    )

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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear usuario: {str(e)}",
        )


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
