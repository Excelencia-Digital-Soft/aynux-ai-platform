# Multi-Tenancy Architecture

Aynux provides enterprise-grade multi-tenant support, enabling complete data isolation between organizations while sharing the same application infrastructure.

---

## Overview

Multi-tenancy in Aynux allows:
- **SaaS Deployment**: Host multiple customers on a single instance
- **White-Label Solutions**: Each organization gets customized branding, prompts, and agents
- **Enterprise Segmentation**: Isolate departments or business units
- **Per-Tenant Configuration**: Custom LLM models, RAG settings, and agent enablement

### Key Features

| Feature | Description |
|---------|-------------|
| **Organization Isolation** | Complete data separation per tenant |
| **Flexible Resolution** | Detect tenant from JWT, headers, or WhatsApp ID |
| **Per-Tenant RAG** | Isolated knowledge bases with pgvector |
| **Prompt Hierarchy** | 4-level override system (USER > ORG > GLOBAL > SYSTEM) |
| **LLM Customization** | Per-tenant model, temperature, and token limits |
| **Agent Configuration** | Enable/disable agents per organization |

---

## Architecture

### Tenant Resolution Flow

```
Request
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│               TenantContextMiddleware                    │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ 1. Check JWT Authorization header                   │ │
│  │    └─ Extract org_id/organization_id/tenant_id      │ │
│  │                                                     │ │
│  │ 2. Check X-Tenant-ID header (customizable)          │ │
│  │    └─ Direct organization UUID                      │ │
│  │                                                     │ │
│  │ 3. Check WhatsApp webhook wa_id                     │ │
│  │    └─ Lookup contact_domains table                  │ │
│  │                                                     │ │
│  │ 4. Fallback to System context (generic mode)        │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│                    TenantContext                         │
│  organization_id, config, enabled_domains, enabled_agents│
└─────────────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│              Tenant-Aware Services                       │
│  ┌────────────────┐ ┌────────────────┐ ┌──────────────┐ │
│  │TenantVectorStore│ │TenantPromptMgr │ │ TenantAgents │ │
│  │   (pgvector)    │ │  (4-level)     │ │ (per-org)    │ │
│  └────────────────┘ └────────────────┘ └──────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Core Components

#### TenantContext (`app/core/tenancy/context.py`)
Request-scoped context using Python's `contextvars` for thread-safe and async-safe propagation.

```python
from app.core.tenancy import get_tenant_context, require_tenant_context

# Get current tenant (may be None)
context = get_tenant_context()
if context:
    print(f"Organization: {context.organization_id}")
    print(f"Mode: {'multi-tenant' if context.is_multi_tenant_mode else 'generic'}")

# Require tenant (raises error if None)
context = require_tenant_context()
org_id = context.organization_id
```

**Key Properties:**
- `organization_id`: UUID of the current organization
- `is_multi_tenant_mode` / `is_generic_mode`: Operating mode
- `enabled_domains`, `enabled_agents`: Tenant configuration
- `rag_enabled`, `rag_similarity_threshold`, `rag_max_results`: RAG settings
- `llm_model`, `llm_temperature`, `llm_max_tokens`: LLM defaults

#### TenantContextMiddleware (`app/core/tenancy/middleware.py`)
Automatic tenant resolution from multiple sources.

**Resolution Priority:**
1. **JWT**: `org_id`, `organization_id`, or `tenant_id` claims
2. **Header**: `X-Tenant-ID` (configurable via `TENANT_HEADER`)
3. **WhatsApp**: `wa_id` from webhook → `contact_domains` table lookup
4. **System**: Fallback to system context for generic mode

**Skipped Paths:**
- `/health`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`
- `/static/*`

#### TenantResolver (`app/core/tenancy/resolver.py`)
Multi-source tenant resolution with validation.

```python
from app.core.tenancy import TenantResolver

resolver = TenantResolver(db_session)

# Resolve from JWT
context = await resolver.resolve_from_jwt(token_payload)

# Resolve from WhatsApp
context = await resolver.resolve_from_whatsapp(wa_id="5491112345678")

# Resolve from organization ID
context = await resolver.resolve_from_organization_id(org_id)
```

---

## Database Models

All tenancy models are in `app/models/db/tenancy/`.

### Organization

The core tenant entity with LLM configuration, quotas, and feature flags.

