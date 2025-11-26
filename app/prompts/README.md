# Sistema de Gestión Centralizada de Prompts

Sistema profesional para gestionar prompts de AI con soporte para archivos estáticos y prompts dinámicos en base de datos.

## 🎯 Características

- ✅ **Prompts Centralizados**: Todos los prompts en un solo lugar
- ✅ **Gestión Híbrida**: Archivos YAML (estáticos) + Base de datos (dinámicos)
- ✅ **Sistema de Templates**: Variables con renderizado automático
- ✅ **Versionado Completo**: Historial de cambios y rollback
- ✅ **Caché Inteligente**: Performance optimizada con LRU cache
- ✅ **Type-Safe Registry**: Autocompletado y validación de claves
- ✅ **API REST**: Gestión completa vía API
- ✅ **A/B Testing**: Soporte para experimentar con versiones

## 📁 Estructura

```
app/prompts/
├── __init__.py              # Exports principales
├── manager.py               # PromptManager - Manager principal
├── loader.py                # PromptLoader - Carga desde archivos/BD
├── registry.py              # PromptRegistry - Registro de claves
├── templates/               # Prompts estáticos en YAML
│   ├── intent/
│   │   └── analyzer.yaml
│   ├── product/
│   │   ├── search.yaml
│   │   └── sql.yaml
│   ├── conversation/
│   │   ├── general.yaml
│   │   └── sales.yaml
│   └── orchestrator/
│       └── main.yaml
├── utils/
│   ├── renderer.py          # Renderizado de templates
│   └── validator.py         # Validación de prompts
└── examples/
    ├── usage_example.py
    └── intent_router_migration.py
```

## 🚀 Inicio Rápido

### 1. Instalación

El sistema ya está integrado en el proyecto. Solo necesitas:

```python
from app.prompts import PromptManager, PromptRegistry
```

### 2. Uso Básico

```python
# Inicializar el manager
manager = PromptManager()

# Obtener un prompt simple
system_prompt = await manager.get_prompt(
    PromptRegistry.INTENT_ANALYZER_SYSTEM
)

# Obtener un prompt con variables
user_prompt = await manager.get_prompt(
    PromptRegistry.INTENT_ANALYZER_USER,
    variables={
        "customer_data": customer_data,
        "context_info": context_info,
        "message": user_message
    }
)

# Usar con Ollama
response = await ollama.generate_response(
    system_prompt=system_prompt,
    user_prompt=user_prompt
)
```

### 3. Crear Prompt Dinámico

```python
# Crear nuevo prompt editable
prompt = await manager.save_dynamic_prompt(
    key="product.custom.analysis",
    name="Análisis Personalizado",
    template="""
    Analiza el producto: {product_name}
    Precio: {price}
    Stock: {stock}

    Genera análisis de competitividad.
    """,
    metadata={"temperature": 0.6, "max_tokens": 400}
)

# Usar el prompt
rendered = await manager.get_prompt(
    "product.custom.analysis",
    variables={
        "product_name": "Laptop HP",
        "price": "45000",
        "stock": "5"
    }
)
```

## 📝 Formato de Archivos YAML

```yaml
# Archivo: app/prompts/templates/product/search.yaml

prompts:
  - key: product.search.intent_analysis
    name: Product Search Intent Analysis
    description: Analyzes user intention for product searches
    version: "1.0.0"
    template: |
      # ANÁLISIS DE INTENCIÓN

      ## MENSAJE: "{message}"
      ## CONTEXTO: {user_context}

      Analiza y responde en JSON...

    metadata:
      temperature: 0.3
      max_tokens: 800
      model: "deepseek-r1:7b"
```

## 🔧 API Endpoints

### Listar Prompts
```bash
GET /api/v1/admin/prompts?domain=product&is_dynamic=true
```

### Obtener Prompt
```bash
GET /api/v1/admin/prompts/product.search.intent_analysis
```

### Crear Prompt Dinámico
```bash
POST /api/v1/admin/prompts
Content-Type: application/json

{
  "key": "product.custom.analysis",
  "name": "Custom Analysis",
  "template": "Analyze {product}...",
  "metadata": {"temperature": 0.6}
}
```

### Actualizar Prompt
```bash
PUT /api/v1/admin/prompts/product.custom.analysis
Content-Type: application/json

{
  "template": "New template with {variables}..."
}
```

### Ver Versiones
```bash
GET /api/v1/admin/prompts/product.custom.analysis/versions
```

### Rollback
```bash
POST /api/v1/admin/prompts/product.custom.analysis/rollback
Content-Type: application/json

{
  "version_id": "uuid-de-la-version"
}
```

### Estadísticas
```bash
GET /api/v1/admin/prompts/system/stats
```

## 🔄 Migración de Código Existente

