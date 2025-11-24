# PDF Vector Storage Service

## Overview

This document describes the PDF and text upload service for the Aynux knowledge base, which allows uploading documents (PDFs or plain text) and storing them in pgvector for semantic search capabilities.

## Architecture

The implementation follows **Clean Architecture** principles with **Domain-Driven Design (DDD)**:

### Layers

1. **Infrastructure Layer** (`app/integrations/document_processing/`)
   - **PDFExtractor**: Service for extracting text from PDF files
   - Handles low-level PDF parsing using `pypdf` library
   - Validates PDF files
   - Extracts metadata (title, author, etc.)

2. **Application Layer** (`app/domains/shared/application/use_cases/`)
   - **UploadPDFUseCase**: Uploads PDF, extracts text, creates knowledge document
   - **UploadTextUseCase**: Uploads plain text/markdown content
   - **BatchUploadDocumentsUseCase**: Batch upload multiple documents
   - Business logic for validation and coordination

3. **Application Layer - Agent Config** (`app/domains/shared/application/use_cases/`)
   - **GetAgentConfigUseCase**: Retrieves current agent configuration
   - **UpdateAgentModulesUseCase**: Updates Excelencia agent modules
   - **UpdateAgentSettingsUseCase**: Updates agent settings

4. **Presentation Layer** (`app/api/routes/`)
   - **document_upload.py**: REST API endpoints for PDF/text upload
   - **agent_config.py**: REST API endpoints for agent configuration
   - Thin controllers that delegate to Use Cases

5. **User Interface** (`streamlit_knowledge_manager.py`)
   - Interactive Streamlit application
   - Upload PDFs and text
   - Browse knowledge base
   - Edit agent configuration
   - View statistics

## Use Cases

### Upload PDF Document

**Use Case**: `UploadPDFUseCase`

**Workflow**:
1. Receive PDF file as bytes
2. Validate PDF format
3. Extract text from all pages using `PDFExtractor`
4. Extract metadata (title, author, pages)
5. Create knowledge document using `CreateKnowledgeUseCase`
6. Generate embeddings automatically (pgvector + ChromaDB)
7. Return created document with ID

**Example**:
```python
from app.domains.shared.application.use_cases import UploadPDFUseCase
from app.database.async_db import get_async_db

async with get_async_db() as db:
    use_case = UploadPDFUseCase(db)

    with open("manual.pdf", "rb") as f:
        pdf_bytes = f.read()

    result = await use_case.execute(
        pdf_bytes=pdf_bytes,
        title="Product Manual",
        document_type="faq",
        tags=["product", "manual"]
    )

    print(f"Document created: {result['id']}")
```

### Upload Text Content

**Use Case**: `UploadTextUseCase`

**Workflow**:
1. Receive text content and metadata
2. Validate content length (minimum 50 characters)
3. Create knowledge document using `CreateKnowledgeUseCase`
4. Generate embeddings automatically
5. Return created document

**Example**:
```python
from app.domains.shared.application.use_cases import UploadTextUseCase
from app.database.async_db import get_async_db

async with get_async_db() as db:
    use_case = UploadTextUseCase(db)

    result = await use_case.execute(
        content="This is important information about our company...",
        title="Company Information",
        document_type="mission_vision",
        tags=["company", "info"]
    )

    print(f"Document created: {result['id']}")
```

### Get Agent Configuration

**Use Case**: `GetAgentConfigUseCase`

**Workflow**:
1. Import Excelencia agent module
2. Extract current modules configuration
3. Extract settings (model, temperature, RAG settings)
4. Return complete configuration

**Example**:
```python
from app.domains.shared.application.use_cases import GetAgentConfigUseCase

use_case = GetAgentConfigUseCase()
config = await use_case.execute()

print(f"Modules: {list(config['modules'].keys())}")
print(f"Model: {config['settings']['model']}")
```

### Update Agent Modules

**Use Case**: `UpdateAgentModulesUseCase`

**Workflow**:
1. Validate module structure
2. Read current agent source file
3. Create backup of current configuration
4. Generate new Python code for modules
5. Update source file
6. Return success status

