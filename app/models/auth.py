from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Modelo base para usuarios"""

    username: str
    email: EmailStr
    full_name: Optional[str] = None
    disabled: bool = False


class UserCreate(UserBase):
    """Modelo para crear usuarios"""

    password: str


class User(UserBase):
    """Modelo de usuario completo"""

    id: str


class UserInDB(BaseModel):
    """Modelo para almacenar usuarios en Redis"""

    id: str
    username: str
    email: str
    password: str  # Contraseña hasheada
    full_name: Optional[str] = None
    disabled: bool = False
    scopes: List[str] = Field(default_factory=list)

    def to_user(self) -> User:
        """Convierte a modelo User (sin password)"""
        return User(
            id=self.id,
            username=self.username,
            email=self.email,
            full_name=self.full_name,
            disabled=self.disabled,
        )


class TokenPayload(BaseModel):
    """Modelo para el payload del token JWT"""

    sub: Optional[str] = None
    scopes: List[str] = []
    exp: Optional[int] = None


class TokenResponse(BaseModel):
    """Modelo para la respuesta de token"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Modelo para datos del token"""

    username: Optional[str] = None
    scopes: List[str] = []


class LoginRequest(BaseModel):
    """Modelo para solicitud de login"""

    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Modelo para solicitud de refresh token"""

    refresh_token: str


class TokenDataJwt(BaseModel):
    """Modelo para datos del token JWT"""

    sub: Optional[str] = None  # Nombre de usuario
    scopes: List[str] = Field(default_factory=list)
    exp: Optional[int] = None  # Timestamp de expiración
    iat: Optional[int] = None  # Timestamp de creación
    token_type: Optional[str] = None  # access o refresh


class TokenMetadata(BaseModel):
    """Modelo para metadatos de token almacenados en Redis"""

    token: str  # El token JWT
    type: str  # "access" o "refresh"
    exp: float  # Timestamp de expiración
    revoked: bool = False  # Si el token ha sido revocado
    created_at: float  # Timestamp de creación
    user_id: str  # ID del usuario
    scopes: List[str] = Field(default_factory=list)  # Permisos del token
