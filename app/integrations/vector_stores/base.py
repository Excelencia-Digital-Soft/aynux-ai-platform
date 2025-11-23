"""
Base Vector Store module - Exports interfaces and factory functions

This module provides a convenient way to import vector store interfaces
and create instances without knowing implementation details.
"""

from app.core.interfaces.vector_store import (
    # Interfaces
    IVectorStore,
    IHybridSearch,
    IVectorStoreMetrics,
    IVectorStoreFactory,
    # Data classes
    Document,
    VectorSearchResult,
    # Enums
    VectorStoreType,
    # Exceptions
    VectorStoreError,
    VectorStoreConnectionError,
    VectorStoreIndexError,
    VectorStoreQueryError,
)

from .pgvector import PgVectorStore

__all__ = [
    # Interfaces
    "IVectorStore",
    "IHybridSearch",
    "IVectorStoreMetrics",
    "IVectorStoreFactory",
    # Data classes
    "Document",
    "VectorSearchResult",
    # Enums
    "VectorStoreType",
    # Exceptions
    "VectorStoreError",
    "VectorStoreConnectionError",
    "VectorStoreIndexError",
    "VectorStoreQueryError",
    # Implementations
    "PgVectorStore",
    # Factory functions
    "create_vector_store",
]


def create_vector_store(
    store_type: VectorStoreType = VectorStoreType.PGVECTOR,
    collection_name: str = "products",
    embedding_dimension: int = 768,
    **kwargs
) -> IVectorStore:
    """
    Factory function to create vector store based on type.

    Args:
        store_type: Type of vector store (PGVECTOR, CHROMA, PINECONE, etc.)
        collection_name: Name of the collection/table
        embedding_dimension: Dimension of embeddings
        **kwargs: Additional parameters specific to the store type

    Returns:
        IVectorStore instance

    Example:
        ```python
        from app.integrations.vector_stores import create_vector_store, VectorStoreType

        # Create pgvector store
        store = create_vector_store(
            store_type=VectorStoreType.PGVECTOR,
            collection_name="products",
            embedding_dimension=768
        )

        # Add documents
        docs = [Document(id="1", content="Laptop gaming")]
        await store.add_documents(docs)

        # Search
        results = await store.search("laptop", top_k=5)
        ```
    """
    if store_type == VectorStoreType.PGVECTOR:
        return PgVectorStore(
            collection_name=collection_name,
            embedding_dimension=embedding_dimension,
            **kwargs
        )
    elif store_type == VectorStoreType.CHROMA:
        # TODO: Implement ChromaDB integration
        raise NotImplementedError("ChromaDB integration not yet implemented in new architecture")
    elif store_type == VectorStoreType.PINECONE:
        # TODO: Implement Pinecone integration
        raise NotImplementedError("Pinecone integration not yet implemented")
    elif store_type == VectorStoreType.WEAVIATE:
        # TODO: Implement Weaviate integration
        raise NotImplementedError("Weaviate integration not yet implemented")
    elif store_type == VectorStoreType.FAISS:
        # TODO: Implement FAISS integration
        raise NotImplementedError("FAISS integration not yet implemented")
    else:
        raise ValueError(f"Unknown vector store type: {store_type}")


class VectorStoreFactory(IVectorStoreFactory):
    """
    Concrete implementation of IVectorStoreFactory.

    Provides a class-based factory for creating vector stores.

    Example:
        ```python
        from app.integrations.vector_stores import VectorStoreFactory, VectorStoreType

        factory = VectorStoreFactory()

        # Create stores
        pgvector = factory.create_vector_store(
            VectorStoreType.PGVECTOR,
            "products",
            config={"embedding_dimension": 768}
        )

        # Future: ChromaDB
        # chroma = factory.create_vector_store(
        #     VectorStoreType.CHROMA,
        #     "products",
        #     config={"persist_directory": "./chroma_data"}
        # )
        ```
    """

    def create_vector_store(
        self,
        store_type: VectorStoreType,
        collection_name: str,
        config: dict = None
    ) -> IVectorStore:
        """
        Create vector store instance.

        Args:
            store_type: Type of vector store
            collection_name: Collection/table name
            config: Configuration dictionary

        Returns:
            IVectorStore instance
        """
        config = config or {}
        return create_vector_store(
            store_type=store_type,
            collection_name=collection_name,
            **config
        )
