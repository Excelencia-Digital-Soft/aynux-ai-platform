# Servicios Deprecados - Guía de Migración

## 📋 Resumen

Este documento lista todos los servicios legacy que han sido marcados como **DEPRECATED** y proporciona una guía clara para migrar a la nueva arquitectura Clean Architecture.

**Versión de deprecación**: 1.x
**Versión de eliminación**: 2.0.0
**Fecha**: 2025-01-23

---

## 🚨 Servicios Deprecados

### 1. ProductService

**Archivo**: `app/services/product_service.py`
**Estado**: ⚠️ DEPRECATED
**Razón**: Mezcla responsabilidades de data access y business logic

#### Problemas del servicio legacy

- ❌ Viola Single Responsibility Principle
- ❌ SQL queries directas mezcladas con business logic
- ❌ Difícil de testear (requiere DB real)
- ❌ Sin separación de capas
- ❌ Tightly coupled a implementación de PostgreSQL

#### Reemplazo

**Usar**:
- `ProductRepository` (app/domains/ecommerce/infrastructure/repositories/product_repository.py)
- `GetProductsByCategoryUseCase` (app/domains/ecommerce/application/use_cases/get_products_by_category.py)
- `GetFeaturedProductsUseCase` (app/domains/ecommerce/application/use_cases/get_featured_products.py)

#### Ejemplo de migración

```python
# ❌ ANTES (Legacy)
from app.services.product_service import ProductService

service = ProductService()
products = await service.search_products("laptop")
featured = await service.get_featured_products(limit=10)
```

```python
# ✅ DESPUÉS (Clean Architecture)
from app.core.container import get_container
from app.domains.ecommerce.application.use_cases.search_products import SearchProductsRequest

container = get_container()

# Búsqueda de productos
search_use_case = container.create_search_products_use_case()
response = await search_use_case.execute(SearchProductsRequest(query="laptop"))
products = response.products

# Productos destacados
featured_use_case = container.create_get_featured_products_use_case()
featured_response = await featured_use_case.execute(GetFeaturedProductsRequest(limit=10))
featured = featured_response.products
```

#### Beneficios de la migración

- ✅ **Testeable**: Usa mocks, no requiere DB
- ✅ **SOLID**: Responsabilidades separadas
- ✅ **Type-Safe**: Type hints completos
- ✅ **Mantenible**: Código organizado en capas

---

### 2. EnhancedProductService

**Archivo**: `app/services/enhanced_product_service.py`
**Estado**: ⚠️ DEPRECATED
**Razón**: Hybrid search con responsabilidades mezcladas

#### Problemas del servicio legacy

- ❌ Hereda de ProductService (coupling)
- ❌ Mezcla vector search, SQL filtering y business logic
- ❌ Difícil de testear (múltiples dependencias hardcoded)
- ❌ No sigue Dependency Injection
- ❌ Conversation history como parámetro (violates SRP)

#### Reemplazo

**Usar**:
- `SearchProductsUseCase` (app/domains/ecommerce/application/use_cases/search_products.py)

#### Ejemplo de migración

```python
# ❌ ANTES (Legacy)
from app.services.enhanced_product_service import EnhancedProductService

service = EnhancedProductService()
results = await service.hybrid_search_products(
    query="laptop gaming",
    conversation_history=messages,
    limit=10,
    price_range=(500, 2000),
    brand_filter="Dell"
)
```

```python
# ✅ DESPUÉS (Clean Architecture)
from app.core.container import get_container
from app.domains.ecommerce.application.use_cases.search_products import SearchProductsRequest

container = get_container()
use_case = container.create_search_products_use_case()

response = await use_case.execute(SearchProductsRequest(
    query="laptop gaming",
    min_price=500.0,
    max_price=2000.0,
    brand="Dell",
    limit=10,
    use_semantic_search=True  # Habilita vector search
))

products = response.products
# Cada producto ya viene con similarity_score si se usó semantic search
```

#### Beneficios de la migración

- ✅ **Estrategia Dual**: Semantic search primero, database fallback automático
- ✅ **Dependency Injection**: Vector store y repository inyectados
- ✅ **Sin coupling**: No hereda de otros servicios
- ✅ **Más rápido**: Optimizado con pgvector

