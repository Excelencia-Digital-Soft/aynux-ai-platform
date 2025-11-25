from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config.settings import get_settings
from app.models.auth import TokenMetadata
from app.repositories.redis_repository import RedisRepository


class TokenService:
    """
    Servicio para gestionar tokens JWT y autenticación
    """

    def __init__(self):
        self.settings = get_settings()
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{self.settings.API_V1_STR}/auth/token")
        self.token_repo = RedisRepository[TokenMetadata](TokenMetadata, prefix="token")

        # Configuración JWT
        self.SECRET_KEY = self.settings.JWT_SECRET_KEY
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = self.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.REFRESH_TOKEN_EXPIRE_DAYS = self.settings.REFRESH_TOKEN_EXPIRE_DAYS

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifica si la contraseña coincide con el hash"""
        # Convertir contraseña y hash a bytes
        password_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)

    def get_password_hash(self, password: str) -> str:
        """Genera un hash para la contraseña"""
        # Convertir contraseña a bytes
        password_bytes = password.encode("utf-8")
        # Generar salt y hash
        salt = bcrypt.gensalt()
        hash_bytes = bcrypt.hashpw(password_bytes, salt)
        # Convertir hash de bytes a string
        return hash_bytes.decode("utf-8")

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Crea un token JWT de acceso

        Args:
            data: Datos a incluir en el token
            expires_delta: Tiempo de expiración (opcional)

        Returns:
            Token JWT codificado
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

        # Incluir tipo de token en el payload
        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "token_type": "access"})

        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

        # Almacenar token en Redis para permitir revocación
        token_id = to_encode.get("sub", "unknown")
        expiration_seconds = int((expire - datetime.now(timezone.utc)).total_seconds())

        # Crear modelo TokenMetadata para almacenar metadatos del token
        token_metadata = TokenMetadata(
            token=encoded_jwt,
            type="access",
            exp=expire.timestamp(),
            revoked=False,
            created_at=datetime.now(timezone.utc).timestamp(),
            user_id=token_id,
            scopes=data.get("scopes", []),
        )

        # Guardar en Redis
        self.token_repo.set(
            f"tokens:{token_id}:{encoded_jwt}",
            token_metadata,
            expiration=expiration_seconds,
        )

        return encoded_jwt

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Crea un token JWT de actualización

        Args:
            data: Datos a incluir en el token

        Returns:
            Token JWT de actualización
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)

        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "token_type": "refresh"})

        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

        # Almacenar refresh token en Redis
        token_id = to_encode.get("sub", "unknown")
        expiration_seconds = int((expire - datetime.now(timezone.utc)).total_seconds())

        # Crear modelo TokenMetadata para almacenar metadatos del token
        token_metadata = TokenMetadata(
            token=encoded_jwt,
            type="refresh",
            exp=expire.timestamp(),
            revoked=False,
            created_at=datetime.now(timezone.utc).timestamp(),
            user_id=token_id,
            scopes=data.get("scopes", []),
        )

        # Guardar en Redis
        self.token_repo.set(
            f"tokens:{token_id}:{encoded_jwt}",
            token_metadata,
            expiration=expiration_seconds,
        )

        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decodifica un token JWT

        Args:
            token: Token JWT a decodificar

        Returns:
            Datos del token decodificado
        """
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    def verify_token(self, token: str) -> bool:
        """
        Verifica si un token es válido y no ha sido revocado

        Estrategia de validación:
        1. Verifica validez del JWT (firma y expiración)
        2. Intenta verificar en Redis (estado de revocación)
        3. Si Redis no tiene el token pero JWT es válido → acepta con advertencia (fallback)

        Args:
            token: Token JWT a verificar

        Returns:
            True si el token es válido, False en caso contrario
        """
        try:
            # Verificar validez del token JWT
            payload = self.decode_token(token)
            username = payload.get("sub")
            if username is None:
                return False

            # Verificar expiración del JWT
            exp = payload.get("exp")
            if exp and datetime.now(timezone.utc) > datetime.fromtimestamp(exp, tz=timezone.utc):
                return False  # Token expirado según JWT

            # Intentar verificar en Redis
            token_metadata = self.token_repo.get(f"tokens:{username}:{token}")

            if token_metadata:
                # Token encontrado en Redis → verificar si fue revocado
                if token_metadata.revoked:
                    return False  # Token revocado explícitamente
                return True  # Token válido en Redis

            # Token no encontrado en Redis pero JWT es válido
            # Esto puede ocurrir si:
            # - Redis se reinició (datos perdidos)
            # - Token generado antes de implementar persistencia en Redis
            # - Ambiente de desarrollo sin persistencia Redis
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Token válido pero no encontrado en Redis (usuario: {username}). "
                "Aceptando por fallback. Considera habilitar persistencia Redis en producción."
            )
            return True  # Fallback: aceptar si JWT es válido

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error al verificar token: {str(e)}")
            return False

    def revoke_token(self, token: str) -> bool:
        """
        Revoca un token

        Args:
            token: Token JWT a revocar

        Returns:
            True si se revocó correctamente, False en caso contrario
        """
        try:
            # Decodificar token para obtener datos
            payload = self.decode_token(token)
            username = payload.get("sub")
            if username is None:
                return False

            # Obtener datos actuales del token
            token_metadata = self.token_repo.get(f"tokens:{username}:{token}")

            if not token_metadata:
                return False

            # Actualizar estado a revocado
            token_metadata.revoked = True

            # Guardar en Redis con la misma expiración
            remaining_ttl = int(token_metadata.exp - datetime.now(timezone.utc).timestamp())
            if remaining_ttl > 0:
                return self.token_repo.set(f"tokens:{username}:{token}", token_metadata, expiration=remaining_ttl)
            return False

        except Exception:
            return False

    def get_current_user(self, token: str) -> str:
        """
        Obtiene el usuario actual a partir del token

        Args:
            token: Token JWT

        Returns:
            Nombre de usuario
        """
        if not self.verify_token(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = self.decode_token(token)
        username = payload.get("sub")

        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se pudo validar las credenciales",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return username

    def get_token_scopes(self, token: str) -> List[str]:
        """
        Obtiene los scopes de un token

        Args:
            token: Token JWT

        Returns:
            Lista de scopes
        """
        payload = self.decode_token(token)
        return payload.get("scopes", [])

    def get_user_active_tokens(self, user_id: str) -> List[TokenMetadata]:
        """
        Obtiene todos los tokens activos de un usuario

        Args:
            user_id: ID del usuario

        Returns:
            Lista de tokens activos
        """
        # Esta función requeriría escanear Redis por patrón
        # Por ahora retornamos lista vacía
        # TODO: Implementar scan de Redis si es necesario
        print(f"User {user_id} active tokens: []")
        return []
