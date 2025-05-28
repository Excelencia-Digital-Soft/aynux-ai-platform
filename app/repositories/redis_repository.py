import json
import logging
import time
from typing import Any, Dict, Generic, Optional, Type, TypeVar

import redis
from pydantic import BaseModel
from redis.exceptions import ConnectionError, TimeoutError

from app.config.settings import get_settings
from app.repositories.dummy_redis_client import DummyRedisClient

logger = logging.getLogger(__name__)


T = TypeVar("T", bound=BaseModel)


class RedisRepository(Generic[T]):
    """
    Repositorio genérico para acceder a Redis.
    """

    def __init__(self, model_class: Type[T], prefix: str = ""):
        self.settings = get_settings()
        self.model_class = model_class
        self.prefix = prefix
        self.redis_client = None
        self.connect_to_redis()

    def connect_to_redis(self, max_retries=3, retry_delay=1):
        """Inicializa la conexión a Redis con reintentos"""
        retries = 0
        last_error = None

        while retries < max_retries:
            try:
                self.redis_client = redis.Redis(
                    host=self.settings.REDIS_HOST,
                    port=self.settings.REDIS_PORT,
                    db=self.settings.REDIS_DB,
                    password=self.settings.REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                # Verificamos que la conexión funciona
                self.redis_client.ping()
                logger.info(
                    f"Conexión a Redis establecida correctamente:{self.settings.REDIS_HOST}:{self.settings.REDIS_PORT}"
                )
                return
            except (ConnectionError, TimeoutError) as e:
                retries += 1
                last_error = e
                logger.warning(f"Intento {retries}/{max_retries} de conexión a Redis fallido: {e}")
                if retries < max_retries:
                    time.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Error inesperado al conectar a Redis: {e}")
                last_error = e
                break

        logger.error(f"No se pudo establecer conexión con Redisdespués de {max_retries} intentos: {last_error}")
        # Configurar un cliente dummy que maneje las operaciones sin fallar
        self.redis_client = DummyRedisClient()

    def _get_key(self, key: str) -> str:
        """Construye la clave completa con prefijo"""
        return f"{self.prefix}:{key}" if self.prefix else key

    def get(self, key: str) -> Optional[T]:
        """Obtiene un objeto por su clave"""
        try:
            redis_key = self._get_key(key)
            data = self.redis_client.get(redis_key)

            if data is None:
                logger.debug(f"No se encontró la clave {redis_key} en Redis")
                return None

            logger.debug(
                "Datos recuperados de Redis:"
                f"tipo={type(data)}, longitud="
                f"{(len(data) if isinstance(data, (str, bytes)) else 'n/a')}"
            )

            if isinstance(data, bytes):
                # Si es bytes, decodificar a string
                data = data.decode("utf-8")
                logger.debug(f"Datos decodificados de bytes a string: {data[:100]}...")

            if not data:
                return None

            # Para depuración, imprimir parte de los datos (evitar datos muy largos)
            truncated_data = data[:100] + "..." if isinstance(data, str) and len(data) > 100 else data
            logger.debug(f"Deserializando datos: {truncated_data}")

            # Si el modelo esperado es un diccionario
            if self.model_class is dict:
                result = json.loads(data)  # type: ignore
                logger.debug("Datos deserializados a dict")
                return result

            # Si es un modelo Pydantic
            try:
                # Primero convertir a diccionario si es un string JSON
                if isinstance(data, str):
                    data_dict = json.loads(data)
                    result = self.model_class.model_validate(data_dict)
                    logger.debug(f"Datos deserializados a {self.model_class.__name__}")
                    return result
                else:
                    # Si ya es un diccionario
                    result = self.model_class.model_validate(data)
                    logger.debug(f"Datos deserializados directamente a{self.model_class.__name__}")
                    return result
            except Exception as pydantic_error:
                logger.error(f"Error al validar datos para {self.model_class.__name__}: {str(pydantic_error)}")
                # Podríamos intentar una recuperación aquí si lo deseas
                return None
        except Exception as e:
            logger.error(f"Error general al obtener datos de Redis: {str(e)}")
            return None

    def set(self, key: str, value: T, expiration: Optional[int] = None) -> bool:
        """Almacena un objeto por su clave"""
        try:
            # Si es un modelo de Pydantic o un diccionario
            if hasattr(value, "model_dump") and callable(value.model_dump):
                # Pydantic v2
                serialized = json.dumps(value.model_dump(mode="json"), default=lambda dt: dt.isoformat())
            elif isinstance(value, dict):
                # Simple diccionario
                serialized = json.dumps(value, default=lambda dt: dt.isoformat())
            else:
                # Otro tipo de valor
                serialized = json.dumps(value, default=lambda dt: dt.isoformat())

            result = self.redis_client.set(self._get_key(key), serialized)
            if expiration:
                self.redis_client.expire(self._get_key(key), expiration)  # type: ignore
            return result  # type: ignore
        except Exception as e:
            logger.error(f"Error al guardar en Redis: {e}")
            return False

    def set_if_not_exists(self, key: str, value: Any, expiration: Optional[int] = None) -> bool:
        """
        Almacena un valor solo si la clave no existe (NX)

        Args:
            key: Clave a utilizar
            value: Valor a almacenar (string o serializable)
            expiration: Tiempo de expiración en segundos (opcional)

        Returns:
            True si se estableció el valor, False si la clave ya existía
        """
        # Serializar el valor si es necesario
        if isinstance(value, BaseModel):
            value = value.model_dump_json()
        elif not isinstance(value, (str, int, float, bool)):
            value = json.dumps(value)

        # Usar NX para establecer solo si no existe
        result = self.redis_client.set(self._get_key(key), value, ex=expiration, nx=True)

        return bool(result)

    def delete(self, key: str) -> bool:
        """Elimina un objeto por su clave"""
        return bool(self.redis_client.delete(self._get_key(key)))

    def exists(self, key: str) -> bool:
        """Verifica si existe una clave"""
        return bool(self.redis_client.exists(self._get_key(key)))

    def hash_set(self, key: str, field: str, value: Any, expiration: Optional[int] = None) -> bool:
        """Almacena un campo en un hash"""
        if isinstance(value, BaseModel):
            value = value.model_dump_json()
        elif not isinstance(value, (str, int, float, bool)):
            value = json.dumps(value)

        result = self.redis_client.hset(self._get_key(key), field, value)  # type: ignore
        if expiration:
            self.redis_client.expire(self._get_key(key), expiration)  # type: ignore
        return bool(result)

    def hash_get(self, key: str, field: str) -> Any:
        """Obtiene un campo de un hash"""
        value = self.redis_client.hget(self._get_key(key), field)
        if value:
            try:
                # Intentar deserializar como JSON
                return json.loads(value)  # type: ignore
            except json.JSONDecodeError:
                # Si no es JSON, devolver el valor tal cual
                return value
        return None

    def hash_get_all(self, key: str) -> Dict[str, Any]:
        """Obtiene todos los campos de un hash"""
        data = self.redis_client.hgetall(self._get_key(key))
        result = {}

        for k, v in data.items():  # type: ignore
            try:
                # Intentar deserializar como JSON
                result[k] = json.loads(v)
            except json.JSONDecodeError:
                # Si no es JSON, devolver el valor tal cual
                result[k] = v

        return result

    def hash_delete(self, key: str, field: str) -> bool:
        """Elimina un campo de un hash"""
        return bool(self.redis_client.hdel(self._get_key(key), field))
