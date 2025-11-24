"""
Interfaces para Vector Stores

Define contratos para almacenamiento y búsqueda de embeddings vectoriales.
"""

from typing import Protocol, List, Dict, Any, Optional, Tuple, runtime_checkable
from abc import abstractmethod
from enum import Enum
from dataclasses import dataclass


class VectorStoreType(str, Enum):
    """Tipos de vector stores soportados"""

    PGVECTOR = "pgvector"  # PostgreSQL con extensión pgvector
    CHROMA = "chroma"  # ChromaDB (legacy)
    PINECONE = "pinecone"  # Pinecone cloud
    WEAVIATE = "weaviate"  # Weaviate
    FAISS = "faiss"  # Facebook AI Similarity Search


@dataclass
class Document:
    """
    Documento con embedding vectorial.

    Representa un documento almacenado en el vector store.
    """

    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    score: Optional[float] = None  # Similarity score (para resultados de búsqueda)


@dataclass
class VectorSearchResult:
    """
    Resultado de búsqueda vectorial.

    Incluye documento y score de similitud.
    """

    document: Document
    score: float  # Similarity score (0.0 a 1.0, mayor es más similar)
    distance: float  # Distance metric (depende del vector store)


@runtime_checkable
class IVectorStore(Protocol):
    """
    Interface base para vector stores.

    Abstrae almacenamiento y búsqueda de embeddings vectoriales.
    Permite cambiar de vector store sin modificar código de negocio.

    Example:
        ```python
        class PgVectorStore(IVectorStore):
            async def add_documents(self, documents: List[Document]) -> List[str]:
                # Implementación usando PostgreSQL + pgvector
                ...
        ```
    """

    @property
    @abstractmethod
    def store_type(self) -> VectorStoreType:
        """Tipo de vector store"""
        ...

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """Nombre de la colección/tabla actual"""
        ...

    @abstractmethod
    async def add_documents(self, documents: List[Document], generate_embeddings: bool = True) -> List[str]:
        """
        Agrega documentos al vector store.

        Args:
            documents: Lista de documentos a agregar
            generate_embeddings: Si True, genera embeddings automáticamente

        Returns:
            Lista de IDs de los documentos agregados

        Example:
            ```python
            docs = [
                Document(id="1", content="Laptop gaming HP"),
                Document(id="2", content="Mouse inalámbrico Logitech")
            ]
            ids = await store.add_documents(docs)
            ```
        """
        ...

    @abstractmethod
    async def search(
        self, query: str, top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None, min_score: float = 0.0
    ) -> List[VectorSearchResult]:
        """
        Búsqueda semántica por similitud.

        Args:
            query: Texto de búsqueda
            top_k: Número de resultados a retornar
            filter_metadata: Filtros adicionales por metadata
            min_score: Score mínimo de similitud (0.0 a 1.0)

        Returns:
            Lista de resultados ordenados por similitud (más similar primero)

        Example:
            ```python
            results = await store.search(
                "laptop gaming económica",
                top_k=5,
                filter_metadata={"category": "electronics", "price_max": 1000}
            )

            for result in results:
                print(f"{result.document.content} (score: {result.score})")
            ```
        """
        ...

    @abstractmethod
    async def search_by_vector(
        self, embedding: List[float], top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[VectorSearchResult]:
        """
        Búsqueda usando embedding directamente (sin generar).

        Args:
            embedding: Vector de búsqueda
            top_k: Número de resultados
            filter_metadata: Filtros por metadata

        Returns:
            Lista de resultados ordenados por similitud
        """
        ...

    @abstractmethod
    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """
        Obtiene documento por ID.

        Args:
            document_id: ID del documento

        Returns:
            Documento o None si no existe
        """
        ...

    @abstractmethod
    async def delete(self, document_ids: List[str]) -> int:
        """
        Elimina documentos por IDs.

        Args:
            document_ids: Lista de IDs a eliminar

        Returns:
            Número de documentos eliminados
        """
        ...

    @abstractmethod
    async def update_document(
        self,
        document_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        regenerate_embedding: bool = True,
    ) -> bool:
        """
        Actualiza un documento existente.

        Args:
            document_id: ID del documento
            content: Nuevo contenido (opcional)
            metadata: Nueva metadata (opcional)
            regenerate_embedding: Si True, regenera embedding

        Returns:
            True si se actualizó exitosamente
        """
        ...

    @abstractmethod
    async def create_collection(self, collection_name: str, embedding_dimension: int = 1024) -> bool:
        """
        Crea una nueva colección.

        Args:
            collection_name: Nombre de la colección
            embedding_dimension: Dimensión de los embeddings

        Returns:
            True si se creó exitosamente
        """
        ...

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Elimina una colección completa.

        Args:
            collection_name: Nombre de la colección a eliminar

        Returns:
            True si se eliminó exitosamente
        """
        ...

    @abstractmethod
    async def count_documents(self, filter_metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Cuenta documentos en la colección.

        Args:
            filter_metadata: Filtros opcionales

        Returns:
            Número de documentos
        """
        ...


@runtime_checkable
class IHybridSearch(Protocol):
    """
    Interface para búsqueda híbrida (vectorial + keyword).

    Combina búsqueda semántica con búsqueda tradicional de keywords.
    """

    @abstractmethod
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """
        Búsqueda híbrida combinando vectores y keywords.

        Args:
            query: Texto de búsqueda
            top_k: Número de resultados
            vector_weight: Peso de búsqueda vectorial (0.0 a 1.0)
            keyword_weight: Peso de búsqueda por keywords (0.0 a 1.0)
            filter_metadata: Filtros adicionales

        Returns:
            Lista de resultados combinados

        Example:
            ```python
            # Búsqueda que combina similitud semántica con match exacto de keywords
            results = await store.hybrid_search(
                "laptop gaming HP",
                vector_weight=0.7,  # 70% similitud semántica
                keyword_weight=0.3   # 30% match de keywords
            )
            ```
        """
        ...


@runtime_checkable
class IVectorStoreMetrics(Protocol):
    """
    Interface para métricas de vector store.

    Permite monitorear rendimiento y estadísticas.
    """

    @abstractmethod
    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del índice vectorial.

        Returns:
            Diccionario con métricas (size, count, avg_query_time, etc.)
        """
        ...

    @abstractmethod
    async def get_search_performance(self, query: str, top_k: int = 5) -> Tuple[List[VectorSearchResult], float]:
        """
        Ejecuta búsqueda y mide tiempo de ejecución.

        Args:
            query: Texto de búsqueda
            top_k: Número de resultados

        Returns:
            Tupla (resultados, tiempo_ms)
        """
        ...


@runtime_checkable
class IVectorStoreFactory(Protocol):
    """
    Interface para factory de vector stores.
    """

    @abstractmethod
    def create_vector_store(
        self, store_type: VectorStoreType, collection_name: str, config: Optional[Dict[str, Any]] = None
    ) -> IVectorStore:
        """
        Crea instance de vector store.

        Args:
            store_type: Tipo de vector store
            collection_name: Nombre de la colección
            config: Configuración adicional

        Returns:
            Instancia de IVectorStore

        Example:
            ```python
            factory = VectorStoreFactory()

            # pgvector
            pgvector = factory.create_vector_store(
                VectorStoreType.PGVECTOR,
                "products",
                config={"db_url": "postgresql://..."}
            )

            # ChromaDB
            chroma = factory.create_vector_store(
                VectorStoreType.CHROMA,
                "products",
                config={"persist_directory": "./chroma_data"}
            )
            ```
        """
        ...


# Excepciones
class VectorStoreError(Exception):
    """Error base para vector stores"""

    pass


class VectorStoreConnectionError(VectorStoreError):
    """Error de conexión"""

    pass


class VectorStoreIndexError(VectorStoreError):
    """Error con el índice vectorial"""

    pass


class VectorStoreQueryError(VectorStoreError):
    """Error durante búsqueda"""

    pass
