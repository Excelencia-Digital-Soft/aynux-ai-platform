# Dynamic Data Pipeline Architecture for AI Agents

## Overview

This document describes the comprehensive Dynamic Data Pipeline Service designed to retrieve data based on table structures, process it for vector store ingestion, and make it available for AI agents at runtime. The system follows a layered, decoupled architecture that can adapt to different data sources and embedding pipelines.

## Architecture Components

### 1. Data Extraction Layer (`data_extraction_service.py`)

**Responsibility**: Dynamic schema inspection and data extraction from various sources.

#### Key Interfaces:
- `DataSourceInspector`: Protocol for schema inspection
- `DataExtractor`: Protocol for data extraction
- `DataSerializer`: Abstract base for data serialization

#### Concrete Implementations:
- `SQLAlchemyInspector`: PostgreSQL/SQL database schema inspection
- `SQLAlchemyExtractor`: SQL data extraction with filtering
- `JSONDataSerializer`: JSON serialization for vector store compatibility

#### Capabilities:
- **Dynamic Schema Detection**: Automatically inspects table structure, columns, types, relationships
- **Flexible Data Extraction**: Supports filtering, user-specific queries, pagination
- **Type-Safe Serialization**: Handles datetime, decimal, UUID, and complex types
- **User Context Support**: Extracts data specific to individual users

### 2. Vector Store Ingestion Layer (`vector_store_ingestion_service.py`)

**Responsibility**: Processing extracted data for vector store integration.

#### Key Interfaces:
- `DataChunker`: Protocol for intelligent data chunking
- `EmbeddingGenerator`: Protocol for creating embeddings
- `VectorStoreAdapter`: Protocol for vector store operations

#### Concrete Implementations:
- `SmartDataChunker`: Preserves semantic meaning while chunking
- `OllamaEmbeddingGenerator`: Uses Ollama for local embeddings
- `ChromaVectorStoreAdapter`: ChromaDB integration

#### Capabilities:
- **Semantic Chunking**: Breaks data into meaningful pieces for embedding
- **Schema Summarization**: Creates human-readable table descriptions
- **Batch Embedding**: Efficient processing of multiple texts
- **User Isolation**: Maintains data separation between users
- **Similarity Search**: Retrieves relevant context for queries

### 3. Pipeline Orchestration Layer (`ai_data_pipeline_service.py`)

**Responsibility**: Main orchestrator coordinating the complete pipeline.

#### Core Services:
- `AIDataPipelineService`: Main orchestration service
- `PipelineExecutionContext`: Configuration for pipeline runs
- `DataRetrievalContext`: Context for AI agent queries

#### Capabilities:
- **End-to-End Pipeline**: From data extraction to AI context generation
- **User Data Management**: Setup, refresh, and deletion of user-specific data
- **Auto-Refresh**: Configurable data freshness management
- **Error Handling**: Comprehensive error tracking and recovery
- **Context Generation**: Formatted output for AI agent consumption

### 4. AI Agent Integration Layer (`ai_data_integration.py`)

**Responsibility**: Seamless integration with LangGraph agents.

#### Integration Components:
- `AgentDataContext`: Simple interface for agents
- `DataEnhancedAgentMixin`: Mixin for existing agent classes
- **Convenience Functions**: Easy-to-use helper functions

#### Agent Integration Methods:
- `get_context_for_query()`: Get relevant context for any query
- `get_user_purchase_history()`: Specialized purchase data retrieval
- `get_user_product_preferences()`: Product preference analysis
- `enhance_prompt_with_context()`: Automatic prompt enhancement

## Data Flow Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Source   │───▶│  Extraction     │───▶│   Chunking &    │
│   (Database)    │    │   Service       │    │   Embedding     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐             │
│   AI Agent      │◀───│  Context        │◀────────────┘
│   Enhanced      │    │  Retrieval      │
│   Responses     │    │                 │
└─────────────────┘    └─────────────────┘
                                │
                       ┌─────────────────┐
                       │  Vector Store   │
                       │   (ChromaDB)    │
                       └─────────────────┘
```

## Usage Examples

### 1. Basic Pipeline Setup

```python
from app.services.ai_data_pipeline_service import create_ai_data_pipeline_service

# Create pipeline service
pipeline = create_ai_data_pipeline_service({
    "chunk_size": 1000,
    "enable_auto_refresh": True,
    "refresh_interval_hours": 24
})

# Setup data for a user
context = PipelineExecutionContext(
    user_id="user_12345",
    tables=["orders", "products", "customers"],
    force_refresh=False
)

result = await pipeline.setup_user_data_pipeline(context)
```

### 2. Agent Integration

```python
from app.agents.langgraph_system.integrations.ai_data_integration import get_enhanced_prompt_for_agent

# Enhance any agent prompt with user context
enhanced_prompt = await get_enhanced_prompt_for_agent(
    agent_type="product",
    base_prompt="Help the user find suitable products",
    user_id="user_12345",
    user_query="I need a new laptop for gaming"
)
```

### 3. Direct Context Retrieval

```python
from app.services.ai_data_pipeline_service import get_user_context_for_agent

