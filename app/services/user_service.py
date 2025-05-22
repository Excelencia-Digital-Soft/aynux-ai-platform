import uuid
from typing import List, Optional

from app.models.auth import User, UserCreate, UserInDB
from app.repositories.redis_repository import RedisRepository
from app.services.token_service import TokenService


class UserService:
    """
    Servicio para gestionar usuarios
    """

    def __init__(self):
        self.redis_repo = RedisRepository[UserInDB](UserInDB, prefix="user_auth")
        self.token_service = TokenService()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Obtiene un usuario por su nombre de usuario

        Args:
            username: Nombre de usuario

        Returns:
            Usuario si existe, None en caso contrario
        """
        # Obtener el ID del usuario por su nombre de usuario
        user_id = self.redis_repo.hash_get("usernames", username)

        if not user_id:
            return None

        # Obtener datos del usuario
        user_in_db = self.redis_repo.get(f"user:{user_id}")

        if not user_in_db:
            return None

        # Convertir a modelo User (sin exponer la contraseña)
        return user_in_db.to_user()

    async def create_user(self, user_data: UserCreate) -> User:
        """
        Crea un nuevo usuario

        Args:
            user_data: Datos del usuario

        Returns:
            Usuario creado
        """
        # Verificar si el usuario ya existe
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            raise ValueError(f"El usuario '{user_data.username}' ya existe")

        # Generar ID único
        user_id = str(uuid.uuid4())

        # Crear hash de la contraseña
        hashed_password = self.token_service.get_password_hash(user_data.password)

        # Crear modelo UserInDB para persistencia
        user_in_db = UserInDB(
            id=user_id,
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            full_name=user_data.full_name,
            disabled=user_data.disabled,
            scopes=[],  # Lista vacía por defecto
        )

        # Guardar el usuario completo como un objeto
        success = self.redis_repo.set(f"user:{user_id}", user_in_db)

        if not success:
            raise ValueError("Error al guardar el usuario en la base de datos")

        # Indexar por nombre de usuario para búsquedas rápidas
        self.redis_repo.hash_set("usernames", user_data.username, user_id)

        # Devolver modelo User público (sin contraseña)
        return User(
            id=user_id,
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            disabled=user_data.disabled,
        )

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Autentica un usuario

        Args:
            username: Nombre de usuario
            password: Contraseña

        Returns:
            Usuario si la autenticación es exitosa, None en caso contrario
        """
        # Obtener el ID del usuario mediante el índice
        user_id = self.redis_repo.hash_get("usernames", username)
        if not user_id:
            return None

        # Recuperar el usuario completo de Redis
        user_in_db = self.redis_repo.get(f"user:{user_id}")
        if not user_in_db:
            return None

        # Verificar si la contraseña es correcta
        if not self.token_service.verify_password(password, user_in_db.password):
            return None

        # Verificar si el usuario está deshabilitado
        if user_in_db.disabled:
            return None

        # Devolver modelo User público (sin contraseña)
        return User(
            id=user_in_db.id,
            username=user_in_db.username,
            email=user_in_db.email,
            full_name=user_in_db.full_name,
            disabled=user_in_db.disabled,
        )

    async def get_user_scopes(self, username: str) -> List[str]:
        """
        Obtiene los alcances (scopes) de un usuario

        Args:
            username: Nombre de usuario

        Returns:
            Lista de alcances
        """
        user_id = self.redis_repo.hash_get("usernames", username)
        if not user_id:
            return []

        # Obtener el usuario completo
        user_in_db = self.redis_repo.get(f"user:{user_id}")
        if not user_in_db:
            return []

        # Devolver la lista de scopes directamente del modelo
        return user_in_db.scopes

    async def update_user_scopes(self, username: str, scopes: List[str]) -> bool:
        """
        Actualiza los alcances de un usuario

        Args:
            username: Nombre de usuario
            scopes: Lista de alcances

        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        user_id = self.redis_repo.hash_get("usernames", username)
        if not user_id:
            return False

        # Obtener el usuario completo
        user_in_db = self.redis_repo.get(f"user:{user_id}")
        if not user_in_db:
            return False

        # Actualizar scopes en el modelo
        user_in_db.scopes = scopes

        # Guardar el modelo completo de nuevo en Redis
        return self.redis_repo.set(f"user:{user_id}", user_in_db)
