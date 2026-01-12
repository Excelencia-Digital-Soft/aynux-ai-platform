# Pharmacy Domain

Business domain for pharmacy operations including debt management, confirmations, and invoice generation via external ERP integration.

## Architecture

```
WhatsApp Webhook
    │
    ▼
GraphRouter.check_bypass_routing()  ──► If bypass: Skip orchestrator
    │
    ▼
PharmacyOperationsAgent
    │
    ▼
PharmacyGraph (LangGraph subgraph)
    │
    ├── debt_check_node      → Check customer debt
    ├── confirmation_node    → Confirm debt
    └── invoice_generation_node → Generate invoice
    │
    ▼
PharmacyERPClient (httpx async) → External ERP API
```

## Agent: PharmacyOperationsAgent

This agent handles pharmacy debt workflows:

1. **Check Debt (Consulta Deuda)**: Query customer's outstanding debt from external ERP
2. **Confirm Debt (Confirmar)**: Customer confirms the debt amount
3. **Generate Invoice (Generar Factura)**: Generate invoice for confirmed debt

### Flow

```
User: "consultar mi deuda"
    │
    ▼
DebtCheckNode: Shows debt → "Tu deuda es $X. Confirma con SI"
    │
    ▼
User: "si"
    │
    ▼
ConfirmationNode: Confirms debt → "Deuda confirmada. Escribe FACTURA"
    │
    ▼
User: "factura"
    │
    ▼
InvoiceGenerationNode: Generates invoice → "Factura #XXX generada"
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PHARMACY_ERP_BASE_URL` | Base URL for Pharmacy ERP API | None |
| `PHARMACY_API_TOKEN` | Bearer token for authentication | None |
| `PHARMACY_ERP_TIMEOUT` | Request timeout in seconds | 30 |

### Example .env

```bash
# Pharmacy ERP Integration
PHARMACY_ERP_BASE_URL=https://pharmacy-erp.example.com/api
PHARMACY_API_TOKEN=your-bearer-token-here
PHARMACY_ERP_TIMEOUT=30
```

### Enabling the Agent

Enable `pharmacy_operations_agent` via the Admin UI:

1. Go to `/agent-catalog` in the admin panel
2. Click "Seed Builtin" if agents haven't been initialized
3. Find `pharmacy_operations_agent` in the list
4. Toggle the "Enabled" switch to ON

**Or via API:**
```bash
# 1. Seed builtin agents (if not done)
POST /api/v1/admin/agents/seed/builtin

# 2. Toggle agent enabled status
POST /api/v1/admin/agents/{agent_id}/toggle
```

## External ERP Endpoints

