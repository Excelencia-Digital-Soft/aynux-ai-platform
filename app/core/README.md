# Core Module - Núcleo del Sistema

El módulo `app/core/` contiene todos los componentes compartidos y reutilizables del sistema Aynux.
Es completamente independiente de los dominios de negocio y puede ser usado por cualquier parte de la aplicación.

## 📂 Estructura

```
app/core/
├── interfaces/       # Interfaces (Protocols) para Dependency Inversion
├── domain/          # Domain primitives (entities, value objects, events, exceptions)
├── infrastructure/  # Infraestructura común (circuit breaker, retry, rate limiter)
├── shared/          # Utilidades compartidas (JSON, language, phone, etc.)
└── config/          # Configuración central
```

---

## 🔌 Interfaces (SOLID - Dependency Inversion)

Las interfaces definen contratos que las implementaciones concretas deben cumplir.
Esto permite cambiar implementaciones sin modificar el código de negocio.

### Interfaces Disponibles

#### 1. **IRepository** (`interfaces/repository.py`)

Contrato para acceso a datos.

```python
from app.core.interfaces.repository import IRepository, ISearchableRepository

# Usar en servicios
class ProductService:
    def __init__(self, repo: IRepository[Product, int]):
        self.repo = repo

    async def get_product(self, id: int) -> Product:
        return await self.repo.find_by_id(id)
```

**Interfaces disponibles**:
- `IRepository[T, ID]` - CRUD básico
- `IReadOnlyRepository[T, ID]` - Solo lectura
- `ISearchableRepository[T, ID]` - Extiende IRepository con búsqueda y filtros
- `IKnowledgeRepository` - Knowledge base con embeddings
- `ICacheRepository[T]` - Con caching integrado

#### 2. **IAgent** (`interfaces/agent.py`)

Contrato para agentes LangGraph.

```python
from app.core.interfaces.agent import IAgent, AgentType

class ProductSearchAgent(IAgent):
    @property
    def agent_type(self) -> AgentType:
        return AgentType.PRODUCT_SEARCH

    @property
    def agent_name(self) -> str:
        return "Product Search Agent"

    async def execute(self, state: dict) -> dict:
        # Implementación
        return {"products": [...]}
```

**Interfaces disponibles**:
- `IAgent` - Base para todos los agentes
- `ISupervisorAgent` - Agentes supervisores con routing
- `IConversationalAgent` - Agentes conversacionales

#### 3. **ILLM** (`interfaces/llm.py`)

Contrato para Language Models.

```python
from app.integrations.llm import create_llm, LLMProvider

# Crear LLM
llm = create_llm(
    provider=LLMProvider.VLLM,
    model_name="qwen-3b",
    temperature=0.7
)

# Usar
response = await llm.generate("Tell me about Python")

# Chat
messages = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello!"}
]
response = await llm.generate_chat(messages)

# Streaming
async for token in llm.generate_stream("Tell me a story"):
    print(token, end="", flush=True)
```

**Interfaces disponibles**:
- `ILLM` - Base para LLM providers
- `IEmbeddingModel` - Modelos de embeddings
- `IChatLLM` - Chat con historial
- `IStructuredLLM` - Salida en JSON estructurado

#### 4. **IVectorStore** (`interfaces/vector_store.py`)

Contrato para vector stores (búsqueda semántica).

```python
from app.integrations.vector_stores import create_vector_store, VectorStoreType, Document

# Crear vector store
store = create_vector_store(
    store_type=VectorStoreType.PGVECTOR,
    collection_name="products",
    embedding_dimension=768
)

# Agregar documentos
docs = [
    Document(id="1", content="Laptop gaming HP", metadata={"price": 899}),
    Document(id="2", content="Mouse inalámbrico Logitech")
]
await store.add_documents(docs, generate_embeddings=True)

# Buscar
results = await store.search("laptop económica", top_k=5, min_score=0.7)
for result in results:
    print(f"{result.document.content} - Score: {result.score}")

# Buscar con filtros
results = await store.search(
    "laptop",
    filter_metadata={"category_id": 1, "price_max": 1000}
)
```