```python
class Organization(Base):
    id = Column(UUID, primary_key=True)
    slug = Column(String, unique=True)          # URL-friendly identifier
    name = Column(String)                        # Internal name
    display_name = Column(String)                # User-facing name
    mode = Column(String)                        # "generic" or "multi_tenant"
    status = Column(String)                      # "active", "suspended", "trial"

    # LLM Configuration (per-tenant)
    llm_model = Column(String)                   # e.g., "deepseek-r1:7b"
    llm_temperature = Column(Float)              # 0.0-2.0
    llm_max_tokens = Column(Integer)             # Max response tokens

    # Quotas
    max_users = Column(Integer)
    max_documents = Column(Integer)
    max_agents = Column(Integer)

    # Feature Flags
    features = Column(JSONB)                     # {"feature_x": true, ...}

    # Relationships
    users = relationship("OrganizationUser")
    config = relationship("TenantConfig", uselist=False)
    agents = relationship("TenantAgent")
    prompts = relationship("TenantPrompt")
    documents = relationship("TenantDocument")
```

### OrganizationUser

User memberships with roles and permissions.

```python
class OrganizationUser(Base):
    id = Column(UUID, primary_key=True)
    organization_id = Column(UUID, ForeignKey("organizations.id"))
    user_id = Column(UUID, ForeignKey("users.id"))
    role = Column(String)                        # "owner", "admin", "member"
    personal_settings = Column(JSONB)            # User-specific customizations

    # Permission Properties
    @property
    def is_owner(self) -> bool: ...

    @property
    def can_manage_agents(self) -> bool: ...     # owner or admin

    @property
    def can_manage_prompts(self) -> bool: ...    # owner or admin

    @property
    def can_upload_documents(self) -> bool: ...  # owner or admin

    @property
    def can_manage_users(self) -> bool: ...      # owner only
```

### TenantConfig

Per-tenant configuration for domains, agents, and RAG.

```python
class TenantConfig(Base):
    organization_id = Column(UUID, primary_key=True)

    # Domain Configuration
    enabled_domains = Column(ARRAY(String))      # ["ecommerce", "healthcare"]
    default_domain = Column(String)              # Fallback domain

    # Agent Configuration
    enabled_agent_types = Column(ARRAY(String))  # ["greeting_agent", "product_agent"]
    agent_timeout_seconds = Column(Integer)      # Operation timeout

    # RAG Configuration
    rag_enabled = Column(Boolean, default=True)
    rag_similarity_threshold = Column(Float)     # 0.0-1.0
    rag_max_results = Column(Integer)            # Max search results

    # Integration
    whatsapp_phone_number_id = Column(String)    # Tenant-specific WhatsApp
    whatsapp_verify_token = Column(String)

    # Advanced Settings
    advanced_config = Column(JSONB)
```

### TenantAgent

Per-tenant agent customization.

```python
class TenantAgent(Base):
    id = Column(UUID, primary_key=True)
    organization_id = Column(UUID, ForeignKey("organizations.id"))
    agent_key = Column(String)                   # e.g., "product_agent"
    agent_type = Column(String)                  # "domain", "specialized", "custom"
    display_name = Column(String)
    description = Column(String)
    enabled = Column(Boolean)
    priority = Column(Integer)                   # Routing priority
    keywords = Column(ARRAY(String))             # Trigger keywords
    intent_patterns = Column(JSONB)              # Pattern matching config
    config = Column(JSONB)                       # Agent-specific settings
```

### TenantPrompt

Prompt overrides at organization or user level.

```python
class TenantPrompt(Base):
    id = Column(UUID, primary_key=True)
    organization_id = Column(UUID, ForeignKey("organizations.id"))
    prompt_key = Column(String)                  # Key from PromptRegistry
    scope = Column(String)                       # "org" or "user"
    user_id = Column(UUID, nullable=True)        # Only for scope="user"
    template = Column(Text)                      # Prompt with {variable} placeholders
    description = Column(Text)
    version = Column(String)                     # Semantic version
    meta_data = Column(JSONB)                    # temperature, max_tokens, model
    is_active = Column(Boolean)
```

### TenantDocument

Tenant-isolated RAG documents with vector embeddings.

