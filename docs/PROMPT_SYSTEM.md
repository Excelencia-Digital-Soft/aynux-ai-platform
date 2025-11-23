# Sistema de Prompts YAML - Aynux

## Descripción General

El sistema de prompts de Aynux es una arquitectura centralizada para gestionar todos los prompts de IA utilizados en el proyecto. Reemplaza los prompts hardcodeados con un sistema basado en archivos YAML que proporciona:

- **Centralización**: Todos los prompts en archivos YAML organizados por dominio
- **Versionado**: Control de versiones de prompts con semantic versioning
- **Validación**: Esquemas Pydantic para validación de estructura y variables
- **Renderizado**: Templates Jinja2 con sustitución de variables
- **Rendimiento**: Sistema de caché para carga rápida
- **Mantenibilidad**: Separación clara entre lógica de negocio y contenido de prompts

## Arquitectura

### Componentes Principales

```
app/prompts/
├── models.py          # Esquemas Pydantic para validación
├── loader.py          # Carga prompts desde archivos YAML
├── renderer.py        # Renderiza templates con variables (Jinja2)
├── registry.py        # Registro centralizado de prompts
├── service.py         # Servicio unificado de alto nivel
└── templates/         # Archivos YAML organizados por dominio
    ├── domains/
    │   ├── ecommerce/
    │   │   ├── sales.yaml
    │   │   └── agents.yaml
    │   ├── credit/
    │   └── hospital/
    └── shared/
        ├── orchestrator.yaml
        └── conversation.yaml
```

### Flujo de Datos

```
YAML File → PromptLoader → PromptRegistry → UnifiedPromptService → Rendered Prompt
                                           ↓
                                      PromptRenderer
                                      (Variables)
```

## Uso

### Método Recomendado (UnifiedPromptService)

```python
from app.prompts import UnifiedPromptService

# Obtener instancia singleton
service = UnifiedPromptService.get_instance()

# Renderizar un prompt con variables
rendered = service.render(
    "ecommerce.sales.assistant",
    message="Busco una laptop",
    historial="Usuario: Hola\nAsistente: ¡Hola! ¿En qué puedo ayudarte?",
    contexto="Productos disponibles: HP Pavilion $800, Dell XPS $1200"
)

# Usar el prompt renderizado
response = llm.invoke(rendered)
```

### Listar Prompts Disponibles

```python
# Listar todos los prompts
all_prompts = service.list_available_prompts()
print(all_prompts)
# ['ecommerce.sales.assistant', 'shared.orchestrator.intent_detection', ...]

# Obtener prompts por dominio
ecommerce_prompts = service.get_prompts_by_domain("ecommerce")

# Obtener prompts por agente
product_prompts = service.get_prompts_by_agent("product")

# Obtener estadísticas
stats = service.get_stats()
print(f"Prompts cargados: {stats['prompts_loaded']}")
print(f"Dominios: {stats['domains']}")
```

### Obtener un Prompt sin Renderizar

```python
# Obtener template de prompt
template = service.get_prompt("ecommerce.sales.assistant")

print(f"Key: {template.key}")
print(f"Version: {template.version}")
print(f"Description: {template.description}")
print(f"Required variables: {template.get_required_variables()}")
```

## Formato de Archivos YAML

### Estructura Básica

```yaml
prompts:
  - key: domain.agent.action
    name: Human Readable Name
    description: What this prompt does
    version: "1.0.0"
    template: |
      Your prompt text here with {variables}.

      Can be multi-line.

      Use {variable_name} for substitution.
    metadata:
      temperature: 0.7
      max_tokens: 500
      model: "deepseek-r1:7b"
      domain: "ecommerce"
      agent: "sales"
      language: "es"
      tags: ["sales", "conversational"]
    variables:
      - name: variable_name
        type: string
        required: true
        description: "What this variable represents"
      - name: optional_var
        type: string
        required: false
        default: "default value"
```

### Convenciones de Nombres

**Keys**: Formato jerárquico con puntos

```
{domain}.{agent}.{action}

Ejemplos:
- ecommerce.sales.assistant
- ecommerce.product.search_intent
- shared.conversation.greeting
- credit.balance.inquiry
```

**Dominios**:
- `ecommerce`: E-commerce / ventas
- `credit`: Sistema de crédito y cobranzas
- `hospital`: Sistema hospitalario
- `shared`: Prompts compartidos entre dominios

**Agentes Comunes**:
- `sales`, `product`, `category`, `promotions`, `tracking` (ecommerce)
- `balance`, `payment`, `collection` (credit)
- `greeting`, `farewell`, `support`, `fallback` (shared)

### Tipos de Variables

```yaml
variables:
  - name: text_var
    type: string
    required: true

  - name: number_var
    type: integer
    required: true

  - name: decimal_var
    type: float
    required: false
    default: 0.0

  - name: flag_var
    type: boolean
    required: false
    default: false

  - name: list_var
    type: list
    required: false

  - name: data_var
    type: dict
    required: false
```

