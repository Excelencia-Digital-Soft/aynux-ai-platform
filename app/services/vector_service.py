import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

from app.config.settings import get_settings
from app.models.vectorial import VectorDBConfig, VectorDocument, VectorQueryResult

# Configurar logging
logger = logging.getLogger(__name__)


class VectorDatabaseService:
    """Servicio para manejar bases de datos vectoriales por usuario."""

    def __init__(self):
        self.settings = get_settings()
        self.base_path = os.path.join(self.settings.OLLAMA_API_CHROMADB, "users")
        self.embeddings = OllamaEmbeddings(model=self.settings.OLLAMA_API_MODEL_EMBEDDING)

        # Crear directorio base si no existe
        os.makedirs(self.base_path, exist_ok=True)
        logger.info(f"Vector database service initialized with base path: {self.base_path}")

    def _get_user_db_path(self, config: VectorDBConfig) -> str:
        """Obtiene la ruta para la base de datos vectorial de un usuario."""
        return os.path.join(self.base_path, f"user_{config.user_id}")

    async def initialize_user_db(
        self, config: VectorDBConfig, initial_data: List[VectorDocument]
    ) -> Tuple[bool, List[str]]:
        """
        Inicializa una base de datos vectorial para un usuario.

        Args:
            config: Configuración de la base de datos vectorial
            initial_data: Datos iniciales para la base de datos

        Returns:
            Tuple: (éxito, lista de IDs de documentos añadidos)
        """
        try:
            db_path = self._get_user_db_path(config)
            collection_name = config.collection_name or f"user_{config.user_id}_data"

            if os.path.exists(db_path):
                logger.info(f"Vector database already exists at {db_path}, adding data instead")
                return await self.add_user_data(config, initial_data)

            # Preparar los documentos iniciales
            documents = self._prepare_documents(initial_data)

            if not documents:
                logger.warning("No valid documents to initialize the vector database")
                return False, []

            # Crear la base de datos y añadir documentos
            try:
                # Generar IDs únicos para cada documento
                doc_ids = [str(uuid.uuid4()) for _ in range(len(documents))]

                # Crear instancia y añadir documentos
                Chroma.from_documents(
                    documents=documents,
                    embedding=self.embeddings,
                    collection_name=collection_name,
                    persist_directory=db_path,
                    ids=doc_ids,
                )

                logger.info(f"Successfully initialized vector database with {len(documents)} documents")
                return True, doc_ids

            except Exception as inner_e:
                logger.error(f"Error creating Chroma instance: {str(inner_e)}")
                raise

        except Exception as e:
            logger.error(f"Error initializing vector database: {str(e)}", exc_info=True)
            return False, []

    async def add_user_data(self, config: VectorDBConfig, data: List[VectorDocument]) -> Tuple[bool, List[str]]:
        """
        Añade datos a la base de datos vectorial de un usuario.

        Args:
            config: Configuración de la base de datos vectorial
            data: Datos a añadir

        Returns:
            Tuple: (éxito, lista de IDs de documentos añadidos)
        """
        try:
            db_path = self._get_user_db_path(config)
            collection_name = config.collection_name or f"user_{config.user_id}_data"

            # Verificar si la base de datos existe
            if not os.path.exists(db_path):
                logger.info(f"Vector database doesn't exist at {db_path}, initializing it")
                return await self.initialize_user_db(config, data)

            # Preparar los documentos a añadir
            documents = self._prepare_documents(data)

            if not documents:
                logger.warning("No valid documents to add to the vector database")
                return False, []

            # Cargar la base de datos existente
            vector_store = Chroma(
                persist_directory=db_path,
                embedding_function=self.embeddings,
                collection_name=collection_name,
            )

            # Generar IDs únicos para cada documento
            doc_ids = [str(uuid.uuid4()) for _ in range(len(documents))]

            # Añadir los documentos
            vector_store.add_documents(documents=documents, ids=doc_ids)

            logger.info(f"Successfully added {len(documents)} documents to vector database")

            return True, doc_ids
        except Exception as e:
            print(f"Error añadiendo datos a base vectorial: {str(e)}")
            return False, []

    async def update_document_by_id(self, config: VectorDBConfig, doc_id: str, document: VectorDocument) -> bool:
        """
        Actualiza un documento específico en la base de datos vectorial por su ID.

        Args:
            config: Configuración de la base de datos vectorial
            doc_id: ID del documento a actualizar
            document: Nuevo contenido del documento

        Returns:
            True si se actualizó correctamente, False en caso contrario
        """
        try:
            db_path = self._get_user_db_path(config)
            collection_name = config.collection_name or f"user_{config.user_id}_data"

            # Verificar si la base de datos existe
            if not os.path.exists(db_path):
                logger.warning(f"Cannot update - vector database doesn't exist at {db_path}")
                return False

            # Cargar la base de datos
            vector_store = Chroma(
                persist_directory=db_path,
                embedding_function=self.embeddings,
                collection_name=collection_name,
            )

            # Preparar el documento actualizado
            prepared_docs = self._prepare_documents([document])
            if not prepared_docs:
                logger.warning("Failed to prepare document for update")
                return False

            # En caso de que el splitter haya dividido el documento, usamos solo el primero
            # Para actualización por ID es recomendable que el documento no se divida
            prepared_doc = prepared_docs[0]

            # Actualizar el documento
            # Utilizamos update_document de Chroma
            vector_store.update_document(document_id=doc_id, document=prepared_doc)

            logger.info(f"Successfully updated document with ID {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating document by ID: {str(e)}", exc_info=True)
            return False

    async def update_documents_batch(self, config: VectorDBConfig, documents: List[Tuple[str, VectorDocument]]) -> bool:
        """
        Actualiza múltiples documentos en lote por sus IDs.

        Args:
            config: Configuración de la base de datos vectorial
            documents: Lista de tuplas (doc_id, documento) a actualizar

        Returns:
            True si se actualizaron correctamente, False en caso contrario
        """
        try:
            db_path = self._get_user_db_path(config)
            collection_name = config.collection_name or f"user_{config.user_id}_data"

            # Verificar si la base de datos existe
            if not os.path.exists(db_path):
                logger.warning(f"Cannot update - vector database doesn't exist at {db_path}")
                return False

            # Cargar la base de datos
            vector_store = Chroma(
                persist_directory=db_path,
                embedding_function=self.embeddings,
                collection_name=collection_name,
            )

            # Preparar todos los documentos
            ids = []
            prepared_docs = []

            for doc_id, doc in documents:
                doc_list = self._prepare_documents([doc])
                if doc_list:
                    ids.append(doc_id)
                    # Usar el primer documento preparado (en caso de que se haya dividido)
                    prepared_docs.append(doc_list[0])

            if not prepared_docs:
                logger.warning("No valid documents to update")
                return False

            # Actualizar los documentos en lote
            vector_store.update_documents(ids=ids, documents=prepared_docs)

            logger.info(f"Successfully updated {len(ids)} documents in batch")
            return True

        except Exception as e:
            logger.error(f"Error updating documents in batch: {str(e)}", exc_info=True)
            return False

    async def query_user_data(
        self,
        config: VectorDBConfig,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[VectorQueryResult]:
        """
        Consulta la base de datos vectorial de un usuario.

        Args:
            config: Configuración de la base de datos vectorial
            query: Consulta a realizar
            k: Número de resultados a devolver
            filter_dict: Filtro opcional para la consulta

        Returns:
            Lista de documentos relevantes
        """
        try:
            db_path = self._get_user_db_path(config)
            collection_name = config.collection_name or f"user_{config.user_id}_data"

            # Verificar si la base de datos existe
            if not os.path.exists(db_path):
                logger.warning(f"Vector database doesn't exist at {db_path}")
                return []

            # Cargar la base de datos
            vector_store = Chroma(
                persist_directory=db_path,
                embedding_function=self.embeddings,
                collection_name=collection_name,
            )

            # Realizar la consulta con filtro opcional
            results = vector_store.similarity_search_with_score(query=query, k=k, filter=filter_dict)

            # Formatear los resultados
            formatted_results = []
            for doc, score in results:
                # Intentar parsear el contenido como JSON
                try:
                    content = json.loads(doc.page_content)
                except json.JSONDecodeError:
                    content = doc.page_content
                except Exception as e:
                    logger.error(f"Error parsing document content: {str(e)}")
                    content = doc.page_content

                # Asegurarse de que el ID esté en los metadatos
                metadata = doc.metadata or {}

                # Incluir el ID del documento en el resultado
                doc_id = metadata.get("id", "unknown_id")

                result = VectorQueryResult(
                    content=content,
                    metadata=doc.metadata,
                    score=float(score),
                    id=doc_id,
                )
                formatted_results.append(result)

            logger.info(f"Query returned {len(formatted_results)} results")
            return formatted_results
        except Exception as e:
            logger.error(f"Error querying vector database: {str(e)}", exc_info=True)
            return []

    async def update_user_vectordb(
        self,
        user_id: str,
        data: List[Dict[str, Any]],
        collection_name: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Actualiza la base de datos vectorial del usuario con nueva información.

        Args:
            user_id: ID del usuario
            data: Lista de datos a añadir a la base de datos vectorial
            collection_name: Nombre opcional de la colección

        Returns:
            Tuple: (éxito, lista de IDs de documentos añadidos)
        """
        try:
            # Configurar la base de datos vectorial
            config = VectorDBConfig(
                user_id=user_id,
                collection_name=collection_name or f"user_{user_id}_context",
            )

            # Convertir los datos a documentos vectoriales
            vector_docs = []
            for item in data:
                timestamp = datetime.now().isoformat()
                vector_docs.append(
                    VectorDocument(
                        content=item,
                        metadata={
                            "source": "user_data",
                            "timestamp": timestamp,
                            "user_id": user_id,
                            "updated_at": timestamp,
                        },
                    )
                )

            # Actualizar la base de datos
            logger.info(f"Updating vector database for user {user_id} with {len(vector_docs)} documents")
            success, doc_ids = await self.add_user_data(config, vector_docs)
            return success, doc_ids
        except Exception as e:
            logger.error(f"Error updating user vector database: {str(e)}", exc_info=True)
            return False, []

    def _prepare_documents(self, data: List[VectorDocument]) -> List[Document]:
        """
        Prepara documentos para la base de datos vectorial.

        Args:
            data: Datos a preparar

        Returns:
            Lista de documentos preparados
        """
        try:
            documents = []

            # Convertir datos a formato de documento
            for item in data:
                # Serializar contenido si es necesario
                if isinstance(item.content, (dict, list)):
                    content = json.dumps(item.content, ensure_ascii=False)
                else:
                    content = str(item.content)

                # Asegurar que metadata tenga campos esenciales
                metadata = dict(item.metadata) if item.metadata else {}
                if "id" not in metadata:
                    metadata["id"] = str(uuid.uuid4())
                if "timestamp" not in metadata:
                    metadata["timestamp"] = datetime.now().isoformat()
                if "source" not in metadata:
                    metadata["source"] = "unknown"

                documents.append(Document(page_content=content, metadata=metadata))

            # Dividir documentos largos si es necesario
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )

            split_documents = []
            for doc in documents:
                splits = text_splitter.split_documents([doc])
                split_documents.extend(splits)

            logger.debug(f"Prepared {len(split_documents)} document chunks from {len(documents)} original documents")
            return split_documents

        except Exception as e:
            logger.error(f"Error preparing documents: {str(e)}", exc_info=True)
            return []

    async def delete_user_data(self, config: VectorDBConfig, doc_ids: Optional[List[str]] = None) -> bool:
        """
        Elimina documentos de la base de datos vectorial de un usuario.

        Args:
            config: Configuración de la base de datos vectorial
            doc_ids: Lista de IDs de documentos a eliminar (None para eliminar toda la colección)

        Returns:
            True si se eliminaron correctamente, False en caso contrario
        """
        try:
            db_path = self._get_user_db_path(config)
            collection_name = config.collection_name or f"user_{config.user_id}_data"

            # Verificar si la base de datos existe
            if not os.path.exists(db_path):
                logger.warning(f"Cannot delete - vector database doesn't exist at {db_path}")
                return False

            # Cargar la base de datos
            vector_store = Chroma(
                persist_directory=db_path,
                embedding_function=self.embeddings,
                collection_name=collection_name,
            )

            if doc_ids:
                # Eliminar documentos específicos
                vector_store.delete(ids=doc_ids)
                logger.info(f"Deleted {len(doc_ids)} documents from vector database")
            else:
                # Eliminar toda la colección (reiniciar)
                vector_store.delete_collection()
                logger.info(f"Deleted entire collection {collection_name}")

            return True

        except Exception as e:
            logger.error(f"Error deleting data from vector database: {str(e)}", exc_info=True)
            return False