---

### 3. SuperOrchestratorService

**Archivo**: `app/services/super_orchestrator_service.py`
**Estado**: ⚠️ DEPRECATED
**Razón**: Arquitectura monolítica con múltiples responsabilidades

#### Problemas del servicio legacy

- ❌ Mezcla domain detection, contact management y routing
- ❌ Hardcoded patterns (no extensible)
- ❌ Tightly coupled a database (Contact, WhatsAppMessage)
- ❌ Difícil agregar nuevos dominios (requires code modification)
- ❌ No usa LLM para domain detection (solo patterns)
- ❌ Domain managers hardcoded

#### Reemplazo

**Usar**:
- `SuperOrchestrator` (app/orchestration/super_orchestrator.py)
- `DependencyContainer` (app/core/container.py)
- Domain Agents vía Dependency Injection

#### Ejemplo de migración

```python
# ❌ ANTES (Legacy)
from app.services.super_orchestrator_service import SuperOrchestratorService

orchestrator = SuperOrchestratorService()
response = await orchestrator.process_message(
    message=whatsapp_message,
    contact=contact,
    db=db_session
)
```

```python
# ✅ DESPUÉS (Clean Architecture)
from app.core.container import get_container

container = get_container()
orchestrator = container.create_super_orchestrator()

# Convertir mensaje WhatsApp a state
state = {
    "messages": [{"role": "user", "content": whatsapp_message.text}],
    "user_id": contact.phone,
    "session_id": f"whatsapp_{contact.phone}",
    "metadata": {
        "contact_name": contact.name,
        "platform": "whatsapp",
    }
}

# Rutear mensaje al dominio apropiado
result = await orchestrator.route_message(state)

# Extraer información de routing
routing_info = result["routing"]
detected_domain = routing_info["detected_domain"]  # "ecommerce", "credit", etc.
agent_used = routing_info["agent_used"]  # "product_agent", "credit_agent", etc.

# Extraer respuesta del asistente
messages = result["messages"]
assistant_response = messages[-1]["content"]

# Datos recuperados (productos, crédito, etc.)
retrieved_data = result.get("retrieved_data", {})
```

#### Beneficios de la migración

- ✅ **LLM-Based Detection**: Usa modelo de IA para detectar dominio
- ✅ **Extensible**: Agregar dominios sin modificar código
- ✅ **Clean Separation**: No accede a DB, solo routing
- ✅ **Testeable**: Mocks fáciles para LLM y agents
- ✅ **Domain-Agnostic**: No conoce detalles internos de dominios

---

## 📊 Tabla Comparativa

| Servicio Legacy | Reemplazo Clean Architecture | Beneficio Principal |
|----------------|------------------------------|---------------------|
| `ProductService` | `ProductRepository` + Use Cases | Separación de capas |
| `EnhancedProductService` | `SearchProductsUseCase` | Semantic search optimizado |
| `SuperOrchestratorService` | `SuperOrchestrator` | LLM-based routing |

---

## 🔄 Estrategia de Migración

### Fase 1: Coexistencia (Actual)

- ✅ Servicios legacy marcados como `@deprecated`
- ✅ Warnings en logs cuando se usan
- ✅ Nueva arquitectura disponible vía `/v2/*` endpoints
- ✅ Backward compatibility mantenida

### Fase 2: Migración Gradual (Próximas semanas)

1. Actualizar endpoints a usar nueva arquitectura
2. Migrar tests a nueva arquitectura
3. Migrar servicios restantes (customer, knowledge, etc.)
4. Deprecar agentes duplicados

### Fase 3: Eliminación (Versión 2.0.0)

1. Eliminar servicios deprecados
2. Eliminar imports legacy
3. Limpiar código no usado
4. Actualizar documentación

---

## 🧪 Cómo Testear la Nueva Arquitectura

### Test Unitario (Ejemplo)