```python
class TenantDocument(Base):
    id = Column(UUID, primary_key=True)
    organization_id = Column(UUID, ForeignKey("organizations.id"))
    title = Column(String)
    content = Column(Text)
    document_type = Column(String)               # "faq", "guide", "policy", etc.
    category = Column(String)
    tags = Column(ARRAY(String))

    # Vector Search
    embedding = Column(Vector(768))              # pgvector for semantic search
    search_vector = Column(TSVECTOR)             # PostgreSQL full-text search

    # Status
    active = Column(Boolean, default=True)
    sort_order = Column(Integer)
    meta_data = Column(JSONB)                    # author, source, language, etc.
```

---

## Tenant Isolation

### TenantVectorStore (`app/core/tenancy/vector_store.py`)

Multi-tenant aware vector store with automatic organization filtering.

```python
from app.core.tenancy import TenantVectorStore

vector_store = TenantVectorStore(db_session, embedding_service)

# Search automatically filters by current tenant
results = await vector_store.search(
    query="What products do you have?",
    limit=5,
    min_similarity=0.7
)

# Add documents for current tenant
await vector_store.add_documents([
    {"title": "FAQ", "content": "Our products include...", "document_type": "faq"}
])
```

**Features:**
- Automatic `WHERE organization_id = :org_id` filtering
- Per-tenant HNSW indexes for performance
- Configurable similarity thresholds per tenant
- Hybrid search (semantic + keyword)

### TenantPromptManager (`app/core/tenancy/prompt_manager.py`)

4-level prompt resolution hierarchy.

```
Resolution Order (highest priority first):
1. USER:   TenantPrompt(org_id, user_id, scope='user')
2. ORG:    TenantPrompt(org_id, scope='org')
3. GLOBAL: Prompt table (system-wide defaults)
4. SYSTEM: PromptRegistry (YAML files in codebase)
```

```python
from app.core.tenancy import TenantPromptManager

prompt_manager = TenantPromptManager(db_session)

# Get prompt (resolves through hierarchy)
template = await prompt_manager.get_prompt("greeting_prompt")

# Render with variables
rendered = await prompt_manager.render_prompt(
    "product_response",
    product_name="Laptop",
    price="$999"
)

# Set organization-level override
await prompt_manager.set_prompt(
    prompt_key="greeting_prompt",
    template="Welcome to {company_name}! How can I help you today?",
    scope="org"
)
```

---

## Admin APIs

All admin APIs require JWT authentication and appropriate permissions.

### Organizations API

**Base Path:** `/api/v1/admin/organizations`

#### List Organizations
```bash
GET /api/v1/admin/organizations
Authorization: Bearer $TOKEN
```

Response:
```json
{
  "organizations": [
    {
      "id": "uuid",
      "slug": "acme-corp",
      "name": "Acme Corp",
      "display_name": "Acme Corporation",
      "status": "active",
      "role": "owner"
    }
  ]
}
```

#### Create Organization
```bash
POST /api/v1/admin/organizations
Authorization: Bearer $TOKEN
Content-Type: application/json

{
  "name": "Acme Corp",
  "slug": "acme-corp",
  "display_name": "Acme Corporation",
  "llm_model": "deepseek-r1:7b",
  "llm_temperature": 0.7
}
```

#### Get Organization
```bash
GET /api/v1/admin/organizations/{org_id}
Authorization: Bearer $TOKEN
```

#### Update Organization
```bash
PATCH /api/v1/admin/organizations/{org_id}
Authorization: Bearer $TOKEN
Content-Type: application/json

{
  "display_name": "Acme Corp Updated",
  "llm_model": "llama3.2:1b"
}
```

#### Delete Organization
```bash
DELETE /api/v1/admin/organizations/{org_id}
Authorization: Bearer $TOKEN
```

### Configuration API

**Base Path:** `/api/v1/admin/organizations/{org_id}/config`

#### Get Configuration
```bash
GET /api/v1/admin/organizations/{org_id}/config
Authorization: Bearer $TOKEN
```

Response:
```json
{
  "enabled_domains": ["ecommerce"],
  "default_domain": "ecommerce",
  "enabled_agent_types": ["greeting_agent", "product_agent", "fallback_agent"],
  "rag_enabled": true,
  "rag_similarity_threshold": 0.7,
  "rag_max_results": 5
}
```

#### Update Configuration
```bash
PATCH /api/v1/admin/organizations/{org_id}/config
Authorization: Bearer $TOKEN
Content-Type: application/json

{
  "enabled_domains": ["ecommerce", "healthcare"],
  "rag_enabled": true,
  "rag_similarity_threshold": 0.8
}
```