## Migración de Prompts Hardcodeados

### Antes (Hardcoded)

```python
def build_sales_prompt(message: str, context: str) -> str:
    prompt = f"""
    You are a sales assistant.

    Context: {context}
    User message: {message}

    Provide a helpful response.
    """
    return prompt
```

### Después (YAML-based)

**1. Crear archivo YAML** (`app/prompts/templates/domains/ecommerce/sales.yaml`):

```yaml
prompts:
  - key: ecommerce.sales.assistant
    name: Sales Assistant Prompt
    description: Prompt for sales assistance
    version: "1.0.0"
    template: |
      You are a sales assistant.

      Context: {context}
      User message: {message}

      Provide a helpful response.
    variables:
      - name: message
        type: string
        required: true
      - name: context
        type: string
        required: true
```

**2. Actualizar código Python**:

```python
from app.prompts import UnifiedPromptService

service = UnifiedPromptService.get_instance()

def build_sales_prompt(message: str, context: str) -> str:
    return service.render(
        "ecommerce.sales.assistant",
        message=message,
        context=context
    )
```

## Mejores Prácticas

### 1. Organización de Prompts

- **Por dominio**: Agrupa prompts relacionados por dominio de negocio
- **Por agente**: Crea archivos separados para cada agente
- **Shared**: Usa `shared/` para prompts reutilizables entre dominios

### 2. Versionado

```yaml
version: "1.0.0"  # Major.Minor.Patch
```

- **Major**: Cambios incompatibles (ej: variables eliminadas)
- **Minor**: Nuevas funcionalidades (ej: variables nuevas opcionales)
- **Patch**: Correcciones menores de texto

### 3. Documentación

- **description**: Explica claramente qué hace el prompt
- **variables.description**: Documenta cada variable
- **tags**: Facilita búsqueda y categorización

### 4. Testing

- Define variables con valores de ejemplo claros
- Usa `required: true` para variables críticas
- Proporciona `default` para variables opcionales

### 5. Metadata

```yaml
metadata:
  temperature: 0.7      # Control de creatividad (0.0-2.0)
  max_tokens: 500       # Límite de tokens de respuesta
  model: "deepseek-r1:7b"  # Modelo LLM preferido
  domain: "ecommerce"   # Dominio de negocio
  agent: "sales"        # Agente responsable
  language: "es"        # Idioma de respuesta
  tags: ["sales", "conversational"]  # Tags para búsqueda
```

## Compatibilidad Hacia Atrás

El sistema mantiene compatibilidad con código existente a través de `PromptService`:

```python
from app.services.prompt_service import PromptService

# Este código antiguo sigue funcionando
service = PromptService()
prompt = service._build_improved_prompt(message, historial, contexto)
```

Internamente, `PromptService` ahora delega a `UnifiedPromptService` y usa los prompts YAML.

## Troubleshooting

### Error: "Prompt not found"

```python
# Verifica que el key existe
available = service.list_available_prompts()
print(available)

# Usa strict=False para evitar excepciones
result = service.render("my.prompt.key", strict=False, **vars)
```

### Error: "Missing required variables"

```python
# Verifica variables requeridas
template = service.get_prompt("my.prompt.key")
print(template.get_required_variables())

# Proporciona todas las variables
result = service.render(
    "my.prompt.key",
    var1="value1",
    var2="value2"
)
```

### Recargar Prompts

```python
# Recargar desde disco (útil en desarrollo)
service.reload()
```

### Ver Estadísticas

```python
stats = service.get_stats()
print(f"Prompts: {stats['prompts_loaded']}")
print(f"Dominios: {stats['domains']}")
print(f"Agentes: {stats['agents']}")
```

## Roadmap

### Implementado ✅
- Sistema de carga desde YAML
- Validación con Pydantic
- Renderizado con Jinja2
- Registro centralizado
- Compatibilidad hacia atrás
- Tests automatizados

### Próximos Pasos 🚀
- [ ] Migrar todos los prompts hardcodeados a YAML
- [ ] Soporte de prompts desde base de datos
- [ ] Sistema de A/B testing de prompts
- [ ] Métricas de rendimiento por prompt
- [ ] Interfaz web para gestión de prompts
- [ ] Versionado avanzado con rollback
- [ ] Multi-idioma con traducciones automáticas

## Referencias

- **Código**: `app/prompts/`
- **Tests**: `tests/test_prompt_service.py`
- **Templates**: `app/prompts/templates/`
- **Ejemplos**: Ver archivos YAML existentes en `app/prompts/templates/`

## Soporte

Para preguntas o problemas:
1. Revisa la documentación en `docs/PROMPT_SYSTEM.md`
2. Consulta los tests en `tests/test_prompt_service.py`
3. Revisa los ejemplos en `app/prompts/templates/`