**Interfaces disponibles**:
- `IVectorStore` - Base para vector stores
- `IHybridSearch` - Búsqueda híbrida (vectorial + keyword)
- `IVectorStoreMetrics` - Métricas y performance

#### 5. **ICache** (`interfaces/cache.py`)

Contrato para sistemas de caché.

```python
from app.core.interfaces.cache import ICache

class MyService:
    def __init__(self, cache: ICache):
        self.cache = cache

    async def get_product(self, id: int):
        # Intentar cache primero
        product = await self.cache.get(f"product:{id}")
        if product is None:
            product = await self.db.get_product(id)
            await self.cache.set(f"product:{id}", product, ttl=3600)
        return product
```

**Interfaces disponibles**:
- `ICache` - Base de caché
- `IAdvancedCache` - Operaciones avanzadas (get_many, increment)
- `IPatternCache` - Búsqueda por patrones
- `ICacheWithCallback` - get_or_set pattern
- `IMultiLayerCache` - Multi-layer (memory + redis)

---

## 🛠️ Shared Utilities

Utilidades compartidas en `app/core/shared/`.

### JSON Extractor

```python
from app.core.shared import extract_json_from_text, safe_json_parse

# Extraer JSON de texto
text = "Here is data: {\"name\": \"John\", \"age\": 30}"
data = extract_json_from_text(text)
# Result: {"name": "John", "age": 30}

# Parse seguro
result = safe_json_parse('{"valid": "json"}')
if result:
    print(result["valid"])
```

### Language Detector

```python
from app.core.shared import detect_language, LanguageDetector

# Detectar idioma
lang = await detect_language("Hello, how are you?")
# Result: "en"

lang = await detect_language("Hola, ¿cómo estás?")
# Result: "es"

# Batch detection
texts = ["Hello", "Hola", "Bonjour"]
langs = await detect_language_batch(texts)
# Result: ["en", "es", "fr"]

# Usar detector con configuración
detector = LanguageDetector(default_language="es")
lang = await detector.detect("Unknown text")
```

### Phone Normalizer

```python
from app.core.shared import normalize_phone, validate_phone

# Normalizar número
phone = normalize_phone("+54 11 1234-5678")
# Result: "+5411123456789"

phone = normalize_phone("(011) 1234-5678", country="AR")
# Result: "+5411123456789"

# Validar
is_valid = validate_phone("+5411123456789")
# Result: True
```

### Rate Limiter

```python
from app.core.shared import RateLimiter

# Crear rate limiter
limiter = RateLimiter(max_requests=100, time_window=60)  # 100 req/min

# Verificar límite
user_id = "user123"
if await limiter.is_allowed(user_id):
    # Procesar request
    pass
else:
    raise HTTPException(429, "Too many requests")
```

---

## 🏗️ Infrastructure

Componentes de infraestructura en `app/core/infrastructure/`.

### Circuit Breaker

```python
from app.core.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=httpx.HTTPError
)

@breaker
async def call_external_api():
    # Llamada a API externa
    response = await client.get("https://api.example.com")
    return response
```

### Retry Mechanism

```python
from app.core.infrastructure.retry import retry

@retry(max_attempts=3, delay=1.0, backoff=2.0)
async def unstable_operation():
    # Operación que puede fallar
    result = await some_api_call()
    return result
```

---

## 📋 Mejores Prácticas

### 1. Dependency Injection

**✅ CORRECTO** (depender de interfaces):
```python
from app.core.interfaces.llm import ILLM
from app.core.interfaces.vector_store import IVectorStore

class ProductSearchService:
    def __init__(
        self,
        llm: ILLM,
        vector_store: IVectorStore
    ):
        self.llm = llm
        self.vector_store = vector_store
```

**INCORRECTO** (depender de implementaciones):
```python
from app.integrations.llm.vllm import VllmLLM
from app.integrations.vector_stores.pgvector import PgVectorStore

class ProductSearchService:
    def __init__(self):
        self.llm = VllmLLM()  # Acoplamiento directo
        self.vector_store = PgVectorStore()  # Acoplamiento directo
```

### 2. Factory Pattern

