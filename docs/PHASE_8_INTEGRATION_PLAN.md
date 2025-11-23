# Fase 8: Integración y Factory - Plan de Acción

## 🎯 Objetivo
Conectar la nueva arquitectura con el sistema existente y crear un sistema de Dependency Injection.

---

## 1. Crear Dependency Injection Container

### `app/core/container.py`

```python
"""
Dependency Injection Container

Crea y gestiona todas las dependencias del sistema.
"""

from typing import Dict
from app.core.interfaces.agent import IAgent
from app.core.interfaces.llm import ILLM
from app.core.interfaces.repository import IRepository
from app.core.interfaces.vector_store import IVectorStore

# Integrations
from app.integrations.llm import create_ollama_llm
from app.integrations.vector_stores import create_pgvector_store

# Repositories
from app.domains.ecommerce.infrastructure.repositories import ProductRepository
from app.domains.credit.infrastructure.persistence.sqlalchemy import CreditAccountRepository

# Agents
from app.domains.ecommerce.agents import ProductAgent
from app.domains.credit.agents import CreditAgent

# Orchestrator
from app.orchestration import SuperOrchestrator


class DependencyContainer:
    """Container for dependency injection"""

    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._llm_instance = None
        self._vector_store_instance = None

    # === Singletons ===

    def get_llm(self) -> ILLM:
        """Get LLM instance (singleton)"""
        if not self._llm_instance:
            self._llm_instance = create_ollama_llm(
                model_name=self.config.get("llm_model", "deepseek-r1:7b")
            )
        return self._llm_instance

    def get_vector_store(self) -> IVectorStore:
        """Get vector store instance (singleton)"""
        if not self._vector_store_instance:
            self._vector_store_instance = create_pgvector_store(
                collection_name="products",
                embedding_dimension=768
            )
        return self._vector_store_instance

    # === Repositories ===

    def create_product_repository(self) -> IRepository:
        """Create product repository"""
        return ProductRepository()

    def create_credit_account_repository(self) -> IRepository:
        """Create credit account repository"""
        return CreditAccountRepository()

    # === Agents ===

    def create_product_agent(self) -> IAgent:
        """Create product agent with all dependencies"""
        return ProductAgent(
            product_repository=self.create_product_repository(),
            vector_store=self.get_vector_store(),
            llm=self.get_llm(),
            config=self.config.get("product_agent", {})
        )

    def create_credit_agent(self) -> IAgent:
        """Create credit agent with all dependencies"""
        # Note: Needs payment repository when implemented
        return CreditAgent(
            credit_account_repository=self.create_credit_account_repository(),
            payment_repository=self.create_credit_account_repository(),  # TODO: Separate repo
            llm=self.get_llm(),
            config=self.config.get("credit_agent", {})
        )

    # === Super Orchestrator ===

    def create_super_orchestrator(self) -> SuperOrchestrator:
        """Create super orchestrator with all domain agents"""
        domain_agents = {
            "ecommerce": self.create_product_agent(),
            "credit": self.create_credit_agent(),
        }

        return SuperOrchestrator(
            domain_agents=domain_agents,
            llm=self.get_llm(),
            config=self.config.get("orchestrator", {})
        )


# Global container instance
_container = None

def get_container(config: Dict = None) -> DependencyContainer:
    """Get global container instance"""
    global _container
    if _container is None:
        _container = DependencyContainer(config)
    return _container
```

---

## 2. Integrar con FastAPI

### `app/api/dependencies.py` (actualizar)

```python
"""
FastAPI Dependencies

Provides dependency injection for FastAPI routes.
"""

from fastapi import Depends
from app.core.container import get_container, DependencyContainer
from app.orchestration import SuperOrchestrator


def get_di_container() -> DependencyContainer:
    """Get dependency injection container"""
    return get_container()


def get_super_orchestrator(
    container: DependencyContainer = Depends(get_di_container)
) -> SuperOrchestrator:
    """Get super orchestrator instance"""
    return container.create_super_orchestrator()
```

### `app/api/routes/chat.py` (actualizar)

```python
"""
Chat Routes

Updated to use new architecture.
"""

from fastapi import APIRouter, Depends
from app.api.dependencies import get_super_orchestrator
from app.orchestration import SuperOrchestrator

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    orchestrator: SuperOrchestrator = Depends(get_super_orchestrator)
):
    """
    Process chat message using new architecture.
    """
    # Convert request to state
    state = {
        "messages": [{"role": "user", "content": request.message}],
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
    }

    # Route to appropriate domain
    result = await orchestrator.route_message(state)

    # Extract response
    assistant_message = result["messages"][-1]["content"]

    return {
        "response": assistant_message,
        "domain": result.get("routing", {}).get("detected_domain"),
        "agent": result.get("routing", {}).get("agent_used"),
        "metadata": result.get("retrieved_data", {}),
    }
```

---

## 3. Migrar Servicios Legacy a Use Cases

### Mapeo de Servicios → Use Cases

| Servicio Legacy | Use Case Nuevo | Estado |
|-----------------|----------------|--------|
| `product_service.py` | Usar `ProductRepository` | ✅ Listo |
| `enhanced_product_service.py` | `SearchProductsUseCase` | ✅ Listo |
| `customer_service.py` | `CustomerRepository` + Use Cases | ❌ Crear |
| `dux_sync_service.py` | Mover a `infrastructure/external/` | ❌ Mover |
| `knowledge_service.py` | `KnowledgeRepository` | ❌ Crear |
| `super_orchestrator_service.py` | `SuperOrchestrator` | ✅ Reemplazar |

