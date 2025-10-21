import logging
from typing import List, Optional

from app.database import get_db_context
from app.models.auth import User, UserCreate, UserInDB
from app.models.db.user import UserDB
from app.repositories.redis_repository import RedisRepository
from app.repositories.user_auth_repository import UserAuthRepository
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

# TTL para cache de usuario en Redis (5 minutos)
USER_CACHE_TTL = 300


class UserService:
    """
    Servicio para gestionar usuarios con persistencia híbrida PostgreSQL + Redis

    Estrategia:
    - PostgreSQL: Persistencia permanente (fuente de verdad)
    - Redis: Cache temporal para lookups rápidos (cache-aside pattern)
    """

    def __init__(self):
        self.redis_repo = RedisRepository[UserInDB](UserInDB, prefix="user_auth")
        self.token_service = TokenService()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Obtiene un usuario por su nombre de usuario (cache-aside pattern)

        Args:
            username: Nombre de usuario

        Returns:
            Usuario si existe, None en caso contrario
        """
        # 1. Intentar obtener del cache Redis
        user_id = self.redis_repo.hash_get("usernames", username)

        if user_id:
            user_in_db = self.redis_repo.get(f"user:{user_id}")
            if user_in_db:
                logger.debug(f"Usuario {username} encontrado en cache Redis")
                return user_in_db.to_user()

        # 2. Si no está en cache, buscar en PostgreSQL
        logger.debug(f"Usuario {username} no encontrado en cache, buscando en PostgreSQL")
        with get_db_context() as db:
            user_repo = UserAuthRepository(db)
            user_db = user_repo.get_by_username(username)

            if not user_db:
                return None

            # 3. Cachear en Redis para futuras consultas
            user_in_db = self._db_to_redis_model(user_db)
            self.redis_repo.set(f"user:{user_db.id}", user_in_db, expiration=USER_CACHE_TTL)
            self.redis_repo.hash_set("usernames", username, str(user_db.id))

            logger.info(f"Usuario {username} cargado desde PostgreSQL y cacheado en Redis")
            return user_in_db.to_user()

    async def create_user(self, user_data: UserCreate) -> User:
        """
        Crea un nuevo usuario en PostgreSQL y Redis

        Args:
            user_data: Datos del usuario

        Returns:
            Usuario creado
        """
        # Verificar si el usuario ya existe
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            raise ValueError(f"El usuario '{user_data.username}' ya existe")

        # Crear hash de la contraseña
        hashed_password = self.token_service.get_password_hash(user_data.password)

        # 1. Guardar en PostgreSQL (fuente de verdad)
        with get_db_context() as db:
            user_repo = UserAuthRepository(db)

            # Verificar si el email ya existe
            if user_repo.email_exists(user_data.email):
                raise ValueError(f"El email '{user_data.email}' ya está registrado")

            # Crear usuario en PostgreSQL
            user_db = user_repo.create_user(
                username=user_data.username,
                email=user_data.email,
                password_hash=hashed_password,
                full_name=user_data.full_name,
            )

            # 2. Cachear en Redis
            user_in_db = self._db_to_redis_model(user_db)
            self.redis_repo.set(f"user:{user_db.id}", user_in_db, expiration=USER_CACHE_TTL)
            self.redis_repo.hash_set("usernames", user_data.username, str(user_db.id))

            logger.info(f"Usuario creado: {user_data.username} (ID: {user_db.id})")

            # 3. Devolver modelo User público (sin contraseña)
            return User(
                id=str(user_db.id),
                username=user_db.username,
                email=user_db.email,
                full_name=user_db.full_name,
                disabled=user_db.disabled,
            )

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Autentica un usuario (cache-first con fallback a PostgreSQL)

        Args:
            username: Nombre de usuario
            password: Contraseña

        Returns:
            Usuario si la autenticación es exitosa, None en caso contrario
        """
        # 1. Intentar obtener usuario del cache Redis
        user_id = self.redis_repo.hash_get("usernames", username)
        user_in_db = None

        if user_id:
            user_in_db = self.redis_repo.get(f"user:{user_id}")

        # 2. Si no está en cache, buscar en PostgreSQL
        if not user_in_db:
            logger.debug(f"Autenticación: usuario {username} no en cache, consultando PostgreSQL")
            with get_db_context() as db:
                user_repo = UserAuthRepository(db)
                user_db = user_repo.get_by_username(username)

                if not user_db:
                    return None

                # Cachear para futuras autenticaciones
                user_in_db = self._db_to_redis_model(user_db)
                self.redis_repo.set(f"user:{user_db.id}", user_in_db, expiration=USER_CACHE_TTL)
                self.redis_repo.hash_set("usernames", username, str(user_db.id))

        # 3. Verificar contraseña
        if not self.token_service.verify_password(password, user_in_db.password):
            logger.warning(f"Intento de autenticación fallido para usuario: {username}")
            return None

        # 4. Verificar si el usuario está deshabilitado
        if user_in_db.disabled:
            logger.warning(f"Intento de autenticación de usuario deshabilitado: {username}")
            return None

        logger.info(f"Autenticación exitosa para usuario: {username}")

        # 5. Devolver modelo User público (sin contraseña)
        return User(
            id=user_in_db.id,
            username=user_in_db.username,
            email=user_in_db.email,
            full_name=user_in_db.full_name,
            disabled=user_in_db.disabled,
        )

    async def get_user_scopes(self, username: str) -> List[str]:
        """
        Obtiene los alcances (scopes) de un usuario (cache-first)

        Args:
            username: Nombre de usuario

        Returns:
            Lista de alcances
        """
        # Intentar obtener del cache
        user_id = self.redis_repo.hash_get("usernames", username)
        if user_id:
            user_in_db = self.redis_repo.get(f"user:{user_id}")
            if user_in_db:
                return user_in_db.scopes

        # Fallback a PostgreSQL
        with get_db_context() as db:
            user_repo = UserAuthRepository(db)
            user_db = user_repo.get_by_username(username)

            if not user_db:
                return []

            # Cachear
            user_in_db = self._db_to_redis_model(user_db)
            self.redis_repo.set(f"user:{user_db.id}", user_in_db, expiration=USER_CACHE_TTL)
            self.redis_repo.hash_set("usernames", username, str(user_db.id))

            return user_db.scopes or []

    async def update_user_scopes(self, username: str, scopes: List[str]) -> bool:
        """
        Actualiza los alcances de un usuario (PostgreSQL + invalidar cache)

        Args:
            username: Nombre de usuario
            scopes: Lista de alcances

        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        with get_db_context() as db:
            user_repo = UserAuthRepository(db)

            # Actualizar en PostgreSQL
            user_db = user_repo.update_scopes(username, scopes)
            if not user_db:
                return False

            # Invalidar cache en Redis (se volverá a cachear en la próxima lectura)
            self.redis_repo.delete(f"user:{user_db.id}")

            logger.info(f"Scopes actualizados para usuario {username}: {scopes}")
            return True

    def _db_to_redis_model(self, user_db: UserDB) -> UserInDB:
        """
        Convierte un modelo UserDB (SQLAlchemy) a UserInDB (Pydantic para Redis)

        Args:
            user_db: Modelo SQLAlchemy de usuario

        Returns:
            UserInDB: Modelo Pydantic para almacenar en Redis
        """
        return UserInDB(
            id=str(user_db.id),
            username=user_db.username,
            email=user_db.email,
            password=user_db.password_hash,
            full_name=user_db.full_name,
            disabled=user_db.disabled,
            scopes=user_db.scopes or [],
        )