#### Update Specific Settings
```bash
# Update LLM settings
PATCH /api/v1/admin/organizations/{org_id}/config/llm
Content-Type: application/json
{"llm_model": "deepseek-r1:7b", "llm_temperature": 0.5}

# Update RAG settings
PATCH /api/v1/admin/organizations/{org_id}/config/rag
Content-Type: application/json
{"rag_enabled": true, "rag_similarity_threshold": 0.75}

# Update enabled domains
PATCH /api/v1/admin/organizations/{org_id}/config/domains
Content-Type: application/json
{"enabled_domains": ["ecommerce", "healthcare"]}

# Update enabled agents
PATCH /api/v1/admin/organizations/{org_id}/config/agents
Content-Type: application/json
{"enabled_agent_types": ["greeting_agent", "product_agent"]}
```

### Agents API

**Base Path:** `/api/v1/admin/organizations/{org_id}/agents`

#### List Agents
```bash
GET /api/v1/admin/organizations/{org_id}/agents
Authorization: Bearer $TOKEN
```

#### Create Agent
```bash
POST /api/v1/admin/organizations/{org_id}/agents
Authorization: Bearer $TOKEN
Content-Type: application/json

{
  "agent_key": "custom_support",
  "agent_type": "specialized",
  "display_name": "Custom Support Agent",
  "enabled": true,
  "priority": 10,
  "keywords": ["help", "support", "issue"]
}
```

#### Update Agent
```bash
PATCH /api/v1/admin/organizations/{org_id}/agents/{agent_key}
Authorization: Bearer $TOKEN
Content-Type: application/json

{"enabled": false}
```

### Prompts API

**Base Path:** `/api/v1/admin/organizations/{org_id}/prompts`

#### List Prompts
```bash
GET /api/v1/admin/organizations/{org_id}/prompts
Authorization: Bearer $TOKEN
```

#### Create/Update Prompt Override
```bash
POST /api/v1/admin/organizations/{org_id}/prompts
Authorization: Bearer $TOKEN
Content-Type: application/json

{
  "prompt_key": "greeting_prompt",
  "scope": "org",
  "template": "Welcome to {company_name}! I'm your AI assistant.",
  "description": "Custom greeting for our organization"
}
```

#### Delete Prompt Override
```bash
DELETE /api/v1/admin/organizations/{org_id}/prompts/{prompt_key}
Authorization: Bearer $TOKEN
```

---

## Configuration Reference

### Environment Variables

```bash
# Multi-Tenancy Mode
MULTI_TENANT_MODE=true                    # Enable/disable multi-tenant mode
TENANT_HEADER=X-Tenant-ID                 # Header name for tenant resolution

# Database (shared by all tenants)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aynux
DB_USER=aynux
DB_PASSWORD=your_secure_password

# Default LLM (overridable per tenant)
OLLAMA_API_URL=http://localhost:11434
OLLAMA_API_MODEL=deepseek-r1:7b
OLLAMA_API_MODEL_EMBEDDING=nomic-embed-text

# Default RAG Settings (overridable per tenant)
USE_PGVECTOR=true
PGVECTOR_SIMILARITY_THRESHOLD=0.7
KNOWLEDGE_SIMILARITY_THRESHOLD=0.7

# Default Agents (overridable per tenant)
ENABLED_AGENTS=["greeting_agent","ecommerce_agent","fallback_agent","farewell_agent"]
```

---

## Usage Examples

### Complete Setup Workflow