**Usar factories para crear instancias**:
```python
from app.integrations.llm import create_llm, LLMProvider
from app.integrations.vector_stores import create_vector_store, VectorStoreType

# En dependencies.py
def get_llm() -> ILLM:
    return create_llm(provider=LLMProvider.VLLM)

def get_vector_store() -> IVectorStore:
    return create_vector_store(store_type=VectorStoreType.PGVECTOR)

# En routes
@router.post("/search")
async def search_products(
    llm: ILLM = Depends(get_llm),
    vector_store: IVectorStore = Depends(get_vector_store)
):
    # Usar interfaces
    results = await vector_store.search(query)
    ...
```

### 3. Testing con Mocks

```python
from unittest.mock import Mock
from app.core.interfaces.vector_store import IVectorStore

def test_product_search():
    # Arrange
    mock_store = Mock(spec=IVectorStore)
    mock_store.search.return_value = [mock_results]

    service = ProductService(vector_store=mock_store)

    # Act
    results = await service.search("laptop")

    # Assert
    assert len(results) > 0
    mock_store.search.assert_called_once_with("laptop")
```

---

## 📚 Ejemplos Completos

### Ejemplo 1: Servicio con Todas las Dependencias

```python
from app.core.interfaces.llm import ILLM
from app.core.interfaces.vector_store import IVectorStore
from app.core.interfaces.repository import IRepository
from app.core.interfaces.cache import ICache

class SmartProductService:
    """Servicio de productos con todas las dependencias inyectadas"""

    def __init__(
        self,
        product_repo: IRepository,
        vector_store: IVectorStore,
        llm: ILLM,
        cache: ICache
    ):
        self.product_repo = product_repo
        self.vector_store = vector_store
        self.llm = llm
        self.cache = cache

    async def search_products(self, query: str, top_k: int = 5):
        # 1. Intentar cache
        cache_key = f"search:{query}:{top_k}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # 2. Búsqueda vectorial
        vector_results = await self.vector_store.search(query, top_k=top_k)
        product_ids = [r.document.id for r in vector_results]

        # 3. Obtener productos completos
        products = []
        for pid in product_ids:
            product = await self.product_repo.find_by_id(int(pid))
            if product:
                products.append(product)

        # 4. Generar respuesta con LLM
        response = await self.llm.generate(
            f"Format these products for user: {products}"
        )

        # 5. Cachear resultado
        await self.cache.set(cache_key, response, ttl=300)

        return response
```

### Ejemplo 2: Dependency Injection en FastAPI

```python
# dependencies.py
from app.core.interfaces.llm import ILLM
from app.core.interfaces.vector_store import IVectorStore
from app.integrations.llm import create_llm, LLMProvider
from app.integrations.vector_stores import create_vector_store, VectorStoreType

def get_llm() -> ILLM:
    return create_llm(provider=LLMProvider.VLLM)

def get_vector_store() -> IVectorStore:
    return create_vector_store(store_type=VectorStoreType.PGVECTOR)

def get_smart_product_service(
    llm: ILLM = Depends(get_llm),
    vector_store: IVectorStore = Depends(get_vector_store),
    product_repo: IRepository = Depends(get_product_repo),
    cache: ICache = Depends(get_cache)
) -> SmartProductService:
    return SmartProductService(product_repo, vector_store, llm, cache)

# routes.py
@router.post("/products/search")
async def search_products(
    query: str,
    service: SmartProductService = Depends(get_smart_product_service)
):
    results = await service.search_products(query)
    return {"results": results}
```

---

## 🎯 Beneficios de esta Arquitectura

✅ **Testeable**: Mocks fáciles con Protocol
✅ **Flexible**: Cambiar implementaciones sin tocar código
✅ **Type-safe**: mypy y IDE autocomplete
✅ **Mantenible**: Código organizado y documentado
✅ **Escalable**: Agregar nuevas implementaciones fácilmente
✅ **SOLID**: Dependency Inversion Principle aplicado correctamente

---

**Documentación adicional**:
- Interfaces completas: Ver archivos en `app/core/interfaces/`
- Implementaciones: Ver `app/integrations/`
- Propuesta arquitectónica: `docs/ARCHITECTURE_PROPOSAL.md`