# Get formatted context for AI consumption
context = await get_user_context_for_agent(
    user_id="user_12345",
    query="show my recent orders",
    table_filters=["orders", "products"],
    max_results=5
)
```

### 4. Agent Mixin Usage

```python
from app.agents.langgraph_system.integrations.ai_data_integration import DataEnhancedAgentMixin

class EnhancedProductAgent(DataEnhancedAgentMixin, BaseAgent):
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]):
        user_id = state_dict.get("user_phone")
        
        # Get user-specific context
        user_context = await self.get_user_context(
            user_id=user_id,
            query=message,
            context_type="products"
        )
        
        # Enhance prompt with context
        enhanced_prompt = await self.enhance_prompt_with_context(
            base_prompt="Help user with product query",
            user_id=user_id,
            query=message,
            context_type="products"
        )
        
        # Process with enhanced context...
```

## Configuration Options

### Pipeline Configuration

```python
{
    "extraction": {
        "source_type": "sql",  # Future: "api", "file", etc.
        "connection_pool_size": 10
    },
    "ingestion": {
        "embedding_model": "nomic-embed-text",
        "collection_name": "user_data_embeddings",
        "batch_size": 50
    },
    "chunk_size": 1000,
    "max_records": 10000,
    "enable_auto_refresh": True,
    "refresh_interval_hours": 24
}
```

### Context Types

- `general`: Search across all tables
- `products`: Focus on product-related data
- `orders`: Order history and transactions
- `conversations`: Chat and interaction history
- `customer`: Customer profile and preferences
- `support`: Support tickets and issues

## Extensibility Points

### 1. Data Sources

The system can be extended to support different data sources by implementing the protocols:

```python
class APIDataExtractor:
    def extract_table_data(self, table_name: str, filters: Dict = None) -> List[Dict]:
        # Implement API-based data extraction
        pass

class FileDataExtractor:
    def extract_table_data(self, table_name: str, filters: Dict = None) -> List[Dict]:
        # Implement file-based data extraction (CSV, JSON, etc.)
        pass
```

### 2. Embedding Providers

Support for different embedding providers:

```python
class OpenAIEmbeddingGenerator:
    async def generate_embedding(self, text: str) -> List[float]:
        # Implement OpenAI embeddings
        pass

class HuggingFaceEmbeddingGenerator:
    async def generate_embedding(self, text: str) -> List[float]:
        # Implement HuggingFace embeddings
        pass
```

### 3. Vector Stores

Support for different vector databases:

```python
class PineconeVectorStoreAdapter:
    async def store_documents(self, documents: List[VectorStoreDocument]) -> bool:
        # Implement Pinecone storage
        pass

class WeaviateVectorStoreAdapter:
    async def store_documents(self, documents: List[VectorStoreDocument]) -> bool:
        # Implement Weaviate storage
        pass
```

## Performance Considerations

### 1. Chunking Strategy
- **Schema Chunks**: Separate chunks for table structure information
- **Data Chunks**: Configurable size based on content complexity
- **Semantic Preservation**: Maintains record boundaries and relationships

### 2. Embedding Efficiency
- **Batch Processing**: Process multiple texts together
- **Caching**: Avoid re-generating embeddings for unchanged data
- **Incremental Updates**: Only process new or modified data

### 3. Vector Store Optimization
- **User Isolation**: Separate collections or namespaces per user
- **Metadata Filtering**: Efficient filtering during similarity search
- **Index Management**: Proper indexing for fast retrieval

## Security and Privacy

### 1. Data Isolation
- User data is strictly separated in the vector store
- Queries are filtered by user ID to prevent cross-contamination
- Data deletion completely removes user information

### 2. Access Control
- User authentication required for all operations
- Context retrieval is limited to the requesting user's data
- No global data access without explicit user consent

### 3. Data Retention
- Configurable data retention policies
- Automatic cleanup of expired user data
- Audit logging for data access and modifications

## Testing and Validation

The system includes comprehensive testing:

1. **Unit Tests**: Individual component validation
2. **Integration Tests**: End-to-end pipeline testing
3. **Performance Tests**: Load and stress testing
4. **Data Quality Tests**: Validation of extracted and processed data

## Future Enhancements

### 1. Advanced Analytics
- User behavior pattern analysis
- Predictive context generation
- Recommendation engine integration

### 2. Real-time Processing
- Stream processing for live data updates
- Event-driven pipeline triggers
- Real-time similarity search optimization

### 3. Multi-modal Support
- Image and document processing
- Audio and video content analysis
- Cross-modal similarity search

## Implementation Status

✅ **Completed:**
- Core architecture and interfaces
- SQL database extraction
- ChromaDB vector store integration
- Ollama embedding generation
- LangGraph agent integration
- Comprehensive testing framework

🔄 **In Progress:**
- Performance optimization
- Additional data source connectors
- Enhanced error handling

📋 **Planned:**
- API-based data extraction
- OpenAI embedding integration
- Advanced chunking strategies
- Real-time processing capabilities

This architecture provides a solid foundation for AI agents to access and utilize user-specific data while maintaining flexibility for future enhancements and different deployment scenarios.