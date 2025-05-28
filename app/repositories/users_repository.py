import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.models.session import UserSession
from app.models.user import User, UserState
from app.repositories.redis_repository import RedisRepository

# Definición del tiempo de expiración de sesión (1 hora)
SESSION_EXPIRATION = 3600


class CiudadanoRepository:
    """
    Repositorio para gestionar usuarios en Redis
    """

    def __init__(self):
        self.redis_repo = RedisRepository[User](User, prefix="user")
        self.session_repo = RedisRepository[UserSession](UserSession, prefix="session")
        self.logger = logging.getLogger(__name__)

    def get_user(self, phone_number: str) -> Optional[User]:
        """
        Obtiene un usuario por su número de teléfono
        """
        try:
            user = self.redis_repo.get(phone_number)
            if user and isinstance(user, User):
                return user
            return None
        except Exception as e:
            self.logger.error(f"Error al obtener usuario {phone_number}: {str(e)}")
            return None

    def create_user(self, phone_number: str, id_ciudadano: Optional[str] = None) -> User:
        """
        Crea un nuevo usuario
        """
        try:
            user = User(
                phone_number=phone_number,
                state=UserState(
                    state="inicio",
                    verificado=False,
                    id_ciudadano=id_ciudadano or "",
                    last_interaction=datetime.now(),
                ),
            )
            success = self.redis_repo.set(phone_number, user, expiration=SESSION_EXPIRATION)
            if not success:
                self.logger.warning(f"No se pudo guardar el usuario {phone_number} en Redis")
            return user
        except Exception as e:
            self.logger.error(f"Error al crear usuario {phone_number}: {str(e)}")
            # Retornamos un usuario de todas formas para evitar errores en el flujo
            return User(phone_number=phone_number)

    def update_user_state(self, phone_number: str, state: str) -> bool:
        """
        Actualiza el estado de un usuario
        """
        try:
            user = self.get_user(phone_number)
            if user:
                user.state.state = state  # type: ignore
                user.state.last_interaction = datetime.now()
                return self.redis_repo.set(phone_number, user, expiration=SESSION_EXPIRATION)
            return False
        except Exception as e:
            self.logger.error(f"Error al actualizar estado del usuario {phone_number}: {str(e)}")
            return False

    def update_user(
        self,
        phone_number: str,
        state: str,
        verificado: bool,
        id_ciudadano: Optional[str] = None,
    ) -> bool:
        """
        Actualiza un usuario con nuevos valores
        """
        try:
            user = self.get_user(phone_number)
            if user:
                user.state.state = state  # type: ignore
                user.state.verificado = verificado
                if id_ciudadano:
                    user.state.id_ciudadano = id_ciudadano
                user.state.last_interaction = datetime.now()
                return self.redis_repo.set(phone_number, user, expiration=SESSION_EXPIRATION)
            return False
        except Exception as e:
            self.logger.error(f"Error al actualizar usuario {phone_number}: {str(e)}")
            return False

    def delete_user(self, phone_number: str) -> bool:
        """
        Elimina un usuario
        """
        try:
            return self.redis_repo.delete(phone_number)
        except Exception as e:
            self.logger.error(f"Error al eliminar usuario {phone_number}: {str(e)}")
            return False

    # Métodos para manejar la sesión del usuario (datos temporales adicionales)
    #
    def _get_or_create_session(self, phone_number: str) -> UserSession:
        """
        Obtiene la sesión existente o crea una nueva
        """
        session = self.session_repo.get(phone_number)
        if not session:
            session = UserSession(user_id=phone_number)
            self.session_repo.set(phone_number, session, expiration=SESSION_EXPIRATION)
        return session

    def set_user_session(self, phone_number: str, key: str, value: Any) -> bool:
        """
        Establece un valor en la sesión del usuario
        """
        try:
            session = self._get_or_create_session(phone_number)
            # Convertir value a un dict si no lo es
            data = value if isinstance(value, dict) else {"value": value}
            session.set_item(key, data)
            return self.session_repo.set(phone_number, session, expiration=SESSION_EXPIRATION)
        except Exception as e:
            self.logger.error(f"Error al establecer sesión para {phone_number}: {str(e)}")
            return False

    def get_user_session(self, phone_number: str) -> Dict[str, Any]:
        """
        Obtiene todos los datos de sesión de un usuario
        """
        try:
            session = self.session_repo.get(phone_number)
            if not session:
                return {}

            # Convertir sesión a diccionario simplificado
            result = {}
            for key, item in session.items.items():
                result[key] = item.data

            return result
        except Exception as e:
            self.logger.error(f"Error al obtener sesión para {phone_number}: {str(e)}")
            return {}

    def get_session_item(self, phone_number: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un elemento específico de la sesión del usuario
        """
        try:
            session = self.session_repo.get(phone_number)
            if not session:
                return None

            return session.get_item(key)
        except Exception as e:
            self.logger.error(f"Error al obtener elemento de sesión para {phone_number}: {str(e)}")
            return None

    def update_user_session(self, phone_number: str, session_key: str, new_data: Dict[str, Any]) -> bool:
        """
        Actualiza datos específicos en la sesión del usuario
        """
        try:
            session = self._get_or_create_session(phone_number)
            current_data = session.get_item(session_key) or {}

            # Asegurarse de que current_data es un diccionario
            if not isinstance(current_data, dict):
                current_data = {}

            # Crear una copia del diccionario actual
            updated_data = current_data.copy()
            # Actualizar con nuevos datos
            updated_data.update(new_data)

            # Establecer los datos actualizados
            session.set_item(session_key, updated_data)

            # Guardar la sesión
            return self.session_repo.set(phone_number, session, expiration=SESSION_EXPIRATION)
        except Exception as e:
            self.logger.error(f"Error al actualizar sesión para {phone_number}: {str(e)}")
            return False

    def delete_session_item(self, phone_number: str, key: str) -> bool:
        """
        Elimina un elemento específico de la sesión del usuario
        """
        try:
            session = self.session_repo.get(phone_number)
            if not session:
                return False

            result = session.delete_item(key)
            if result:
                # Solo guardamos si se eliminó algo
                self.session_repo.set(phone_number, session, expiration=SESSION_EXPIRATION)

            return result
        except Exception as e:
            self.logger.error(f"Error al eliminar elemento de sesión para {phone_number}: {str(e)}")
            return False

    def delete_user_session(self, phone_number: str) -> bool:
        """
        Elimina la sesión completa de un usuario
        """
        try:
            return self.session_repo.delete(phone_number)
        except Exception as e:
            self.logger.error(f"Error al eliminar sesión para {phone_number}: {str(e)}")
            return False
