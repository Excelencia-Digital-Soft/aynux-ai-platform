"""
Repository for user authentication operations with PostgreSQL
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.db.user import UserDB

logger = logging.getLogger(__name__)


class UserAuthRepository:
    """
    Repositorio para operaciones CRUD de usuarios de autenticación

    Attributes:
        db: Sesión de SQLAlchemy (sincrónica o asincrónica)
    """

    def __init__(self, db: Session):
        """
        Inicializa el repositorio con la sesión de base de datos

        Args:
            db: Sesión de SQLAlchemy
        """
        self.db = db

    def create_user(self, username: str, email: str, password_hash: str, full_name: str = None) -> UserDB:
        """
        Crea un nuevo usuario en la base de datos

        Args:
            username: Nombre de usuario único
            email: Email único del usuario
            password_hash: Hash bcrypt de la contraseña
            full_name: Nombre completo del usuario (opcional)

        Returns:
            UserDB: Usuario creado

        Raises:
            Exception: Si el usuario ya existe o hay un error de base de datos
        """
        try:
            user = UserDB(
                id=uuid.uuid4(),
                username=username,
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                disabled=False,
                scopes=[],
            )

            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            logger.info(f"Usuario creado exitosamente: {username} (ID: {user.id})")
            return user

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al crear usuario {username}: {str(e)}")
            raise

    def get_by_username(self, username: str) -> Optional[UserDB]:
        """
        Obtiene un usuario por su nombre de usuario

        Args:
            username: Nombre de usuario a buscar

        Returns:
            UserDB o None si no existe
        """
        try:
            user = self.db.query(UserDB).filter(UserDB.username == username).first()
            return user
        except Exception as e:
            logger.error(f"Error al obtener usuario por username {username}: {str(e)}")
            return None

    def get_by_email(self, email: str) -> Optional[UserDB]:
        """
        Obtiene un usuario por su email

        Args:
            email: Email a buscar

        Returns:
            UserDB o None si no existe
        """
        try:
            user = self.db.query(UserDB).filter(UserDB.email == email).first()
            return user
        except Exception as e:
            logger.error(f"Error al obtener usuario por email {email}: {str(e)}")
            return None

    def get_by_id(self, user_id: uuid.UUID) -> Optional[UserDB]:
        """
        Obtiene un usuario por su ID

        Args:
            user_id: UUID del usuario

        Returns:
            UserDB o None si no existe
        """
        try:
            user = self.db.query(UserDB).filter(UserDB.id == user_id).first()
            return user
        except Exception as e:
            logger.error(f"Error al obtener usuario por ID {user_id}: {str(e)}")
            return None

    def update_scopes(self, username: str, scopes: List[str]) -> Optional[UserDB]:
        """
        Actualiza los scopes (permisos) de un usuario

        Args:
            username: Nombre de usuario
            scopes: Nueva lista de permisos

        Returns:
            UserDB actualizado o None si no existe
        """
        try:
            user = self.get_by_username(username)
            if user:
                user.scopes = scopes  # type: ignore[assignment]
                self.db.commit()
                self.db.refresh(user)
                logger.info(f"Scopes actualizados para usuario {username}: {scopes}")
                return user
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al actualizar scopes de usuario {username}: {str(e)}")
            return None

    def update_user(
        self,
        username: str,
        email: str = None,
        full_name: str = None,
        disabled: bool = None,
    ) -> Optional[UserDB]:
        """
        Actualiza información del usuario

        Args:
            username: Nombre de usuario
            email: Nuevo email (opcional)
            full_name: Nuevo nombre completo (opcional)
            disabled: Nuevo estado de habilitación (opcional)

        Returns:
            UserDB actualizado o None si no existe
        """
        try:
            user = self.get_by_username(username)
            if not user:
                return None

            if email is not None:
                user.email = email  # type: ignore[assignment]
            if full_name is not None:
                user.full_name = full_name  # type: ignore[assignment]
            if disabled is not None:
                user.disabled = disabled  # type: ignore[assignment]

            self.db.commit()
            self.db.refresh(user)
            logger.info(f"Usuario actualizado: {username}")
            return user

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al actualizar usuario {username}: {str(e)}")
            return None

    def delete_user(self, username: str) -> bool:
        """
        Elimina un usuario de la base de datos

        Args:
            username: Nombre de usuario a eliminar

        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        try:
            user = self.get_by_username(username)
            if user:
                self.db.delete(user)
                self.db.commit()
                logger.info(f"Usuario eliminado: {username}")
                return True
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al eliminar usuario {username}: {str(e)}")
            return False

    def list_users(self, limit: int = 100, offset: int = 0) -> List[UserDB]:
        """
        Lista usuarios con paginación

        Args:
            limit: Número máximo de usuarios a devolver
            offset: Desplazamiento para paginación

        Returns:
            Lista de usuarios
        """
        try:
            users = self.db.query(UserDB).offset(offset).limit(limit).all()
            return users
        except Exception as e:
            logger.error(f"Error al listar usuarios: {str(e)}")
            return []

    def user_exists(self, username: str) -> bool:
        """
        Verifica si un usuario existe

        Args:
            username: Nombre de usuario a verificar

        Returns:
            True si existe, False en caso contrario
        """
        user = self.get_by_username(username)
        return user is not None

    def email_exists(self, email: str) -> bool:
        """
        Verifica si un email ya está registrado

        Args:
            email: Email a verificar

        Returns:
            True si existe, False en caso contrario
        """
        user = self.get_by_email(email)
        return user is not None