```python
import pytest
from unittest.mock import AsyncMock

from app.domains.ecommerce.application.use_cases.search_products import (
    SearchProductsUseCase,
    SearchProductsRequest,
)

@pytest.fixture
def mock_repository():
    repo = AsyncMock()
    repo.search.return_value = [
        MagicMock(id=1, name="Laptop Dell", price=1200.0)
    ]
    return repo

@pytest.fixture
def mock_vector_store():
    vector = AsyncMock()
    vector.search.return_value = [
        {"id": "prod_1", "score": 0.95}
    ]
    return vector

@pytest.mark.asyncio
async def test_search_products(mock_repository, mock_vector_store):
    # Arrange
    use_case = SearchProductsUseCase(
        product_repository=mock_repository,
        vector_store=mock_vector_store,
        llm=None  # No needed for this test
    )

    request = SearchProductsRequest(query="laptop", limit=10)

    # Act
    response = await use_case.execute(request)

    # Assert
    assert response.success is True
    assert len(response.products) > 0
    mock_vector_store.search.assert_called_once()
```

### Test de Integración (Ejemplo)

```python
@pytest.mark.asyncio
async def test_end_to_end_product_search():
    # Setup
    container = get_container()
    orchestrator = container.create_super_orchestrator()

    # Execute
    state = {
        "messages": [{"role": "user", "content": "Busco laptop"}],
        "user_id": "test_user"
    }
    result = await orchestrator.route_message(state)

    # Verify
    assert result["routing"]["detected_domain"] == "ecommerce"
    assert "laptop" in result["messages"][-1]["content"].lower()
```

---

## ⚡ Quick Reference

### Obtener SuperOrchestrator

```python
from app.core.container import get_container

container = get_container()
orchestrator = container.create_super_orchestrator()
```

### Obtener ProductAgent

```python
from app.core.container import get_container

container = get_container()
product_agent = container.create_product_agent()
```

### Obtener Use Case

```python
from app.core.container import get_container

container = get_container()
search_use_case = container.create_search_products_use_case()
```

### Usar en FastAPI

```python
from fastapi import Depends
from app.api.dependencies import get_super_orchestrator

@router.post("/chat")
async def chat(
    request: ChatRequest,
    orchestrator: SuperOrchestrator = Depends(get_super_orchestrator)
):
    result = await orchestrator.route_message(state)
    return result
```

---

## 📚 Documentación Relacionada

- **Clean Architecture Guide**: `docs/ARCHITECTURE_PROPOSAL.md`
- **Phase 8 Integration**: `docs/PHASE_8_INTEGRATION_PLAN.md`
- **Phase 8a Completion**: `docs/PHASE_8A_COMPLETION_SUMMARY.md`
- **Domain Implementation Guide**: `docs/DOMAIN_IMPLEMENTATION_GUIDE.md`
- **Testing Guide**: `docs/TESTING_GUIDE.md`

---

## ❓ FAQ

### ¿Cuándo se eliminarán estos servicios?

Los servicios deprecados se eliminarán en la **versión 2.0.0** (fecha TBD). Por ahora, siguen funcionando pero emiten warnings.

### ¿Puedo usar ambos en mi código?

Sí, durante la fase de transición ambos coexisten. Sin embargo, se recomienda migrar a la nueva arquitectura lo antes posible.

### ¿Qué pasa si no migro?

En versión 2.0.0, los servicios deprecados serán eliminados y tu código dejará de funcionar. Migrar ahora evita breaking changes futuros.

### ¿Cómo identifico uso de servicios deprecados?

Los servicios deprecados emiten `DeprecationWarning` en logs cuando son instanciados. Busca estos warnings en tus logs.

### ¿Dónde encuentro ejemplos de la nueva arquitectura?

- Integration tests: `tests/integration/test_clean_architecture_integration.py`
- API routes: `app/api/routes/chat.py` (endpoints `/v2/*`)
- Use cases: `app/domains/*/application/use_cases/`
- Agents: `app/domains/*/agents/`

---

## 🎯 Conclusión

La nueva arquitectura Clean Architecture proporciona:

✅ **Mejor organización**: Código separado en capas claras
✅ **Más testeable**: 100% cobertura posible con mocks
✅ **Más mantenible**: SOLID principles aplicados
✅ **Más extensible**: Agregar dominios sin modificar código existente
✅ **Type-safe**: Type hints completos

**Migra ahora para aprovechar estos beneficios** 🚀

---

**Última actualización**: 2025-01-23
**Versión del documento**: 1.0