**Example**:
```python
from app.domains.shared.application.use_cases import UpdateAgentModulesUseCase

use_case = UpdateAgentModulesUseCase()

new_modules = {
    "historia_clinica": {
        "name": "Historia Clínica Electrónica",
        "description": "Sistema completo de historias clínicas",
        "features": ["Registro de pacientes", "Consultas médicas"],
        "target": "Hospitales, Clínicas"
    }
}

result = await use_case.execute(modules=new_modules, create_backup=True)
print(f"Updated: {result['modules_updated']} modules")
print(f"Backup: {result['backup_path']}")
```

## REST API Endpoints

### Document Upload Endpoints

**Base URL**: `/api/v1/admin/documents`

#### POST `/upload/pdf`
Upload a PDF file to the knowledge base.

**Request**:
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file`: PDF file (required)
  - `title`: Document title (optional, extracted from PDF if not provided)
  - `document_type`: Type of document (default: "general")
  - `category`: Category (optional)
  - `tags`: Comma-separated tags (optional)

**Response**:
```json
{
  "success": true,
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Product Manual",
  "document_type": "faq",
  "character_count": 15234,
  "has_embedding": true,
  "message": "PDF uploaded successfully: Product Manual"
}
```

#### POST `/upload/text`
Upload plain text or markdown content.

**Request**:
- **Content-Type**: `application/json`
- **Body**:
```json
{
  "content": "This is the document content...",
  "title": "Document Title",
  "document_type": "general",
  "category": "tutorials",
  "tags": ["tutorial", "guide"],
  "metadata": {"author": "John Doe"}
}
```

**Response**:
```json
{
  "success": true,
  "document_id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Document Title",
  "document_type": "general",
  "character_count": 523,
  "has_embedding": true,
  "message": "Text uploaded successfully: Document Title"
}
```

#### POST `/upload/batch`
Upload multiple documents in a single request.

**Request**:
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `files`: List of files (PDFs or text files)
  - `document_type`: Document type for all files
  - `category`: Category for all files (optional)

**Response**:
```json
{
  "total": 5,
  "successful": 4,
  "failed": 1,
  "results": [...],
  "errors": ["Document 3 failed: Invalid PDF"]
}
```

#### GET `/supported-types`
Get list of supported document types.

**Response**:
```json
{
  "document_types": [
    {
      "id": "mission_vision",
      "name": "Mission & Vision",
      "description": "Company mission, vision, and values"
    },
    ...
  ]
}
```

### Agent Configuration Endpoints

**Base URL**: `/api/v1/admin/agent-config`

#### GET `/excelencia`
Get current Excelencia agent configuration.

**Response**:
```json
{
  "modules": {
    "historia_clinica": {
      "name": "Historia Clínica Electrónica",
      "description": "...",
      "features": [...],
      "target": "Hospitales, Clínicas"
    },
    ...
  },
  "query_types": {...},
  "settings": {
    "model": "llama3.1",
    "temperature": 0.7,
    "max_response_length": 500,
    "use_rag": true,
    "rag_max_results": 3
  },
  "available_document_types": [...]
}
```

#### PUT `/excelencia/modules`
Update Excelencia agent modules.

**Request**:
```json
{
  "modules": {
    "module_id": {
      "name": "Module Name",
      "description": "Module description",
      "features": ["Feature 1", "Feature 2"],
      "target": "Target audience"
    }
  },
  "create_backup": true
}
```

**Response**:
```json
{
  "success": true,
  "message": "Configuration updated successfully. Please restart...",
  "backup_path": "app/agents/subagent/excelencia_agent.py.backup",
  "requires_restart": true
}
```

#### PATCH `/excelencia/settings`
Update Excelencia agent settings.

**Request**:
```json
{
  "model": "llama3.1",
  "temperature": 0.7,
  "max_response_length": 500,
  "use_rag": true,
  "rag_max_results": 3
}
```

**Response**:
```json
{
  "success": true,
  "message": "Settings validated. For production use...",
  "requires_restart": false
}
```

#### GET `/excelencia/modules`
Get list of Excelencia modules.

#### GET `/excelencia/settings`
Get current Excelencia settings.

## Streamlit User Interface

### Starting the Knowledge Manager

```bash
# Using the provided script
./run_knowledge_manager.sh

