# Bypass Rules API - Frontend Guide

API para gestionar reglas de bypass routing que permiten dirigir conversaciones directamente a agentes específicos basándose en patrones de números de teléfono o IDs de WhatsApp.

## Base URL

```
/api/v1/admin/organizations/{org_id}/bypass-rules
```

## Autenticación

Todas las rutas requieren:
- Header `Authorization: Bearer {token}`
- Usuario con rol `admin` o `owner` en la organización

---

## Endpoints

### 1. Listar Reglas

```http
GET /{org_id}/bypass-rules
```

**Response** `200 OK`:
```json
{
  "rules": [
    {
      "id": "uuid",
      "organization_id": "uuid",
      "rule_name": "VIP Customers",
      "description": "Route VIP customers to support",
      "rule_type": "phone_number_list",
      "pattern": null,
      "phone_numbers": ["5491155551234", "5491155554321"],
      "phone_number_id": null,
      "target_agent": "support_agent",
      "target_domain": "excelencia",
      "priority": 10,
      "enabled": true,
      "created_at": "2025-12-28T16:57:41.947116+00:00",
      "updated_at": "2025-12-28T16:57:41.947119+00:00"
    }
  ],
  "total": 1,
  "enabled_count": 1,
  "disabled_count": 0
}
```

> Las reglas se devuelven ordenadas por `priority` descendente (mayor prioridad primero).

---

### 2. Crear Regla

```http
POST /{org_id}/bypass-rules
Content-Type: application/json
```

**Request Body**:
```json
{
  "rule_name": "VIP Customers",
  "description": "Optional description",
  "rule_type": "phone_number_list",
  "phone_numbers": ["5491155551234", "5491155554321"],
  "target_agent": "support_agent",
  "target_domain": "excelencia",
  "priority": 10,
  "enabled": true
}
```

**Response** `201 Created`: Objeto `BypassRule` completo.

#### Tipos de Regla (`rule_type`)

| Tipo | Campo Requerido | Descripción |
|------|-----------------|-------------|
| `phone_number` | `pattern` | Patrón con wildcard (`549*`, `5491155*`) |
| `phone_number_list` | `phone_numbers` | Lista exacta de números |
| `whatsapp_phone_number_id` | `phone_number_id` | ID del número de WhatsApp Business |

**Ejemplos por tipo**:

```json
// phone_number - con wildcard
{
  "rule_name": "Argentina Numbers",
  "rule_type": "phone_number",
  "pattern": "549*",
  "target_agent": "spanish_agent"
}

// phone_number_list - lista exacta
{
  "rule_name": "VIP List",
  "rule_type": "phone_number_list",
  "phone_numbers": ["5491155551234", "5491155554321"],
  "target_agent": "vip_agent"
}

// whatsapp_phone_number_id - por ID de WhatsApp
{
  "rule_name": "Pharmacy Line",
  "rule_type": "whatsapp_phone_number_id",
  "phone_number_id": "123456789012345",
  "target_agent": "pharmacy_agent"
}
```

---

### 3. Obtener Regla

```http
GET /{org_id}/bypass-rules/{rule_id}
```

**Response** `200 OK`: Objeto `BypassRule`.

**Errors**:
- `404 Not Found`: Regla no existe o no pertenece a la organización.

---

### 4. Actualizar Regla

```http
PUT /{org_id}/bypass-rules/{rule_id}
Content-Type: application/json
```

**Request Body** (todos los campos son opcionales):
```json
{
  "rule_name": "Updated Name",
  "description": "Updated description",
  "priority": 20,
  "enabled": false
}
```

**Response** `200 OK`: Objeto `BypassRule` actualizado.

> **Nota**: Para cambiar `rule_type`, se recomienda eliminar y crear nueva regla.

---

### 5. Eliminar Regla

```http
DELETE /{org_id}/bypass-rules/{rule_id}
```

**Response** `204 No Content`

---

### 6. Activar/Desactivar Regla

```http
POST /{org_id}/bypass-rules/{rule_id}/toggle
```

**Response** `200 OK`: Objeto `BypassRule` con `enabled` invertido.

---

### 7. Probar Routing

Simula el matching sin procesar mensaje real.

```http
POST /{org_id}/bypass-rules/test
Content-Type: application/json
```

**Request Body**:
```json
{
  "wa_id": "5491155551234",
  "whatsapp_phone_number_id": "123456789012345"
}
```

> `whatsapp_phone_number_id` es opcional.

**Response** `200 OK`:
```json
{
  "matched": true,
  "matched_rule": {
    "id": "uuid",
    "rule_name": "VIP Customers",
    "target_agent": "support_agent",
    "target_domain": "excelencia",
    "priority": 10
  },
  "target_agent": "support_agent",
  "target_domain": "excelencia",
  "evaluation_order": [
    "VIP Customers",
    "Argentina Numbers",
    "Default Rule"
  ]
}
```

**Sin match**:
```json
{
  "matched": false,
  "matched_rule": null,
  "target_agent": null,
  "target_domain": null,
  "evaluation_order": ["VIP Customers", "Argentina Numbers"]
}
```

---

### 8. Reordenar Reglas

```http
POST /{org_id}/bypass-rules/reorder
Content-Type: application/json
```

