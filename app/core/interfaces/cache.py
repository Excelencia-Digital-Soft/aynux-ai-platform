"""
Interfaces para sistemas de caché

Define contratos para almacenamiento en caché (Redis, Memcached, in-memory, etc.)
"""

from typing import Protocol, Optional, Any, List, Set, Dict, runtime_checkable, Callable
from abc import abstractmethod
from enum import Enum
from dataclasses import dataclass
from datetime import timedelta


class CacheBackend(str, Enum):
    """Backends de caché soportados"""

    REDIS = "redis"
    MEMCACHED = "memcached"
    IN_MEMORY = "in_memory"
    MULTI_LAYER = "multi_layer"  # Cache en capas (memory + redis)


@dataclass
class CacheEntry:
    """Entrada de caché con metadata"""

    key: str
    value: Any
    ttl: Optional[int] = None  # Seconds
    created_at: Optional[float] = None
    hits: int = 0


@runtime_checkable
class ICache(Protocol):
    """
    Interface base para sistemas de caché.

    Abstrae operaciones de caché permitiendo cambiar backend sin modificar código.

    Example:
        ```python
        class RedisCache(ICache):
            async def get(self, key: str) -> Optional[Any]:
                return await self.redis_client.get(key)
        ```
    """

    @property
    @abstractmethod
    def backend(self) -> CacheBackend:
        """Tipo de backend de caché"""
        ...

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Obtiene valor del caché.

        Args:
            key: Clave a buscar

        Returns:
            Valor cacheado o None si no existe/expiró

        Example:
            ```python
            product = await cache.get("product:123")
            if product is None:
                product = await db.get_product(123)
                await cache.set("product:123", product, ttl=3600)
            ```
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Guarda valor en caché.

        Args:
            key: Clave
            value: Valor a cachear (debe ser serializable)
            ttl: Time-to-live en segundos (None = sin expiración)

        Returns:
            True si se guardó exitosamente

        Example:
            ```python
            await cache.set("user:456", user_data, ttl=1800)  # 30 minutos
            ```
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Elimina entrada de caché.

        Args:
            key: Clave a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Verifica si existe una clave.

        Args:
            key: Clave a verificar

        Returns:
            True si existe, False en caso contrario
        """
        ...

    @abstractmethod
    async def clear(self) -> bool:
        """
        Limpia todo el caché.

        Returns:
            True si se limpió exitosamente
        """
        ...

    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Obtiene tiempo de vida restante.

        Args:
            key: Clave

        Returns:
            Segundos restantes o None si no existe/sin expiración
        """
        ...

    @abstractmethod
    async def set_ttl(self, key: str, ttl: int) -> bool:
        """
        Actualiza tiempo de vida.

        Args:
            key: Clave
            ttl: Nuevo TTL en segundos

        Returns:
            True si se actualizó exitosamente
        """
        ...