# Or directly with streamlit
streamlit run streamlit_knowledge_manager.py
```

Access at: **http://localhost:8501**

### Features

#### 📄 Upload PDF
- Drag and drop PDF files
- Optional title (extracted from PDF if not provided)
- Select document type
- Add category and tags
- Automatic text extraction and embedding generation

#### ✍️ Upload Text
- Enter text content (plain text or markdown)
- Required title
- Select document type
- Add category and tags
- Minimum 50 characters required

#### 📋 Browse Knowledge
- View all documents in knowledge base
- Filter by document type
- Pagination support
- View document details
- Delete documents (soft delete)
- Content preview

#### ⚙️ Agent Configuration
- View current agent modules
- Edit module configuration
  - Name, description, features, target audience
  - Save changes with automatic backup
- View agent settings
  - Model, temperature, RAG settings

#### 📊 Statistics
- Active/inactive documents count
- Missing embeddings count
- Embedding coverage percentage
- ChromaDB collection stats
- Embedding model information

## Data Flow

### PDF Upload Flow

```
User → Streamlit UI → POST /api/v1/admin/documents/upload/pdf
     → UploadPDFUseCase
     → PDFExtractor.extract_text_from_bytes()
     → CreateKnowledgeUseCase.execute()
     → CompanyKnowledge (Database)
     → KnowledgeEmbeddingService.update_knowledge_embeddings()
     → pgvector (PostgreSQL)
     → ChromaDB
     → Response
```

### Text Upload Flow

```
User → Streamlit UI → POST /api/v1/admin/documents/upload/text
     → UploadTextUseCase
     → CreateKnowledgeUseCase.execute()
     → CompanyKnowledge (Database)
     → KnowledgeEmbeddingService.update_knowledge_embeddings()
     → pgvector (PostgreSQL)
     → ChromaDB
     → Response
```

### Agent Configuration Flow

```
User → Streamlit UI → GET/PUT /api/v1/admin/agent-config/excelencia
     → GetAgentConfigUseCase / UpdateAgentModulesUseCase
     → Read/Update excelencia_agent.py source file
     → Create backup (if updating)
     → Response (requires restart if modules updated)