**Request Body**:
```json
{
  "rule_ids": [
    "uuid-highest-priority",
    "uuid-second-priority",
    "uuid-lowest-priority"
  ]
}
```

**Response** `200 OK`: Lista completa con nuevas prioridades asignadas.

---

## Modelo de Datos

### BypassRule

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `id` | UUID | Auto | ID único |
| `organization_id` | UUID | Auto | Organización propietaria |
| `rule_name` | string(100) | Sí | Nombre único por org |
| `description` | string | No | Descripción opcional |
| `rule_type` | enum | Sí | `phone_number`, `phone_number_list`, `whatsapp_phone_number_id` |
| `pattern` | string(100) | Condicional | Patrón con wildcard (para `phone_number`) |
| `phone_numbers` | string[] | Condicional | Lista de números (para `phone_number_list`) |
| `phone_number_id` | string(100) | Condicional | WhatsApp ID (para `whatsapp_phone_number_id`) |
| `target_agent` | string(100) | Sí | Agente destino |
| `target_domain` | string(50) | No | Dominio destino (usa default si null) |
| `priority` | integer | No | Mayor = evalúa primero (default: 0) |
| `enabled` | boolean | No | Activa/inactiva (default: true) |
| `created_at` | datetime | Auto | Fecha creación |
| `updated_at` | datetime | Auto | Última modificación |

---

## Lógica de Evaluación

1. Las reglas se evalúan en orden de **prioridad descendente** (mayor primero)
2. Solo se evalúan reglas con `enabled: true`
3. La **primera regla que matchea** gana
4. Si ninguna regla matchea, se usa el routing normal del orquestador

### Patrones de Matching

| Tipo | Pattern | Matchea | No Matchea |
|------|---------|---------|------------|
| `phone_number` | `549*` | `5491155551234` | `5411234567` |
| `phone_number` | `549115555*` | `5491155551234` | `5491166661234` |
| `phone_number_list` | `["549...1234"]` | `5491155551234` | `5491155554321` |
| `whatsapp_phone_number_id` | `123456789` | ID exacto | Cualquier otro |

---

## Errores Comunes

| Status | Código | Descripción |
|--------|--------|-------------|
| 400 | `validation_error` | Campos inválidos o faltantes |
| 403 | `forbidden` | Usuario no es admin de la organización |
| 404 | `not_found` | Regla o organización no existe |
| 409 | `conflict` | `rule_name` duplicado en la organización |

**Ejemplo error 400**:
```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "phone_numbers"],
      "msg": "phone_numbers is required for rule_type 'phone_number_list'"
    }
  ]
}
```

---

## Ejemplo de Integración (Vue.js)

```typescript
// composables/useBypassRules.ts
import { ref } from 'vue'
import { api } from '@/lib/api'

interface BypassRule {
  id: string
  rule_name: string
  rule_type: 'phone_number' | 'phone_number_list' | 'whatsapp_phone_number_id'
  pattern?: string
  phone_numbers?: string[]
  phone_number_id?: string
  target_agent: string
  target_domain?: string
  priority: number
  enabled: boolean
}

export function useBypassRules(orgId: string) {
  const rules = ref<BypassRule[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchRules() {
    loading.value = true
    try {
      const { data } = await api.get(`/admin/organizations/${orgId}/bypass-rules`)
      rules.value = data.rules
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createRule(rule: Partial<BypassRule>) {
    const { data } = await api.post(`/admin/organizations/${orgId}/bypass-rules`, rule)
    rules.value.unshift(data)
    return data
  }

  async function updateRule(ruleId: string, updates: Partial<BypassRule>) {
    const { data } = await api.put(
      `/admin/organizations/${orgId}/bypass-rules/${ruleId}`,
      updates
    )
    const index = rules.value.findIndex(r => r.id === ruleId)
    if (index !== -1) rules.value[index] = data
    return data
  }

  async function deleteRule(ruleId: string) {
    await api.delete(`/admin/organizations/${orgId}/bypass-rules/${ruleId}`)
    rules.value = rules.value.filter(r => r.id !== ruleId)
  }

  async function toggleRule(ruleId: string) {
    const { data } = await api.post(
      `/admin/organizations/${orgId}/bypass-rules/${ruleId}/toggle`
    )
    const index = rules.value.findIndex(r => r.id === ruleId)
    if (index !== -1) rules.value[index] = data
    return data
  }

  async function testRouting(waId: string, phoneNumberId?: string) {
    const { data } = await api.post(
      `/admin/organizations/${orgId}/bypass-rules/test`,
      { wa_id: waId, whatsapp_phone_number_id: phoneNumberId }
    )
    return data
  }

  return {
    rules,
    loading,
    error,
    fetchRules,
    createRule,
    updateRule,
    deleteRule,
    toggleRule,
    testRouting
  }
}
```

---

## Notas de Implementación

### Prioridad
- Usar valores espaciados (10, 20, 30) para facilitar inserción
- El endpoint `/reorder` reasigna prioridades automáticamente

### Agentes Disponibles
Consultar `/api/v1/admin/agents/available` para lista de agentes válidos.

### Dominios Disponibles
- `excelencia` (default)
- `healthcare`
- `credit`
- `ecommerce` (si está habilitado)

### Fallback
Si `target_domain` es null, se usa `tenant_config.default_domain` de la organización.
