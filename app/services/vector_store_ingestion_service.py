"""
Vector Store Ingestion Service for AI Agent Integration.

This service handles the processing and storage of extracted data into vector stores,
making it available for AI agents at runtime through embeddings.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from app.services.data_extraction_service import ExtractedData

logger = logging.getLogger(__name__)


# Data Models
class EmbeddingChunk(BaseModel):
    """A chunk of data to be embedded."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_table: str
    user_id: Optional[str] = None
    chunk_index: int = 0
    total_chunks: int = 1


class VectorStoreDocument(BaseModel):
    """Document to be stored in vector store."""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class IngestionResult(BaseModel):
    """Result of vector store ingestion."""
    success: bool
    documents_processed: int
    documents_stored: int
    errors: List[str] = Field(default_factory=list)
    processing_time_seconds: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Abstract Interfaces
class DataChunker(Protocol):
    """Protocol for chunking data for embedding."""
    
    def chunk_data(
        self,
        extracted_data: ExtractedData,
        user_id: Optional[str] = None,
        chunk_size: int = 1000
    ) -> List[EmbeddingChunk]:
        """Break down extracted data into chunks suitable for embedding."""
        ...


class EmbeddingGenerator(Protocol):
    """Protocol for generating embeddings."""
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for given text."""
        ...
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str]
    ) -> List[List[float]]:
        """Generate embeddings for multiple texts in batch."""
        ...


class VectorStoreAdapter(Protocol):
    """Protocol for vector store operations."""
    
    async def store_documents(
        self,
        documents: List[VectorStoreDocument]
    ) -> bool:
        """Store documents in the vector store."""
        ...
    
    async def search_similar(
        self,
        query_embedding: List[float],
        user_id: Optional[str] = None,
        table_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[VectorStoreDocument]:
        """Search for similar documents in the vector store."""
        ...
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all data for a specific user."""
        ...


# Concrete Implementations
class SmartDataChunker:
    """Intelligent data chunker that preserves semantic meaning."""
    
    def chunk_data(
        self,
        extracted_data: ExtractedData,
        user_id: Optional[str] = None,
        chunk_size: int = 1000
    ) -> List[EmbeddingChunk]:
        """Break down extracted data into semantically meaningful chunks."""
        chunks = []
        
        # Create a summary chunk with schema information
        schema_content = self._create_schema_summary(extracted_data)
        chunks.append(EmbeddingChunk(
            content=schema_content,
            metadata={
                "type": "schema",
                "table_name": extracted_data.table_name,
                "total_records": extracted_data.total_records
            },
            source_table=extracted_data.table_name,
            user_id=user_id,
            chunk_index=0
        ))
        
        # Create chunks for actual data
        data_chunks = self._chunk_records(
            extracted_data.data,
            extracted_data.table_name,
            chunk_size,
            user_id
        )
        
        chunks.extend(data_chunks)
        
        # Update total chunks count
        total_chunks = len(chunks)
        for chunk in chunks:
            chunk.total_chunks = total_chunks
        
        return chunks
    
    def _create_schema_summary(self, extracted_data: ExtractedData) -> str:
        """Create a human-readable summary of the table schema."""
        schema = extracted_data.table_schema
        
        summary_parts = [
            f"Table: {schema.name}",
            f"Total records: {extracted_data.total_records}",
            "Columns:"
        ]
        
        for col in schema.columns:
            col_desc = f"- {col.name} ({col.type})"
            if col.primary_key:
                col_desc += " [PRIMARY KEY]"
            if col.foreign_key:
                col_desc += f" [REFERENCES {col.foreign_key}]"
            if not col.nullable:
                col_desc += " [NOT NULL]"
            
            summary_parts.append(col_desc)
        
        if schema.indexes:
            summary_parts.append("Indexes: " + ", ".join(schema.indexes))
        
        return "\n".join(summary_parts)
    
    def _chunk_records(
        self,
        records: List[Dict[str, Any]],
        table_name: str,
        chunk_size: int,
        user_id: Optional[str]
    ) -> List[EmbeddingChunk]:
        """Chunk individual records into manageable pieces."""
        chunks = []
        
        # Group records into chunks
        for i in range(0, len(records), chunk_size):
            chunk_records = records[i:i + chunk_size]
            
            # Create human-readable content for this chunk
            content_parts = [f"Data from table {table_name}:"]
            
            for record in chunk_records:
                record_text = self._format_record(record)
                content_parts.append(record_text)
            
            content = "\n\n".join(content_parts)
            
            # Create chunk ID based on content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            chunk_id = f"{table_name}_{user_id or 'global'}_{i}_{content_hash}"
            
            chunks.append(EmbeddingChunk(
                id=chunk_id,
                content=content,
                metadata={
                    "type": "data",
                    "record_count": len(chunk_records),
                    "chunk_start_index": i,
                    "chunk_end_index": min(i + chunk_size, len(records))
                },
                source_table=table_name,
                user_id=user_id,
                chunk_index=len(chunks) + 1  # +1 because schema chunk is index 0
            ))
        
        return chunks
    
    def _format_record(self, record: Dict[str, Any]) -> str:
        """Format a single record into human-readable text."""
        formatted_fields = []
        
        for key, value in record.items():
            if value is not None:
                formatted_fields.append(f"{key}: {value}")
        
        return "Record: " + ", ".join(formatted_fields)