### Ejemplo: Migrar customer_service.py

**Antes:**
```python
# app/services/customer_service.py
class CustomerService:
    def get_customer(self, id):
        # Lógica mezclada
        pass
    def update_customer(self, id, data):
        # Más lógica mezclada
        pass
```

**Después:**
```python
# app/domains/ecommerce/infrastructure/repositories/customer_repository.py
class CustomerRepository(IRepository[Customer, int]):
    async def find_by_id(self, id: int) -> Optional[Customer]:
        # Solo data access
        pass

# app/domains/ecommerce/application/use_cases/get_customer.py
class GetCustomerUseCase:
    def __init__(self, repository: IRepository):
        self.repo = repository

    async def execute(self, request: GetCustomerRequest) -> GetCustomerResponse:
        # Solo business logic
        pass
```

---

## 4. Migrar Agentes Restantes

### Agentes E-commerce

- [ ] `promotions_agent.py` → `PromotionsAgent`
- [ ] `tracking_agent.py` → `OrderTrackingAgent`
- [ ] `category_agent.py` → Integrar en `ProductAgent`

### Agentes Shared (Multi-dominio)

- [ ] `greeting_agent.py` → `app/shared_agents/greeting_agent.py`
- [ ] `farewell_agent.py` → `app/shared_agents/farewell_agent.py`
- [ ] `fallback_agent.py` → `app/shared_agents/fallback_agent.py`
- [ ] `support_agent.py` → `app/shared_agents/support_agent.py`

### Agentes Credit

- [ ] `invoice_agent.py` → `InvoiceAgent` en `domains/credit/`

### Agentes Excelencia

- [ ] `excelencia_agent.py` → `ExcelenciaAgent` en `domains/excelencia/`

---

## 5. Cleanup de Código Legacy

### Archivos a deprecar/eliminar:

```python
# Marcar como deprecated
app/services/product_service.py  # → ProductRepository
app/services/enhanced_product_service.py  # → Use cases
app/services/super_orchestrator_service.py  # → SuperOrchestrator

# Agentes duplicados
app/agents/subagent/refactored_product_agent.py  # → ProductAgent
app/agents/subagent/smart_product_agent.py  # → ProductAgent
```

### Estrategia:
1. Agregar `@deprecated` decorator
2. Mantener por 1 versión (backward compatibility)
3. Eliminar en próxima versión major

---

## 6. Tests de Integración

### Crear tests end-to-end:

```python
# tests/integration/test_chat_flow.py

@pytest.mark.asyncio
async def test_ecommerce_flow():
    """Test completo E-commerce: API → Orchestrator → Agent → Use Case → Repository"""

    # Setup
    container = get_container()
    orchestrator = container.create_super_orchestrator()

    # Ejecutar
    state = {
        "messages": [{"role": "user", "content": "Busco laptop"}],
        "user_id": "test_user"
    }
    result = await orchestrator.route_message(state)

    # Verificar
    assert result["routing"]["detected_domain"] == "ecommerce"
    assert "laptop" in result["messages"][-1]["content"].lower()
    assert len(result["retrieved_data"]["products"]) > 0


@pytest.mark.asyncio
async def test_credit_flow():
    """Test completo Credit"""
    # Similar para credit domain
```

---

## 7. Configuración

### `app/config/domain_config.py`

```python
"""
Domain Configuration

Configuration for each domain.
"""

DOMAIN_CONFIG = {
    "ecommerce": {
        "product_agent": {
            "max_results": 10,
            "use_semantic_search": True,
        },
        "vector_store": {
            "collection_name": "products",
            "embedding_dimension": 768,
        }
    },
    "credit": {
        "credit_agent": {
            "default_payment_plan_months": 6,
        }
    },
    "orchestrator": {
        "default_domain": "ecommerce",
    }
}
```

---

## Checklist de Implementación

### Fase 8a: Container e Integración (1-2 días)
- [ ] Crear `app/core/container.py`
- [ ] Actualizar `app/api/dependencies.py`
- [ ] Actualizar `/api/chat` route
- [ ] Tests de integración básicos

### Fase 8b: Migración de Servicios (2-3 días)
- [ ] Deprecar `product_service.py`
- [ ] Deprecar `enhanced_product_service.py`
- [ ] Migrar `customer_service.py` → Use Cases
- [ ] Mover `dux_sync_service.py` → infrastructure/

### Fase 8c: Migración de Agentes (2-3 días)
- [ ] Migrar agentes E-commerce restantes
- [ ] Migrar agentes shared
- [ ] Migrar agentes Credit
- [ ] Actualizar AgentFactory

### Fase 8d: Cleanup (1 día)
- [ ] Marcar código legacy como deprecated
- [ ] Actualizar imports
- [ ] Documentar breaking changes
- [ ] Tests de regresión

---

## Resultado Esperado

Después de Fase 8:
- ✅ Sistema completamente integrado
- ✅ API routes usando nueva arquitectura
- ✅ Todos los servicios migrados o deprecados
- ✅ Todos los agentes migrados
- ✅ Código legacy marcado para eliminación
- ✅ Tests de integración completos

**Tiempo estimado:** 6-9 días de trabajo