@runtime_checkable
class IAdvancedCache(Protocol):
    """
    Interface extendida con operaciones avanzadas de caché.
    """

    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Obtiene múltiples valores en una sola operación.

        Args:
            keys: Lista de claves

        Returns:
            Diccionario {key: value} (solo claves que existen)

        Example:
            ```python
            products = await cache.get_many(["product:1", "product:2", "product:3"])
            # products = {"product:1": {...}, "product:2": {...}}  # product:3 no existe
            ```
        """
        ...

    @abstractmethod
    async def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """
        Guarda múltiples valores en una sola operación.

        Args:
            items: Diccionario {key: value}
            ttl: TTL para todas las claves

        Returns:
            Número de items guardados

        Example:
            ```python
            await cache.set_many({
                "product:1": product1,
                "product:2": product2
            }, ttl=3600)
            ```
        """
        ...

    @abstractmethod
    async def delete_many(self, keys: List[str]) -> int:
        """
        Elimina múltiples claves.

        Args:
            keys: Lista de claves a eliminar

        Returns:
            Número de claves eliminadas
        """
        ...

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Incrementa valor numérico.

        Args:
            key: Clave
            amount: Cantidad a incrementar

        Returns:
            Nuevo valor

        Example:
            ```python
            # Rate limiting
            requests = await cache.increment("api:requests:user:123")
            if requests > 100:
                raise RateLimitError()
            ```
        """
        ...

    @abstractmethod
    async def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrementa valor numérico.

        Args:
            key: Clave
            amount: Cantidad a decrementar

        Returns:
            Nuevo valor
        """
        ...


@runtime_checkable
class IPatternCache(Protocol):
    """
    Interface para operaciones con patrones de claves.
    """

    @abstractmethod
    async def get_keys(self, pattern: str) -> List[str]:
        """
        Obtiene claves que coinciden con patrón.

        Args:
            pattern: Patrón de búsqueda (ej. "product:*", "user:*:session")

        Returns:
            Lista de claves que coinciden

        Example:
            ```python
            # Obtener todas las claves de productos
            product_keys = await cache.get_keys("product:*")
            # ["product:1", "product:2", "product:3", ...]
            ```
        """
        ...

    @abstractmethod
    async def delete_pattern(self, pattern: str) -> int:
        """
        Elimina todas las claves que coinciden con patrón.

        Args:
            pattern: Patrón de búsqueda

        Returns:
            Número de claves eliminadas

        Example:
            ```python
            # Invalidar todos los cachés de productos
            deleted = await cache.delete_pattern("product:*")
            ```
        """
        ...


@runtime_checkable
class ICacheWithCallback(Protocol):
    """
    Interface para caché con función de recuperación automática.
    """

    @abstractmethod
    async def get_or_set(self, key: str, fetch_fn: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        Obtiene del caché o ejecuta función si no existe.

        Pattern "Cache-Aside" implementado.

        Args:
            key: Clave de caché
            fetch_fn: Función async para obtener valor si no está en caché
            ttl: TTL en segundos

        Returns:
            Valor del caché o del fetch

        Example:
            ```python
            async def fetch_product():
                return await db.get_product(123)

            product = await cache.get_or_set(
                "product:123",
                fetch_fn=fetch_product,
                ttl=3600
            )
            ```
        """
        ...

    @abstractmethod
    async def remember(self, key: str, fetch_fn: Callable[[], Any], ttl: int = 3600) -> Any:
        """
        Alias de get_or_set con TTL obligatorio.

        Args:
            key: Clave
            fetch_fn: Función de recuperación
            ttl: TTL en segundos (obligatorio)

        Returns:
            Valor cacheado o recuperado
        """
        ...


@runtime_checkable
class IMultiLayerCache(Protocol):
    """
    Interface para caché en múltiples capas.

    Combina caché en memoria (rápido) con caché distribuido (compartido).
    """

    @abstractmethod
    async def get_with_fallback(self, key: str, layers: List[str] = ["memory", "redis"]) -> Optional[Any]:
        """
        Obtiene valor probando múltiples capas.

        Args:
            key: Clave
            layers: Orden de capas a probar

        Returns:
            Valor de la primera capa que lo tenga

        Example:
            ```python
            # Primero intenta memory cache, luego Redis
            value = await cache.get_with_fallback("product:123")
            ```
        """
        ...

    @abstractmethod
    async def set_multi_layer(self, key: str, value: Any, memory_ttl: int = 60, redis_ttl: int = 3600) -> bool:
        """
        Guarda en múltiples capas con TTLs diferentes.

        Args:
            key: Clave
            value: Valor
            memory_ttl: TTL para caché en memoria (corto)
            redis_ttl: TTL para Redis (largo)

        Returns:
            True si se guardó en al menos una capa
        """
        ...

    @abstractmethod
    async def invalidate_all_layers(self, key: str) -> int:
        """
        Invalida entrada en todas las capas.

        Args:
            key: Clave a invalidar

        Returns:
            Número de capas donde se invalidó
        """
        ...


@runtime_checkable
class ICacheMetrics(Protocol):
    """
    Interface para métricas de caché.
    """

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del caché.

        Returns:
            Diccionario con métricas (hits, misses, evictions, memory_usage, etc.)

        Example:
            ```python
            stats = await cache.get_stats()
            # {
            #     "hits": 1523,
            #     "misses": 87,
            #     "hit_rate": 0.946,
            #     "memory_usage_mb": 45.2,
            #     "keys_count": 1250
            # }
            ```
        """
        ...

    @abstractmethod
    async def reset_stats(self) -> bool:
        """Resetea estadísticas"""
        ...


# Excepciones
class CacheError(Exception):
    """Error base para caché"""

    pass


class CacheConnectionError(CacheError):
    """Error de conexión con backend"""

    pass


class CacheSerializationError(CacheError):
    """Error serializando/deserializando valor"""

    pass


class CacheKeyError(CacheError):
    """Error con formato de clave"""

    pass