class ChromaVectorStoreAdapter:
    """ChromaDB adapter for vector store operations."""
    
    def __init__(self, collection_name: str = "user_data_embeddings"):
        self.collection_name = collection_name
        self._collection = None
    
    async def _get_collection(self):
        """Get or create ChromaDB collection."""
        if self._collection is None:
            try:
                from app.agents.langgraph_system.integrations.chroma_integration import ChromaDBIntegration
                chroma_integration = ChromaDBIntegration()
                # Create collection if it doesn't exist
                self._collection = chroma_integration.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "User-specific data embeddings for AI agents"}
                )
            except Exception as e:
                logger.error(f"Error initializing ChromaDB collection: {e}")
                raise
        
        return self._collection
    
    async def store_documents(self, documents: List[VectorStoreDocument]) -> bool:
        """Store documents in ChromaDB."""
        try:
            collection = await self._get_collection()
            
            # Prepare data for ChromaDB
            ids = [doc.id for doc in documents]
            embeddings = [doc.embedding for doc in documents if doc.embedding]
            metadatas = [doc.metadata for doc in documents]
            documents_text = [doc.content for doc in documents]
            
            # Store in ChromaDB
            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents_text
            )
            
            logger.info(f"Stored {len(documents)} documents in vector store")
            return True
            
        except Exception as e:
            logger.error(f"Error storing documents in vector store: {e}")
            return False
    
    async def search_similar(
        self,
        query_embedding: List[float],
        user_id: Optional[str] = None,
        table_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[VectorStoreDocument]:
        """Search for similar documents."""
        try:
            collection = await self._get_collection()
            
            # Build where clause for filtering
            where_clause = {}
            if user_id:
                where_clause["user_id"] = user_id
            if table_filter:
                where_clause["source_table"] = table_filter
            
            # Query ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_clause if where_clause else None
            )
            
            # Convert results to VectorStoreDocument objects
            documents = []
            if results.get('ids') and results['ids'] and results['ids'][0]:
                ids = results['ids'][0]
                documents_data = results.get('documents')
                documents_list = documents_data[0] if documents_data and documents_data[0] else []
                metadatas_data = results.get('metadatas')
                metadatas_list = metadatas_data[0] if metadatas_data and metadatas_data[0] else []
                embeddings_data = results.get('embeddings')
                embeddings_list = embeddings_data[0] if embeddings_data and embeddings_data[0] else []
                
                for i, doc_id in enumerate(ids):
                    documents.append(VectorStoreDocument(
                        id=doc_id,
                        content=documents_list[i] if i < len(documents_list) else "",
                        metadata=metadatas_list[i] if i < len(metadatas_list) else {},
                        embedding=embeddings_list[i] if i < len(embeddings_list) else None
                    ))
            
            return documents
            
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all data for a specific user."""
        try:
            collection = await self._get_collection()
            
            # Query for user's documents
            results = collection.get(where={"user_id": user_id})
            
            if results['ids']:
                # Delete the documents
                collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} documents for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting user data: {e}")
            return False


class OllamaEmbeddingGenerator:
    """Ollama-based embedding generator."""
    
    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
            ollama = OllamaIntegration()
            
            # Generate embedding using Ollama
            embeddings = ollama.get_embeddings(model=self.model_name)
            embedding = await embeddings.aembed_query(text)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []
        
        for text in texts:
            try:
                embedding = await self.generate_embedding(text)
                embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Error generating embedding for text: {e}")
                # Use zeros as fallback
                embeddings.append([0.0] * 384)  # Default embedding dimension
        
        return embeddings


# Main Service
class VectorStoreIngestionService:
    """
    Main service for processing and ingesting data into vector stores.
    
    This service coordinates the chunking, embedding, and storage of extracted data
    to make it available for AI agents at runtime.
    """
    
    def __init__(
        self,
        chunker: DataChunker,
        embedding_generator: EmbeddingGenerator,
        vector_store: VectorStoreAdapter
    ):
        self.chunker = chunker
        self.embedding_generator = embedding_generator
        self.vector_store = vector_store
    
    async def ingest_extracted_data(
        self,
        extracted_data: ExtractedData,
        user_id: Optional[str] = None,
        chunk_size: int = 1000
    ) -> IngestionResult:
        """
        Ingest extracted data into the vector store.
        
        Args:
            extracted_data: The data to ingest
            user_id: Optional user ID for user-specific storage
            chunk_size: Size of chunks for embedding
            
        Returns:
            IngestionResult with processing details
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Step 1: Chunk the data
            chunks = self.chunker.chunk_data(
                extracted_data=extracted_data,
                user_id=user_id,
                chunk_size=chunk_size
            )
            
            logger.info(f"Created {len(chunks)} chunks for table {extracted_data.table_name}")
            
            # Step 2: Generate embeddings
            texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_generator.generate_embeddings_batch(texts)
            
            # Step 3: Create vector store documents
            documents = []
            for chunk, embedding in zip(chunks, embeddings):
                # Enhance metadata
                metadata = chunk.metadata.copy()
                metadata.update({
                    "source_table": chunk.source_table,
                    "user_id": chunk.user_id,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks,
                    "ingestion_timestamp": datetime.now().isoformat()
                })
                
                documents.append(VectorStoreDocument(
                    id=chunk.id,
                    content=chunk.content,
                    embedding=embedding,
                    metadata=metadata
                ))
            
            # Step 4: Store in vector store
            success = await self.vector_store.store_documents(documents)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return IngestionResult(
                success=success,
                documents_processed=len(chunks),
                documents_stored=len(documents) if success else 0,
                errors=errors,
                processing_time_seconds=processing_time,
                metadata={
                    "table_name": extracted_data.table_name,
                    "user_id": user_id,
                    "chunk_size": chunk_size,
                    "original_records": extracted_data.total_records
                }
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Error during ingestion: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
            
            return IngestionResult(
                success=False,
                documents_processed=0,
                documents_stored=0,
                errors=errors,
                processing_time_seconds=processing_time
            )
    
    async def search_user_data(
        self,
        query: str,
        user_id: str,
        table_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[VectorStoreDocument]:
        """
        Search for user-specific data using a query.
        
        Args:
            query: Search query
            user_id: User ID to filter by
            table_filter: Optional table name filter
            limit: Maximum number of results
            
        Returns:
            List of relevant documents
        """
        try:
            # Generate embedding for the query
            query_embedding = await self.embedding_generator.generate_embedding(query)
            
            # Search in vector store
            results = await self.vector_store.search_similar(
                query_embedding=query_embedding,
                user_id=user_id,
                table_filter=table_filter,
                limit=limit
            )
            
            logger.info(f"Found {len(results)} relevant documents for user {user_id}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching user data: {e}")
            return []
    
    async def delete_user_data(self, user_id: str) -> bool:
        """Delete all vector store data for a user."""
        return await self.vector_store.delete_user_data(user_id)


# Factory Functions
def create_vector_ingestion_service() -> VectorStoreIngestionService:
    """Create a vector store ingestion service with default components."""
    chunker = SmartDataChunker()
    embedding_generator = OllamaEmbeddingGenerator()
    vector_store = ChromaVectorStoreAdapter()
    
    return VectorStoreIngestionService(chunker, embedding_generator, vector_store)


def create_ingestion_service_from_config(config: Dict[str, Any]) -> VectorStoreIngestionService:
    """Create a vector store ingestion service based on configuration."""
    # Create chunker
    chunker = SmartDataChunker()
    
    # Create embedding generator
    embedding_model = config.get("embedding_model", "nomic-embed-text")
    embedding_generator = OllamaEmbeddingGenerator(model_name=embedding_model)
    
    # Create vector store adapter
    collection_name = config.get("collection_name", "user_data_embeddings")
    vector_store = ChromaVectorStoreAdapter(collection_name=collection_name)
    
    return VectorStoreIngestionService(chunker, embedding_generator, vector_store)