```bash
# 1. Enable multi-tenant mode
export MULTI_TENANT_MODE=true

# 2. Register admin user
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "secure123", "name": "Admin User"}'

# 3. Login and get token
TOKEN=$(curl -s -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@acme.com", "password": "secure123"}' | jq -r '.access_token')

# 4. Create organization
ORG_ID=$(curl -s -X POST http://localhost:8001/api/v1/admin/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme",
    "display_name": "Acme Corporation",
    "llm_model": "deepseek-r1:7b",
    "llm_temperature": 0.7
  }' | jq -r '.id')

echo "Created organization: $ORG_ID"

# 5. Configure tenant
curl -X PATCH "http://localhost:8001/api/v1/admin/organizations/$ORG_ID/config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled_domains": ["ecommerce"],
    "enabled_agent_types": ["greeting_agent", "product_agent", "fallback_agent"],
    "rag_enabled": true,
    "rag_similarity_threshold": 0.75
  }'

# 6. Add custom prompt
curl -X POST "http://localhost:8001/api/v1/admin/organizations/$ORG_ID/prompts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_key": "greeting_prompt",
    "scope": "org",
    "template": "Welcome to Acme! I am your AI shopping assistant. How can I help you find the perfect product today?"
  }'

# 7. Map WhatsApp contact to organization
PGPASSWORD=your_password psql -h localhost -U aynux -d aynux -c "
  INSERT INTO contact_domains (wa_id, domain, organization_id, assigned_method, confidence)
  VALUES ('5491112345678', 'ecommerce', '$ORG_ID', 'admin', 1.0)
  ON CONFLICT (wa_id) DO UPDATE SET organization_id = EXCLUDED.organization_id;"

# 8. Test with tenant context
curl -X POST http://localhost:8001/api/v1/chat/message \
  -H "X-Tenant-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-123", "message": "Hello, what products do you have?"}'
```

### Testing Tenant Isolation

```bash
# Create second organization
ORG_B=$(curl -s -X POST http://localhost:8001/api/v1/admin/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Beta Inc", "slug": "beta"}' | jq -r '.id')

# Add document to Org A
curl -X POST "http://localhost:8001/api/v1/knowledge/documents" \
  -H "X-Tenant-ID: $ORG_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Acme Products", "content": "We sell laptops and phones", "document_type": "faq"}'

# Add document to Org B
curl -X POST "http://localhost:8001/api/v1/knowledge/documents" \
  -H "X-Tenant-ID: $ORG_B" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Beta Services", "content": "We provide consulting services", "document_type": "faq"}'

# Search as Org A - should only see Acme Products
curl "http://localhost:8001/api/v1/knowledge/search?query=products" \
  -H "X-Tenant-ID: $ORG_ID"

# Search as Org B - should only see Beta Services
curl "http://localhost:8001/api/v1/knowledge/search?query=services" \
  -H "X-Tenant-ID: $ORG_B"
```

---

## File Reference

```
app/
├── core/tenancy/                          # Core tenancy module
│   ├── __init__.py                        # Public API exports
│   ├── context.py                         # TenantContext (contextvars)
│   ├── middleware.py                      # TenantContextMiddleware
│   ├── resolver.py                        # TenantResolver
│   ├── vector_store.py                    # TenantVectorStore
│   └── prompt_manager.py                  # TenantPromptManager
│
├── models/db/tenancy/                     # Database models
│   ├── organization.py                    # Organization
│   ├── organization_user.py               # OrganizationUser
│   ├── tenant_config.py                   # TenantConfig
│   ├── tenant_agent.py                    # TenantAgent
│   ├── tenant_prompt.py                   # TenantPrompt
│   └── tenant_document.py                 # TenantDocument
│
├── api/routes/admin/                      # Admin APIs
│   ├── organizations.py                   # Organization CRUD
│   ├── tenant_config.py                   # Configuration management
│   ├── tenant_agents.py                   # Agent management
│   ├── tenant_prompts.py                  # Prompt overrides
│   └── org_users.py                       # User management
│
└── models/db/contact_domains.py           # WhatsApp ID → Organization mapping
```

---

## Troubleshooting

### Common Issues

**1. Tenant context is None**
```python
# Check if multi-tenant mode is enabled
from app.config.settings import get_settings
settings = get_settings()
print(f"Multi-tenant mode: {settings.MULTI_TENANT_MODE}")
```

**2. Organization not found**
```sql
-- Check if organization exists
SELECT id, slug, status FROM organizations WHERE slug = 'your-slug';
```

**3. WhatsApp contact not mapping**
```sql
-- Verify contact_domains mapping
SELECT wa_id, organization_id, domain FROM contact_domains WHERE wa_id = '5491112345678';
```

**4. RAG not returning tenant documents**
```sql
-- Check tenant documents exist
SELECT id, title, organization_id, active FROM tenant_documents
WHERE organization_id = 'your-org-uuid' AND active = true;
```

---

## See Also

- [Docker Deployment Guide](DOCKER_DEPLOYMENT.md) - Deploying Aynux with Docker
- [LangGraph Architecture](LangGraph.md) - Multi-agent system details
- [Testing Guide](TESTING_GUIDE.md) - Testing multi-tenant features