The `PharmacyERPClient` expects the following REST endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/customers/{customer_id}/debt` | Get customer debt |
| `POST` | `/api/v1/debts/{debt_id}/confirm` | Confirm debt |
| `POST` | `/api/v1/debts/{debt_id}/invoice` | Generate invoice |
| `GET` | `/api/v1/health` | Health check |

### Expected Response Formats

#### GET /customers/{id}/debt

```json
{
  "id": "debt-123",
  "customer_id": "5491155551234",
  "customer_name": "Juan Perez",
  "total_debt": 1500.00,
  "has_debt": true,
  "status": "pending",
  "due_date": "2024-12-31",
  "items": [
    {
      "description": "Medicamento A",
      "amount": 1000.00,
      "quantity": 2
    }
  ]
}
```

#### POST /debts/{id}/confirm

```json
{
  "status": "confirmed",
  "confirmed": true,
  "debt": { ... }
}
```

#### POST /debts/{id}/invoice

```json
{
  "invoice_number": "FAC-2024-001234",
  "total_amount": 1500.00,
  "pdf_url": "https://erp.example.com/invoices/FAC-2024-001234.pdf"
}
```

## Bypass Routing

For dedicated pharmacy WhatsApp numbers, configure bypass routing to skip the orchestrator:

### TenantConfig.advanced_config

```json
{
  "bypass_routing": {
    "enabled": true,
    "rules": [
      {
        "type": "phone_number_list",
        "phone_numbers": ["5491155551234", "5491155559999"],
        "target_agent": "pharmacy_operations_agent"
      },
      {
        "type": "whatsapp_phone_number_id",
        "phone_number_id": "1234567890",
        "target_agent": "pharmacy_operations_agent"
      }
    ]
  }
}
```

### Bypass Rule Types

| Type | Description |
|------|-------------|
| `phone_number_list` | Route specific phone numbers |
| `phone_number` | Route by pattern (supports `*` wildcard) |
| `whatsapp_phone_number_id` | Route by WhatsApp Business number ID |

## Directory Structure

```
app/domains/pharmacy/
├── __init__.py
├── README.md
├── agents/
│   ├── __init__.py
│   ├── pharmacy_operations_agent.py  # Main agent
│   ├── state.py                      # PharmacyState TypedDict
│   ├── graph.py                      # PharmacyGraph LangGraph
│   └── nodes/
│       ├── __init__.py
│       ├── debt_check_node.py
│       ├── confirmation_node.py
│       └── invoice_generation_node.py
├── application/
│   ├── __init__.py
│   ├── ports/
│   │   └── __init__.py               # IPharmacyERPPort Protocol
│   └── use_cases/
│       ├── __init__.py
│       ├── check_debt.py
│       ├── confirm_debt.py
│       └── generate_invoice.py
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── pharmacy_debt.py
│   │   └── pharmacy_invoice.py
│   └── value_objects/
│       ├── __init__.py
│       └── debt_status.py
└── infrastructure/
    └── __init__.py
```

## Domain Layer

### Entities

- **PharmacyDebt**: Aggregate root for debt with status transitions
- **PharmacyInvoice**: Invoice entity with PDF URL support
- **DebtItem**: Line item within a debt
- **InvoiceItem**: Line item within an invoice

### Value Objects

- **DebtStatus**: Enum with states: `PENDING`, `CONFIRMED`, `INVOICED`, `PAID`, `CANCELLED`

## Application Layer

### Ports

- **IPharmacyERPPort**: Protocol interface for ERP integration

### Use Cases

| Use Case | Purpose |
|----------|---------|
| `CheckDebtUseCase` | Query customer debt from ERP |
| `ConfirmDebtUseCase` | Confirm debt in ERP |
| `GenerateInvoiceUseCase` | Generate invoice for confirmed debt |

## Infrastructure Layer

- **PharmacyERPClient**: httpx async client for external ERP (`app/clients/pharmacy_erp_client.py`)

## Testing

```bash
# Run pharmacy domain tests
uv run pytest tests/domains/pharmacy/ -v

# Test with specific ERP URL
PHARMACY_ERP_BASE_URL=http://localhost:8080 uv run pytest tests/domains/pharmacy/
```

## Keywords for Intent Detection

The orchestrator uses these keywords to route to `pharmacy_operations_agent`:

- `deuda`, `farmacia`, `saldo`, `factura`, `confirmar`, `cuenta`, `pendiente`, `debo`

## Integration with Main Graph

The agent is registered in:

1. `app/core/schemas/agent_schema.py` - `AgentType.PHARMACY_OPERATIONS_AGENT`
2. `app/core/agents/builtin_agents.py` - Default configuration
3. `app/core/graph/factories/agent_factory.py` - Class registration

**Enable via database** (not environment variable):

1. **Seed builtin agents** (if not done): `POST /admin/agents/seed/builtin`
2. **Enable in UI**: Go to `/agent-catalog` and toggle `pharmacy_operations_agent` ON
3. **Or via API**: `POST /admin/agents/{agent_id}/toggle`

The agent must be enabled in `core.agents` table with `enabled=true`.

## Development Rules

See `CLAUDE.md` for critical development rules including:

- **Section 5**: Prompt service usage - all prompts in `app/prompts/templates/pharmacy/`
- **Section 6**: Database-driven spaCy intent patterns - NO hardcoding
