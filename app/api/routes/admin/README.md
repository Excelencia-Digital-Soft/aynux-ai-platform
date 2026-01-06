# Admin API Routes

Endpoints administrativos para gestión del sistema Aynux.

## LLM Admin (`/api/v1/admin/llm`)

Endpoints públicos para consultar modelos disponibles en vLLM con clasificación automática.

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/models` | Lista todos los modelos con clasificación LLM/embedding |
| `GET` | `/health` | Verifica estado del servicio vLLM |

### GET `/models`

Lista modelos disponibles en vLLM, clasificándolos automáticamente como **LLM** o **embedding**.

#### Query Parameters

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `model_type` | `llm` \| `embedding` | No | Filtrar por tipo de modelo |

#### Algoritmo de Clasificación

```
1. Si family contiene "bert" → embedding
2. Si name contiene "embed" → embedding
3. Resto → llm
```

#### Response Schema

```json
{
  "models": [
    {
      "name": "qwen-3b",
      "model": "qwen-3b",
      "family": "qwen",
      "families": ["qwen"],
      "parameter_size": "3.0B",
      "quantization_level": "FP16",
      "size_bytes": 6000000000,
      "model_type": "llm",
      "modified_at": "2025-10-17T02:02:45.661590805-03:00"
    },
    {
      "name": "BAAI/bge-m3",
      "model": "BAAI/bge-m3",
      "family": "bert",
      "families": ["bert"],
      "parameter_size": "568M",
      "quantization_level": "FP16",
      "size_bytes": 1136000000,
      "model_type": "embedding",
      "modified_at": "2025-10-17T13:34:20.719715012-03:00"
    }
  ],
  "total": 2,
  "llm_count": 1,
  "embedding_count": 1,
  "vllm_url": "http://localhost:8090/v1"
}
```

#### Ejemplos

```bash
# Listar todos los modelos
curl http://localhost:8000/api/v1/admin/llm/models

# Solo LLMs
curl "http://localhost:8000/api/v1/admin/llm/models?model_type=llm"

# Solo embeddings
curl "http://localhost:8000/api/v1/admin/llm/models?model_type=embedding"
```

### GET `/health`

Verifica el estado del servicio vLLM.

#### Response Schema

```json
{
  "status": "healthy",
  "vllm_url": "http://localhost:8090/v1",
  "model_count": 2,
  "error": null
}
```

#### Estados

| Status | Descripción |
|--------|-------------|
| `healthy` | vLLM accesible y funcionando |
| `unhealthy` | Error de conexión o servicio no disponible |

#### Ejemplo

```bash
curl http://localhost:8000/api/v1/admin/llm/health
```

---

## Otros Endpoints Admin

| Módulo | Prefijo | Descripción |
|--------|---------|-------------|
| `organizations` | `/admin/organizations` | Gestión de organizaciones |
| `org_users` | `/admin/organizations` | Usuarios por organización |
| `tenant_config` | `/admin/organizations` | Configuración por tenant |
| `tenant_agents` | `/admin/organizations` | Agentes por tenant |
| `tenant_prompts` | `/admin/organizations` | Prompts por tenant |
| `tenant_documents` | `/admin/organizations` | Documentos por tenant |
| `prompts` | `/admin/prompts` | Gestión global de prompts |
