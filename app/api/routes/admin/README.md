# Admin API Routes

Endpoints administrativos para gestión del sistema Aynux.

## Ollama Admin (`/api/v1/admin/ollama`)

Endpoints públicos para consultar modelos disponibles en Ollama con clasificación automática.

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/models` | Lista todos los modelos con clasificación LLM/embedding |
| `GET` | `/health` | Verifica estado del servicio Ollama |

### GET `/models`

Lista modelos disponibles en Ollama, clasificándolos automáticamente como **LLM** o **embedding**.

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
      "name": "llama3.1:latest",
      "model": "llama3.1:latest",
      "family": "llama",
      "families": ["llama"],
      "parameter_size": "8.0B",
      "quantization_level": "Q4_K_M",
      "size_bytes": 4920753328,
      "model_type": "llm",
      "modified_at": "2025-10-17T02:02:45.661590805-03:00"
    },
    {
      "name": "nomic-embed-text:latest",
      "model": "nomic-embed-text:latest",
      "family": "nomic-bert",
      "families": ["nomic-bert"],
      "parameter_size": "137M",
      "quantization_level": "F16",
      "size_bytes": 274302450,
      "model_type": "embedding",
      "modified_at": "2025-10-17T13:34:20.719715012-03:00"
    }
  ],
  "total": 9,
  "llm_count": 5,
  "embedding_count": 4,
  "ollama_url": "http://localhost:11434"
}
```

#### Ejemplos

```bash
# Listar todos los modelos
curl http://localhost:8000/api/v1/admin/ollama/models

# Solo LLMs
curl "http://localhost:8000/api/v1/admin/ollama/models?model_type=llm"

# Solo embeddings
curl "http://localhost:8000/api/v1/admin/ollama/models?model_type=embedding"
```

### GET `/health`

Verifica el estado del servicio Ollama.

#### Response Schema

```json
{
  "status": "healthy",
  "ollama_url": "http://localhost:11434",
  "model_count": 9,
  "error": null
}
```

#### Estados

| Status | Descripción |
|--------|-------------|
| `healthy` | Ollama accesible y funcionando |
| `unhealthy` | Error de conexión o servicio no disponible |

#### Ejemplo

```bash
curl http://localhost:8000/api/v1/admin/ollama/health
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