### ANTES (código antiguo):
```python
def analyze_intent(message, context):
    system_prompt = """
    You are an expert intent classifier...
    """

    user_prompt = f"""
    Message: {message}
    Context: {context}
    """

    return await ollama.generate(system_prompt, user_prompt)
```

### DESPUÉS (con PromptManager):
```python
def analyze_intent(message, context):
    system_prompt = await self.prompt_manager.get_prompt(
        PromptRegistry.INTENT_ANALYZER_SYSTEM
    )

    user_prompt = await self.prompt_manager.get_prompt(
        PromptRegistry.INTENT_ANALYZER_USER,
        variables={"message": message, "context": context}
    )

    return await ollama.generate(system_prompt, user_prompt)
```

## 📊 Beneficios

| Característica | Antes | Después |
|----------------|-------|---------|
| **Mantenibilidad** | Prompts en código | Prompts en YAML |
| **Versionado** | ❌ No | ✅ Completo |
| **Performance** | ❌ Sin caché | ✅ Caché LRU |
| **Flexibilidad** | ❌ Redeploy | ✅ Sin redeploy |
| **Colaboración** | ❌ Solo devs | ✅ Todo el equipo |
| **Testing** | ❌ Difícil | ✅ A/B testing |
| **Auditoría** | ❌ No | ✅ Completa |

## 🔍 PromptRegistry

El `PromptRegistry` proporciona constantes type-safe para todas las claves:

```python
# Autocompletado y validación
PromptRegistry.INTENT_ANALYZER_SYSTEM
PromptRegistry.PRODUCT_SEARCH_INTENT
PromptRegistry.SALES_ASSISTANT_SYSTEM

# Utilidades
all_keys = PromptRegistry.get_all_keys()
product_keys = PromptRegistry.get_by_domain("product")
is_valid = PromptRegistry.validate_key("product.search.intent")
```

## 🧪 Testing

```bash
# Ejecutar tests
pytest tests/test_prompt_system.py -v

# Tests específicos
pytest tests/test_prompt_system.py::TestPromptManager -v

# Con coverage
pytest tests/test_prompt_system.py --cov=app/prompts
```

## 📖 Ejemplos Completos

Ver archivos de ejemplo en `app/prompts/examples/`:
- `usage_example.py`: Ejemplos básicos de uso
- `intent_router_migration.py`: Guía de migración paso a paso

## 🛠️ Configuración

```python
# Custom configuration
manager = PromptManager(
    cache_size=1000,      # Máximo 1000 prompts en caché
    cache_ttl=7200        # TTL de 2 horas
)
```

## 🔐 Base de Datos

### Ejecutar Migración

```bash
# PostgreSQL
psql -h localhost -U usuario -d database -f app/scripts/migrations/002_create_prompts_tables.sql
```

### Tablas Creadas

- `prompts`: Almacena prompts activos
- `prompt_versions`: Historial de versiones

## 🚀 Producción

### Consideraciones de Despliegue

1. **Ejecutar migración de BD**: `002_create_prompts_tables.sql`
2. **Configurar caché**: Ajustar `cache_size` y `cache_ttl` según carga esperada
3. **Monitorear performance**: Revisar `/api/v1/admin/prompts/system/stats`
4. **Backup de prompts**: Implementar respaldo para prompts dinámicos
5. **Permisos API**: Los endpoints admin requieren autenticación apropiada

### Migración Gradual

- **No rompe código existente**: Sistema compatible con código antiguo
- **Migrar por servicios**: Actualizar servicios uno por uno
- **Testing exhaustivo**: Verificar cada servicio migrado
- **Rollback disponible**: Versionado permite revertir cambios

## 📈 Estado de Migración

### Agentes Migrados (~90%)

| Agente | Estado | Fecha |
|--------|--------|-------|
| ProductAgent | ✅ Migrado | 2025-01 |
| SuperOrchestrator | ✅ Migrado | 2025-01 |
| FarewellAgent | ✅ Creado con PromptManager | 2025-01 |
| FallbackAgent | ✅ Creado con PromptManager | 2025-01 |
| ExcelenciaAgent | ✅ Creado con PromptManager | 2025-01 |
| SupervisorAgent | ✅ Creado con PromptManager | 2025-01 |
| CreditAgent | ✅ Ya usaba PromptManager | - |

### Pendiente

- [ ] Migrar agentes restantes según se necesiten
- [ ] Implementar A/B testing de prompts
- [ ] Dashboard de métricas de prompts

## 🤝 Contribuir

Para agregar nuevos prompts:

1. Crear archivo YAML en `templates/{domain}/`
2. Agregar clave en `PromptRegistry`
3. Documentar uso en este README
4. Crear tests

## 📞 Soporte

Para preguntas o issues:
- Revisar ejemplos en `app/prompts/examples/`
- Consultar tests en `tests/test_prompt_system.py`
- Ver API en `app/api/routes/admin/prompts.py`

---

**Versión**: 2.0.0
**Última actualización**: 2025-01
