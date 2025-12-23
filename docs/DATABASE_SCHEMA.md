# Database Schema Reference - Aynux

> Last updated: 2024-12-23

## Overview

| Metric | Value |
|--------|-------|
| **Schemas** | 4 (core, ecommerce, healthcare, credit) |
| **Total Tables** | 43 |
| **Active Tables** | 35 |
| **Partially Used** | 5 |
| **Disabled (domain off)** | 6 |
| **Extensions** | pgvector, pgcrypto |

---

## Schema: `core` (17 tables)

System tables for multi-tenancy, knowledge base, conversations, and authentication.

| Table | Purpose | Status | Model Location |
|-------|---------|--------|----------------|
| `organizations` | Tenant root entities | **ACTIVE** | `app/models/db/tenancy/organization.py` |
| `users` | System authentication | **ACTIVE** | `app/models/db/user.py` |
| `organization_users` | User-org membership | **ACTIVE** | `app/models/db/tenancy/organization_user.py` |
| `tenant_configs` | Per-tenant settings (RAG, domains) | **ACTIVE** | `app/models/db/tenancy/tenant_config.py` |
| `tenant_agents` | Per-tenant agent configuration | **ACTIVE** | `app/models/db/tenancy/tenant_agent.py` |
| `tenant_documents` | Isolated knowledge base per tenant | **ACTIVE** | `app/models/db/tenancy/tenant_document.py` |
| `tenant_prompts` | Custom prompts per org/user | **ACTIVE** | `app/models/db/tenancy/tenant_prompt.py` |
| `tenant_credentials` | Encrypted API credentials (pgcrypto) | **ACTIVE** | `app/models/db/tenancy/tenant_credentials.py` |
| `pharmacy_merchant_configs` | Mercado Pago + receipt config | **ACTIVE** | `app/models/db/tenancy/pharmacy_merchant_config.py` |
| `company_knowledge` | Global RAG knowledge base | **ACTIVE** | `app/models/db/knowledge_base.py` |
| `contact_domains` | WhatsApp contact-to-domain mapping | **ACTIVE** | `app/models/db/contact_domains.py` |
| `domain_configs` | Domain enable/disable configuration | **ACTIVE** | `app/models/db/contact_domains.py` |
| `conversation_contexts` | Conversation context with rolling summary | **ACTIVE** | `app/models/db/conversation_history.py` |
| `conversation_messages` | Individual message history | **ACTIVE** | `app/models/db/conversation_history.py` |
| `support_tickets` | User support/feedback tickets | **ACTIVE** | `app/models/db/support_ticket.py` |
| `prompts` | Global prompt templates | **ACTIVE** | `app/models/db/prompts.py` |
| `prompt_versions` | Prompt versioning (A/B testing) | **ACTIVE** | `app/models/db/prompts.py` |

---

## Schema: `ecommerce` (18 tables)

E-commerce domain tables for product catalog, customers, orders, and analytics.

| Table | Purpose | Status | Model Location |
|-------|---------|--------|----------------|
| `products` | Product catalog (pgvector embeddings) | **ACTIVE** | `app/models/db/catalog.py` |
| `categories` | Product categories | **ACTIVE** | `app/models/db/catalog.py` |
| `subcategories` | Product subcategories | **ACTIVE** | `app/models/db/catalog.py` |
| `brands` | Product brands | **ACTIVE** | `app/models/db/catalog.py` |
| `product_attributes` | Dynamic key-value attributes | **ACTIVE** | `app/models/db/catalog.py` |
| `product_images` | Product images (multiple per product) | **ACTIVE** | `app/models/db/catalog.py` |
| `product_promotions` | M:M association products-promotions | **ACTIVE** | `app/models/db/catalog.py` |
| `promotions` | Promotional campaigns/discounts | **ACTIVE** | `app/models/db/promotions.py` |
| `customers` | WhatsApp customer profiles | **ACTIVE** | `app/models/db/customers.py` |
| `orders` | Purchase orders | **ACTIVE** | `app/models/db/orders.py` |
| `order_items` | Order line items | **ACTIVE** | `app/models/db/orders.py` |
| `conversations` | E-commerce conversation sessions | **ACTIVE** | `app/models/db/conversations.py` |
| `messages` | Individual WhatsApp messages | **ACTIVE** | `app/models/db/conversations.py` |
| `product_inquiries` | Product queries (budget/specs) | **PARTIAL** | `app/models/db/inquiries.py` |
| `product_reviews` | Product reviews/ratings (1-5) | **PARTIAL** | `app/models/db/reviews.py` |
| `analytics` | Chatbot metrics by period | **ACTIVE** | `app/models/db/analytics.py` |
| `price_history` | Historical pricing | **PARTIAL** | `app/models/db/analytics.py` |
| `stock_movements` | Inventory movement log | **PARTIAL** | `app/models/db/analytics.py` |