```

## Storage

### Database (PostgreSQL)

Documents are stored in the `company_knowledge` table:

```sql
CREATE TABLE company_knowledge (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    document_type document_type_enum NOT NULL,
    category VARCHAR(200),
    tags TEXT[],
    meta_data JSONB,
    active BOOLEAN DEFAULT true,
    embedding vector(768),  -- pgvector
    search_vector tsvector,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Vector Search

**pgvector**:
- Primary vector search using PostgreSQL extension
- 768-dimensional embeddings (nomic-embed-text)
- HNSW index for fast similarity search
- Native SQL integration

**ChromaDB**:
- Secondary vector store (legacy support)
- Collections by document type
- Semantic search capabilities

## Configuration

### Environment Variables

```bash
# API Configuration
API_BASE_URL=http://localhost:8000

# Database
DB_HOST=localhost
DB_NAME=aynux
DB_USER=your_user
DB_PASSWORD=your_password

# Ollama (for embeddings)
OLLAMA_API_URL=http://localhost:11434
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text

# Knowledge Base
KNOWLEDGE_BASE_ENABLED=true
KNOWLEDGE_SEARCH_STRATEGY=hybrid
USE_PGVECTOR=true
```

### Document Types

Available document types:
- `mission_vision`: Company mission, vision, and values
- `contact_info`: Contact information and social networks
- `software_catalog`: Software catalog and modules
- `faq`: Frequently asked questions
- `clients`: Client information
- `success_stories`: Case studies and success stories
- `general`: General information

## Dependencies

### Python Packages

```toml
# Required for PDF extraction
pypdf>=5.1.0

# Already available in project
langchain-core>=0.3.62
langchain-chroma>=0.1.2
pgvector>=0.4.1
streamlit>=1.39.0
fastapi>=0.115.12
sqlalchemy>=2.0.41
```

### Installation

```bash
# Using uv (recommended)
uv sync

# Or manually install PDF support
pip install pypdf
```

## Usage Examples

### Example 1: Upload PDF via API

```python
import httpx

# Upload PDF
with open("manual.pdf", "rb") as f:
    files = {"file": ("manual.pdf", f, "application/pdf")}
    data = {
        "title": "Product Manual",
        "document_type": "faq",
        "tags": "product,manual"
    }

    response = httpx.post(
        "http://localhost:8000/api/v1/admin/documents/upload/pdf",
        files=files,
        data=data
    )

    print(response.json())
```

### Example 2: Upload Text via API

```python
import httpx

# Upload text
data = {
    "content": "This is our company mission and vision...",
    "title": "Mission & Vision",
    "document_type": "mission_vision",
    "tags": ["company", "mission"]
}

response = httpx.post(
    "http://localhost:8000/api/v1/admin/documents/upload/text",
    json=data
)

print(response.json())
```

### Example 3: Update Agent Configuration

```python
import httpx

# Get current config
response = httpx.get(
    "http://localhost:8000/api/v1/admin/agent-config/excelencia"
)
config = response.json()

# Update a module
modules = {
    "historia_clinica": {
        "name": "Historia Clínica Electrónica v2",
        "description": "Updated description...",
        "features": ["New Feature 1", "New Feature 2"],
        "target": "Hospitales, Clínicas, Sanatorios"
    }
}

response = httpx.put(
    "http://localhost:8000/api/v1/admin/agent-config/excelencia/modules",
    json={"modules": modules, "create_backup": True}
)

print(response.json())
```

## Testing

Run tests:

```bash
# All tests
pytest tests/test_document_upload.py -v

# Specific test
pytest tests/test_document_upload.py::TestPDFExtractor::test_pdf_extractor_initialization -v
```

## Security Considerations

1. **File Validation**:
   - PDF files are validated before processing
   - File size limits should be enforced (configure in FastAPI)
   - Only PDF files accepted for PDF upload endpoint

2. **Content Validation**:
   - Minimum content length (50 characters)
   - Maximum content length (database limit: TEXT type)
   - Title length validation

3. **Authentication**:
   - All admin endpoints should require authentication
   - Implement proper authorization checks
   - Rate limiting for upload endpoints

4. **Configuration Changes**:
   - Module updates create automatic backups
   - Source code modifications require application restart
   - Backup files should be protected

## Future Enhancements

1. **Document Processing**:
   - Support for DOCX, TXT, MD files
   - Image extraction from PDFs
   - OCR for scanned PDFs
   - Multi-language support

2. **Agent Configuration**:
   - Database-backed configuration (instead of source file)
   - Hot-reload configuration without restart
   - Configuration versioning and rollback
   - Multi-agent configuration support

3. **User Interface**:
   - Drag-and-drop file upload
   - Batch upload progress tracking
   - Document preview before upload
   - Advanced search and filtering

4. **Vector Search**:
   - Hybrid search strategies
   - Custom embedding models
   - Similarity score threshold configuration
   - Vector index optimization

## Troubleshooting

### Common Issues

**Issue**: PDF extraction fails
- **Solution**: Ensure `pypdf` is installed: `pip install pypdf`
- Check PDF file is not encrypted or corrupted

**Issue**: Embeddings not generated
- **Solution**: Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check `nomic-embed-text` model is installed

**Issue**: Agent configuration update fails
- **Solution**: Check file permissions on `excelencia_agent.py`
- Verify Python syntax in modules configuration
- Review backup file for previous configuration

**Issue**: Streamlit UI can't connect to API
- **Solution**: Verify API is running: `curl http://localhost:8000/health`
- Check `API_BASE_URL` environment variable
- Ensure no firewall blocking ports

## References

- [Clean Architecture Documentation](FINAL_MIGRATION_SUMMARY.md)
- [Knowledge Base API](../app/api/routes/knowledge_admin.py)
- [pgvector Migration](PGVECTOR_MIGRATION.md)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [pypdf Documentation](https://pypdf.readthedocs.io/)
