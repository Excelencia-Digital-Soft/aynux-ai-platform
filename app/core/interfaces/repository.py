"""
Interfaces base para repositorios (Data Access Layer)

Estos protocols definen contratos que deben implementar todos los repositorios
del sistema, siguiendo el patrón Repository y Dependency Inversion Principle.
"""

from abc import abstractmethod
from typing import Generic, List, Optional, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")  # Entity type
ID = TypeVar("ID")  # ID type (int, str, UUID, etc.)


@runtime_checkable
class IRepository(Protocol, Generic[T, ID]):
    """
    Interface base para todos los repositorios.

    Implementa el patrón Repository para abstraer el acceso a datos.
    Las implementaciones concretas pueden usar SQLAlchemy, MongoDB, Redis, etc.

    Type Parameters:
        T: Tipo de entidad que maneja el repositorio
        ID: Tipo de identificador de la entidad

    Example:
        ```python
        class ProductRepository(IRepository[Product, int]):
            async def find_by_id(self, id: int) -> Optional[Product]:
                # Implementation using SQLAlchemy
                ...
        ```
    """

    @abstractmethod
    async def find_by_id(self, id: ID) -> Optional[T]:
        """
        Encuentra una entidad por su ID.

        Args:
            id: Identificador único de la entidad

        Returns:
            Entidad encontrada o None si no existe
        """
        ...

    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Obtiene todas las entidades con paginación.

        Args:
            skip: Número de registros a saltar
            limit: Número máximo de registros a retornar

        Returns:
            Lista de entidades
        """
        ...

    @abstractmethod
    async def save(self, entity: T) -> T:
        """
        Persiste una entidad (create o update).

        Args:
            entity: Entidad a guardar

        Returns:
            Entidad guardada (puede incluir campos generados como ID, timestamps)
        """
        ...

    @abstractmethod
    async def delete(self, id: ID) -> bool:
        """
        Elimina una entidad por su ID.

        Args:
            id: Identificador de la entidad a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        ...

    @abstractmethod
    async def exists(self, id: ID) -> bool:
        """
        Verifica si existe una entidad con el ID dado.

        Args:
            id: Identificador a verificar

        Returns:
            True si existe, False en caso contrario
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """
        Cuenta el número total de entidades.

        Returns:
            Número total de registros
        """
        ...


@runtime_checkable
class IReadOnlyRepository(Protocol, Generic[T, ID]):
    """
    Interface para repositorios de solo lectura.

    Útil para vistas, reportes, o cuando no se permite modificar datos.
    """

    @abstractmethod
    async def find_by_id(self, id: ID) -> Optional[T]:
        """Encuentra entidad por ID"""
        ...

    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Obtiene todas las entidades"""
        ...

    @abstractmethod
    async def exists(self, id: ID) -> bool:
        """Verifica existencia"""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Cuenta entidades"""
        ...


@runtime_checkable
class ISearchableRepository(Protocol, Generic[T]):
    """
    Interface para repositorios con capacidad de búsqueda.

    Extiende IRepository agregando métodos de búsqueda y filtrado.
    """

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[T]:
        """
        Búsqueda de texto completo.

        Args:
            query: Texto a buscar
            limit: Número máximo de resultados

        Returns:
            Lista de entidades que coinciden con la búsqueda
        """
        ...

    @abstractmethod
    async def filter_by(self, **kwargs) -> List[T]:
        """
        Filtra entidades por criterios específicos.

        Args:
            **kwargs: Pares clave-valor para filtrar

        Returns:
            Lista de entidades que cumplen los criterios

        Example:
            ```python
            products = await repo.filter_by(category="laptop", price_max=1000)
            ```
        """
        ...


@runtime_checkable
class IKnowledgeRepository(Protocol):
    """
    Interface especializada para repositorios de knowledge base.

    Maneja documentos, embeddings y búsqueda semántica.
    """

    @abstractmethod
    async def add_documents(
        self, documents: List[str], metadatas: Optional[List[dict]] = None, ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Agrega documentos a la knowledge base.

        Args:
            documents: Lista de textos a agregar
            metadatas: Metadatos opcionales por documento
            ids: IDs opcionales (se generan automáticamente si no se proveen)

        Returns:
            Lista de IDs de los documentos agregados
        """
        ...

    @abstractmethod
    async def search_semantic(self, query: str, top_k: int = 5, filter_metadata: Optional[dict] = None) -> List[dict]:
        """
        Búsqueda semántica usando embeddings.

        Args:
            query: Texto de búsqueda
            top_k: Número de resultados a retornar
            filter_metadata: Filtros adicionales por metadata

        Returns:
            Lista de documentos con scores de similitud
        """
        ...

    @abstractmethod
    async def update_embeddings(self, document_ids: List[str]) -> bool:
        """
        Actualiza embeddings de documentos específicos.

        Args:
            document_ids: IDs de documentos a actualizar

        Returns:
            True si se actualizó exitosamente
        """
        ...

    @abstractmethod
    async def delete_collection(self) -> bool:
        """
        Elimina toda la colección de documentos.

        Returns:
            True si se eliminó exitosamente
        """
        ...


@runtime_checkable
class ICacheRepository(Protocol, Generic[T]):
    """
    Interface para repositorios con caching.

    Combina acceso a datos persistentes con cache (ej. Redis).
    """

    @abstractmethod
    async def get_cached(self, key: str) -> Optional[T]:
        """
        Obtiene valor del cache.

        Args:
            key: Clave de cache

        Returns:
            Valor cacheado o None si no existe/expiró
        """
        ...

    @abstractmethod
    async def set_cached(self, key: str, value: T, ttl: int = 3600) -> None:
        """
        Guarda valor en cache.

        Args:
            key: Clave de cache
            value: Valor a cachear
            ttl: Time-to-live en segundos
        """
        ...

    @abstractmethod
    async def invalidate_cache(self, key: str) -> None:
        """
        Invalida entrada de cache.

        Args:
            key: Clave a invalidar
        """
        ...

    @abstractmethod
    async def get_or_fetch(self, key: str, fetch_fn: callable, ttl: int = 3600) -> T:
        """
        Obtiene del cache o ejecuta función de fetch si no existe.

        Args:
            key: Clave de cache
            fetch_fn: Función async para obtener el valor si no está en cache
            ttl: Time-to-live en segundos

        Returns:
            Valor del cache o del fetch
        """
        ...