---

## Schema: `healthcare` (3 tables)

Healthcare domain tables. **Disabled by default** - not in `ENABLED_AGENTS`.

| Table | Purpose | Status | Model Location |
|-------|---------|--------|----------------|
| `patients` | Patient records | **DISABLED** | `app/domains/healthcare/infrastructure/persistence/sqlalchemy/models.py` |
| `doctors` | Doctor profiles | **DISABLED** | `app/domains/healthcare/infrastructure/persistence/sqlalchemy/models.py` |
| `appointments` | Medical appointments | **DISABLED** | `app/domains/healthcare/infrastructure/persistence/sqlalchemy/models.py` |

---

## Schema: `credit` (3 tables)

Credit/finance domain tables. **Disabled by default** - not in `ENABLED_AGENTS`.

| Table | Purpose | Status | Model Location |
|-------|---------|--------|----------------|
| `credit_accounts` | Customer credit accounts | **DISABLED** | `app/domains/credit/infrastructure/persistence/sqlalchemy/models.py` |
| `payments` | Payment transactions | **DISABLED** | `app/domains/credit/infrastructure/persistence/sqlalchemy/models.py` |
| `payment_schedule_items` | Payment plan items | **DISABLED** | `app/domains/credit/infrastructure/persistence/sqlalchemy/models.py` |

---

## Vector Search Tables (pgvector)

Tables with semantic search capability using 768-dimensional embeddings (nomic-embed-text).

| Table | Column | Index Type | Purpose |
|-------|--------|------------|---------|
| `ecommerce.products` | `embedding` | HNSW (cosine) | Product semantic search |
| `core.company_knowledge` | `embedding` | HNSW (cosine) | Global RAG knowledge base |
| `core.tenant_documents` | `embedding` | HNSW (cosine) | Per-tenant RAG knowledge base |

---

## Full-Text Search Tables (TSVECTOR)

| Table | Column | Index |
|-------|--------|-------|
| `ecommerce.products` | `search_vector` | GIN |
| `core.company_knowledge` | `search_vector` | GIN |
| `core.tenant_documents` | `search_vector` | GIN |

---

## Encrypted Fields (pgcrypto)

| Table | Encrypted Columns |
|-------|-------------------|
| `core.tenant_credentials` | `whatsapp_access_token_encrypted`, `whatsapp_verify_token_encrypted`, `dux_api_key_encrypted`, `plex_api_pass_encrypted` |

---

## Usage by Operating Mode

### Global Mode (Default)

**Active Tables**:
- All `core.*` tables
- All `ecommerce.*` tables (catalog, customers, conversations)
- **NOT USED**: `healthcare.*`, `credit.*`

### Multi-tenant Mode

**Additional Tables Required**:
- `core.organizations` (root entity)
- All `core.tenant_*` tables (6 tables)
- `core.pharmacy_merchant_configs`
- All tables with `organization_id` FK

---

## Key Relationships

```
organizations (1) ──┬── (N) organization_users
                    ├── (1) tenant_configs
                    ├── (N) tenant_agents
                    ├── (N) tenant_documents
                    ├── (N) tenant_prompts
                    ├── (1) tenant_credentials
                    ├── (1) pharmacy_merchant_configs
                    └── (N) conversation_contexts

categories (1) ──── (N) subcategories
                └── (N) products

products (N) ──┬── (N) promotions (via product_promotions)
               ├── (N) product_attributes
               ├── (N) product_images
               └── (N) order_items

customers (1) ──┬── (N) orders
                ├── (N) conversations
                └── (N) product_reviews

orders (1) ──── (N) order_items

conversations (1) ──── (N) messages

conversation_contexts (1) ──── (N) conversation_messages
```

---

## Statistics

| Category | Count |
|----------|-------|
| Total Tables | 43 |
| Active (frequent use) | 30 |
| Partially Used | 5 |
| Disabled (domains off) | 6 |
| Association Tables (M:M) | 1 |
| Tables with Vector Search | 3 |
| Tables with Encryption | 1 |
