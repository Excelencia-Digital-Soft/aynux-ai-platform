"""
Integración con ChromaDB para búsqueda vectorial
"""

import logging
import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class ChromaDBIntegration:
    """Gestiona la integración con ChromaDB para almacenamiento vectorial"""

    def __init__(self, persist_directory: str = None):
        self.settings = get_settings()
        self.persist_directory = persist_directory or self.settings.OLLAMA_API_CHROMADB

        # Asegurar que el directorio existe
        os.makedirs(self.persist_directory, exist_ok=True)

        # Inicializar cliente de ChromaDB
        self.client = chromadb.PersistentClient(
            path=self.persist_directory, settings=Settings(anonymized_telemetry=False, allow_reset=False)
        )

        # Inicializar integración con Ollama para embeddings
        self.ollama = OllamaIntegration()
        self.embeddings = self.ollama.get_embeddings()

        # Cache de colecciones
        self._collections_cache = {}

    def get_collection(
        self, collection_name: str, create_if_not_exists: bool = True, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Obtiene o crea una colección de ChromaDB

        Args:
            collection_name: Nombre de la colección
            create_if_not_exists: Crear si no existe
            metadata: Metadatos de la colección
        """
        if collection_name in self._collections_cache:
            return self._collections_cache[collection_name]

        try:
            # Intentar obtener colección existente
            collection = self.client.get_collection(collection_name)
            logger.debug(f"Retrieved existing collection: {collection_name}")

        except Exception:
            if create_if_not_exists:
                # Crear nueva colección
                collection_metadata = metadata or {
                    "hnsw:space": "cosine",
                    "description": f"Vector collection for {collection_name}",
                }

                collection = self.client.create_collection(name=collection_name, metadata=collection_metadata)
                logger.info(f"Created new collection: {collection_name}")
            else:
                raise ValueError(f"Collection {collection_name} does not exist")

        self._collections_cache[collection_name] = collection
        return collection

    def get_langchain_vectorstore(self, collection_name: str, create_if_not_exists: bool = True) -> Chroma:
        """
        Obtiene un vector store de LangChain conectado a ChromaDB

        Args:
            collection_name: Nombre de la colección
            create_if_not_exists: Crear si no existe
        """
        # Asegurar que la colección existe
        self.get_collection(collection_name, create_if_not_exists)

        return Chroma(
            client=self.client,
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )

    async def add_documents(
        self, collection_name: str, documents: List[Document], ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Añade documentos a una colección

        Args:
            collection_name: Nombre de la colección
            documents: Lista de documentos a añadir
            ids: IDs opcionales para los documentos
        """
        vectorstore = self.get_langchain_vectorstore(collection_name)

        if ids:
            added_ids = await vectorstore.aadd_documents(documents, ids=ids)
        else:
            added_ids = await vectorstore.aadd_documents(documents)

        logger.info(f"Added {len(documents)} documents to {collection_name}")
        return added_ids

    async def search_similar(
        self,
        collection_name: str,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_scores: bool = False,
    ) -> List[Document]:
        """
        Busca documentos similares en una colección

        Args:
            collection_name: Nombre de la colección
            query: Texto de consulta
            k: Número de resultados
            filter_dict: Filtros opcionales
            include_scores: Incluir scores de similitud
        """
        vectorstore = self.get_langchain_vectorstore(collection_name)

        if include_scores:
            results = await vectorstore.asimilarity_search_with_score(query=query, k=k, filter=filter_dict)
            return results
        else:
            results = await vectorstore.asimilarity_search(query=query, k=k, filter=filter_dict)
            return results

    async def search_by_vector(
        self, collection_name: str, embedding: List[float], k: int = 5, filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Busca documentos por vector de embedding

        Args:
            collection_name: Nombre de la colección
            embedding: Vector de embedding
            k: Número de resultados
            filter_dict: Filtros opcionales
        """
        vectorstore = self.get_langchain_vectorstore(collection_name)

        results = await vectorstore.asimilarity_search_by_vector(embedding=embedding, k=k, filter=filter_dict)

        return results

    def delete_documents(self, collection_name: str, ids: List[str]) -> bool:
        """
        Elimina documentos de una colección

        Args:
            collection_name: Nombre de la colección
            ids: IDs de documentos a eliminar
        """
        try:
            vectorstore = self.get_langchain_vectorstore(collection_name, create_if_not_exists=False)
            vectorstore.delete(ids=ids)

            logger.info(f"Deleted {len(ids)} documents from {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Error deleting documents from {collection_name}: {e}")
            return False

    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """
        Obtiene estadísticas de una colección

        Args:
            collection_name: Nombre de la colección
        """
        try:
            collection = self.get_collection(collection_name, create_if_not_exists=False)

            count = collection.count()
            metadata = collection.metadata

            return {"name": collection_name, "document_count": count, "metadata": metadata}

        except Exception as e:
            logger.error(f"Error getting stats for {collection_name}: {e}")
            return {}

    def list_collections(self) -> List[str]:
        """Lista todas las colecciones disponibles"""
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []

    def delete_collection(self, collection_name: str) -> bool:
        """
        Elimina una colección completa

        Args:
            collection_name: Nombre de la colección a eliminar
        """
        try:
            self.client.delete_collection(collection_name)

            # Limpiar cache
            if collection_name in self._collections_cache:
                del self._collections_cache[collection_name]

            logger.info(f"Deleted collection: {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Verifica el estado de ChromaDB

        Returns:
            True si ChromaDB está funcionando correctamente
        """
        try:
            # Intentar crear y usar una colección de prueba
            test_collection = "health_check_test"

            # Crear colección de prueba
            collection = self.get_collection(test_collection, create_if_not_exists=True)

            # Añadir un documento de prueba
            test_doc = Document(page_content="This is a test document", metadata={"test": True})

            vectorstore = self.get_langchain_vectorstore(test_collection)
            await vectorstore.aadd_documents([test_doc])

            # Buscar el documento
            results = await vectorstore.asimilarity_search("test document", k=1)

            # Limpiar
            self.delete_collection(test_collection)

            return len(results) > 0

        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False

    async def initialize_collections(self, collections_config: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """
        Inicializa múltiples colecciones según configuración

        Args:
            collections_config: Configuración de colecciones
                Format: {
                    "collection_name": {
                        "metadata": {...},
                        "initial_documents": [...]
                    }
                }
        """
        results = {}

        for collection_name, config in collections_config.items():
            try:
                # Crear colección
                metadata = config.get("metadata", {})
                collection = self.get_collection(collection_name, create_if_not_exists=True, metadata=metadata)

                # Añadir documentos iniciales si existen
                initial_docs = config.get("initial_documents", [])
                if initial_docs:
                    await self.add_documents(collection_name, initial_docs)

                results[collection_name] = True
                logger.info(f"Successfully initialized collection: {collection_name}")

            except Exception as e:
                logger.error(f"Failed to initialize collection {collection_name}: {e}")
                results[collection_name] = False

        return results

    def backup_collection(self, collection_name: str, backup_path: str) -> bool:
        """
        Crea backup de una colección

        Args:
            collection_name: Nombre de la colección
            backup_path: Ruta del backup
        """
        try:
            collection = self.get_collection(collection_name, create_if_not_exists=False)

            # Obtener todos los documentos
            result = collection.get(include=["documents", "metadatas", "embeddings"])

            # Guardar en archivo
            import pickle

            with open(backup_path, "wb") as f:
                pickle.dump(result, f)

            logger.info(f"Collection {collection_name} backed up to {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error backing up collection {collection_name}: {e}")
            return False

    def restore_collection(self, collection_name: str, backup_path: str, overwrite: bool = False) -> bool:
        """
        Restaura una colección desde backup

        Args:
            collection_name: Nombre de la colección
            backup_path: Ruta del backup
            overwrite: Sobrescribir si existe
        """
        try:
            # Verificar si la colección existe
            existing_collections = self.list_collections()
            if collection_name in existing_collections:
                if not overwrite:
                    logger.warning(f"Collection {collection_name} already exists")
                    return False
                else:
                    self.delete_collection(collection_name)

            # Cargar backup
            import pickle

            with open(backup_path, "rb") as f:
                data = pickle.load(f)

            # Crear nueva colección
            collection = self.get_collection(collection_name, create_if_not_exists=True)

            # Restaurar datos
            if data.get("documents"):
                collection.add(
                    ids=data["ids"],
                    documents=data["documents"],
                    metadatas=data.get("metadatas"),
                    embeddings=data.get("embeddings"),
                )

            logger.info(f"Collection {collection_name} restored from {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Error restoring collection {collection_name}: {e}")
            return False

    def get_memory_usage(self) -> Dict[str, Any]:
        """Obtiene información sobre uso de memoria"""
        try:
            collections = self.list_collections()
            total_docs = 0
            collection_info = {}

            for collection_name in collections:
                stats = self.get_collection_stats(collection_name)
                doc_count = stats.get("document_count", 0)
                total_docs += doc_count
                collection_info[collection_name] = doc_count

            return {
                "total_collections": len(collections),
                "total_documents": total_docs,
                "collections": collection_info,
                "persist_directory": self.persist_directory,
                "directory_size": self._get_directory_size(),
            }

        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}

    def _get_directory_size(self) -> int:
        """Calcula el tamaño del directorio de persistencia"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.persist_directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return total_size
        except:
            return 0

    def clear_cache(self):
        """Limpia el cache de colecciones"""
        self._collections_cache.clear()
        logger.debug("ChromaDB cache cleared")

