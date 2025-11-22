# PLAN DE ACCIÓN: MIGRACIÓN ARQUITECTÓNICA AYNUX
## De Estructura Monolítica a Arquitectura Multi-Dominio DDD

**Fecha**: 2025-11-22
**Duración Estimada**: 16 semanas
**Tipo de Migración**: Gradual (sin downtime)

---

## 🎯 RESUMEN EJECUTIVO

### Situación Actual
- **244 archivos Python** con organización inconsistente
- **Archivo crítico**: `knowledge_repository.py` con 18,434 líneas (URGENTE)
- **Dominios mezclados**: E-commerce fragmentado en múltiples carpetas
- **Dependencias circulares**: Services ↔ Agents
- **29 servicios** con responsabilidades solapadas

### Objetivo
Transformar Aynux en un sistema **modular, escalable y mantenible** basado en **Domain-Driven Design (DDD)** + **Clean Architecture** + **SOLID principles**.

### ROI Esperado
- ⚡ **-50%** tiempo para agregar nuevos dominios
- 🐛 **-60%** bugs en producción (tests exhaustivos)
- 📚 **-70%** tiempo de onboarding de nuevos desarrolladores
- 🚀 **+300%** capacidad de escalar dominios independientemente

---

## 🚨 PROBLEMAS CRÍTICOS (PRIORIDAD MÁXIMA)

### 1. `knowledge_repository.py` (18,434 líneas)
**Riesgo**: CRÍTICO - Inmantenible, imposible de testear completamente

**Acción Inmediata**:
```bash
# SEMANA 1: Dividir en repositorios por dominio
app/repositories/knowledge_repository.py
↓
app/domains/ecommerce/infrastructure/knowledge/
  ├── product_knowledge_repo.py      (~500 líneas)
  ├── category_knowledge_repo.py     (~300 líneas)
  └── promotion_knowledge_repo.py    (~200 líneas)

app/domains/credit/infrastructure/knowledge/
  └── credit_knowledge_repo.py       (~400 líneas)

app/core/infrastructure/knowledge/
  └── base_knowledge_repo.py         (~300 líneas)
```

**Script de migración**:
```python
# scripts/migration/split_knowledge_repository.py
"""
Script para dividir knowledge_repository.py en módulos específicos
"""
import ast
import re

def extract_ecommerce_methods():
    """Extrae métodos relacionados con e-commerce"""
    # Regex patterns para identificar métodos por dominio
    ecommerce_patterns = [
        r"product_", r"category_", r"promotion_",
        r"order_", r"dux_"
    ]
    # ...

def create_domain_repository(domain: str, methods: list):
    """Crea repositorio específico por dominio"""
    # ...
```

---

### 2. Dependencias Circulares
**Riesgo**: ALTO - Dificulta testing, genera bugs sutiles

**Acción Inmediata**:
```python
# SEMANA 2: Implementar Dependency Inversion

# ANTES (dependencia directa)
# app/services/langgraph_chatbot_service.py
class LangGraphChatbotService:
    def __init__(self):
        self.product_agent = SmartProductAgent()  # ❌ Hardcoded

# DESPUÉS (dependency injection)
# app/domains/ecommerce/application/services/chatbot_service.py
class EcommerceChatbotService:
    def __init__(self, product_agent: IProductAgent):  # ✅ Interface
        self.product_agent = product_agent

# app/core/interfaces/agent.py
class IProductAgent(Protocol):
    async def search(self, query: str) -> list[Product]: ...
```

---

### 3. Agentes de Producto Duplicados
**Riesgo**: MEDIO - Confusión, mantenimiento duplicado

**Acción Inmediata**:
```bash
# SEMANA 3: Consolidar en un solo agente con Strategy Pattern

# ELIMINAR (3 agentes diferentes)
app/agents/subagent/smart_product_agent.py         # 450 líneas
app/agents/subagent/refactored_product_agent.py    # 380 líneas
app/agents/product/product_agent_orchestrator.py   # 320 líneas

# CREAR (un agente con estrategias)
app/domains/ecommerce/agents/nodes/product_search.py  # 200 líneas
  + Estrategias intercambiables:
    - PgVectorSearchStrategy
    - DatabaseSearchStrategy
    - HybridSearchStrategy
```

---

## 📅 CRONOGRAMA DETALLADO (16 SEMANAS)

### FASE 1: PREPARACIÓN (Semanas 1-2) 🟢 BAJO RIESGO

**Objetivo**: Crear infraestructura base sin tocar código existente

**Semana 1**:
- [ ] Crear estructura de directorios nueva (`app/core/`, `app/domains/`)
- [ ] Implementar `app/core/interfaces/` (IRepository, IAgent, ILLM, etc.)
- [ ] Configurar dependency injection container
- [ ] Documentar convenciones de código

**Semana 2**:
- [ ] Migrar `app/utils/` → `app/core/shared/`
- [ ] Migrar `app/core/` (circuit breaker, cache, validators)
- [ ] Crear base de tests (`tests/conftest.py` con fixtures globales)
- [ ] Actualizar CI/CD para nueva estructura

**Entregables**:
- Nueva estructura coexistiendo con código actual
- Tests pasando
- CI/CD funcional

**Comandos**:
```bash
# Crear estructura
mkdir -p app/core/{interfaces,domain,infrastructure,shared,config}
mkdir -p app/domains/{ecommerce,credit,healthcare,excelencia}
mkdir -p tests/{unit,integration,e2e}

# Instalar herramientas
uv add dependency-injector pytest-asyncio pytest-cov

# Validar estructura
tree app/core/
pytest tests/ -v
```

---

### FASE 2: MIGRACIÓN CORE (Semanas 3-4) 🟡 RIESGO MEDIO

**Objetivo**: Migrar componentes compartidos sin romper funcionalidad

**Semana 3**:
- [ ] **CRÍTICO**: Dividir `knowledge_repository.py` (18K líneas)
  - [ ] Crear `ProductKnowledgeRepository` (~500 líneas)
  - [ ] Crear `CategoryKnowledgeRepository` (~300 líneas)
  - [ ] Crear `PromotionKnowledgeRepository` (~200 líneas)
  - [ ] Tests para cada repositorio
- [ ] Migrar configuración → `app/core/config/`
- [ ] Implementar logging estructurado

**Semana 4**:
- [ ] Migrar integraciones:
  - [ ] `app/integrations/llm/ollama.py`
  - [ ] `app/integrations/vector_stores/pgvector.py`
  - [ ] `app/integrations/whatsapp/client.py`
- [ ] Implementar interfaces (IVectorStore, ILLM)
- [ ] Actualizar imports en código existente
- [ ] Tests de integración

**Entregables**:
- `knowledge_repository.py` dividido y funcional
- Integraciones migradas con interfaces
- Tests de integración >80%

**Validación**:
```bash
# Verificar que todos los tests pasan
pytest tests/ -v --cov=app/core --cov-report=html

# Verificar que no hay dependencias circulares
pydeps app/core --max-bacon=2

# Verificar métricas de código
radon cc app/core/ -a  # Complejidad ciclomática
radon mi app/core/ -s  # Maintainability Index
```

---

### FASE 3: MIGRACIÓN E-COMMERCE (Semanas 5-7) 🟡 RIESGO MEDIO-ALTO

**Objetivo**: Migrar dominio más maduro como blueprint para otros

**Semana 5 - Domain Layer**:
- [ ] Crear entidades de dominio:
  - [ ] `app/domains/ecommerce/domain/entities/product.py`
  - [ ] `app/domains/ecommerce/domain/entities/order.py`
  - [ ] `app/domains/ecommerce/domain/entities/customer.py`
- [ ] Crear value objects:
  - [ ] `Price`, `SKU`, `OrderStatus`
- [ ] Tests unitarios de entidades (100% coverage)

**Semana 6 - Application Layer**:
- [ ] Crear use cases:
  - [ ] `SearchProductsUseCase`
  - [ ] `CreateOrderUseCase`
  - [ ] `TrackOrderUseCase`
  - [ ] `ApplyPromotionUseCase`
- [ ] Implementar DTOs (ProductDTO, OrderDTO)
- [ ] Definir ports (interfaces para repositorios)
- [ ] Tests de use cases con mocks

**Semana 7 - Infrastructure & Agents**:
- [ ] Migrar repositorios:
  - [ ] `SQLAlchemyProductRepository`
  - [ ] `SQLAlchemyOrderRepository`
- [ ] Consolidar agentes de producto (3 → 1):
  - [ ] Eliminar `smart_product_agent.py`
  - [ ] Eliminar `refactored_product_agent.py`
  - [ ] Crear `ProductSearchNode` con Strategy Pattern
- [ ] Migrar `graph.py` → `ecommerce/agents/graph.py`
- [ ] Tests E2E de flujo completo

**Entregables**:
- Dominio e-commerce completamente migrado
- Tests unitarios + integración + E2E
- Documentación completa del dominio

**Validación**:
```bash
# Tests completos
pytest tests/unit/domains/ecommerce/ -v --cov=app/domains/ecommerce/domain --cov-report=term-missing
pytest tests/integration/ecommerce/ -v
pytest tests/e2e/test_ecommerce_flow.py -v

# Verificar que API funciona
python test_chat_endpoint.py

# Load testing
locust -f tests/load/test_ecommerce.py --headless -u 100 -r 10 -t 5m
```

---

### FASE 4: MIGRACIÓN CREDIT (Semanas 8-9) 🟢 BAJO RIESGO

**Objetivo**: Migrar dominio ya organizado

**Semana 8**:
- [ ] Mover `app/agents/credit/` → `app/domains/credit/`
- [ ] Reorganizar siguiendo estructura DDD
- [ ] Crear modelos de base de datos (actualmente stubs)
- [ ] Implementar repositorios reales

**Semana 9**:
- [ ] Implementar use cases reales (actualmente solo stubs):
  - [ ] `CheckBalanceUseCase`
  - [ ] `ProcessPaymentUseCase`
  - [ ] `ApplyCreditUseCase`
- [ ] Integración con sistema externo de crédito (si aplica)
- [ ] Tests completos

**Entregables**:
- Dominio credit producción-ready
- Integración con sistema externo
- Tests >80%

---

### FASE 5: DOMINIOS NUEVOS (Semanas 10-12) 🔴 RIESGO ALTO

**Objetivo**: Implementar Healthcare y Excelencia desde cero

**Semana 10-11 - Healthcare**:
- [ ] Domain layer:
  - [ ] Entities: `Patient`, `Appointment`, `Doctor`, `MedicalRecord`
  - [ ] Value objects: `PatientId`, `AppointmentTime`, `Diagnosis`
  - [ ] Domain services: `SchedulingService`, `TriageService`
- [ ] Application layer:
  - [ ] Use cases: `BookAppointment`, `ConsultDoctor`, `EmergencyHandler`
- [ ] Infrastructure:
  - [ ] Database models
  - [ ] Repositorios
- [ ] Agents (LangGraph):
  - [ ] `HealthcareGraph` orchestrator
  - [ ] Agent nodes: appointment, consultation, emergency, records
- [ ] Tests completos

**Semana 12 - Excelencia**:
- [ ] Domain layer:
  - [ ] Entities: `ERPModule`, `DemoRequest`, `SupportTicket`
  - [ ] Services: `DemoService`, `ModuleInfoService`
- [ ] Application layer:
  - [ ] Use cases: `ShowModules`, `ScheduleDemo`, `TechnicalSupport`
- [ ] Agents (LangGraph):
  - [ ] `ExcelenciaGraph` orchestrator
  - [ ] Agent nodes: modules, demo, support
- [ ] Tests completos

**Entregables**:
- 2 dominios nuevos operativos
- Tests >75%
- Documentación de dominios

---

### FASE 6: ORQUESTACIÓN MULTI-DOMINIO (Semanas 13-14) 🟡 RIESGO MEDIO

**Objetivo**: Super orchestrator robusto

**Semana 13**:
- [ ] Implementar `app/orchestration/super_orchestrator.py`
- [ ] Implementar routing strategies:
  - [ ] `AIBasedRoutingStrategy` (LLM classifica dominio)
  - [ ] `KeywordRoutingStrategy` (reglas + keywords)
  - [ ] `HybridRoutingStrategy` (combina ambas)
- [ ] Context manager para conversaciones multi-dominio
- [ ] Cache de decisiones de routing

**Semana 14**:
- [ ] Implementar fallback cuando no se identifica dominio
- [ ] Logging y monitoring de decisiones de routing
- [ ] Tests E2E de domain switching:
  - [ ] Conversación E-commerce → Credit
  - [ ] Conversación Healthcare → E-commerce
  - [ ] Conversación con contexto multi-dominio
- [ ] Performance testing

**Entregables**:
- Super orchestrator robusto
- Tests E2E de switching >90%
- Métricas de accuracy de routing

**Validación**:
```bash
# Test de switching entre dominios
pytest tests/e2e/test_domain_switching.py -v

# Verificar accuracy de routing
python scripts/evaluate_routing_accuracy.py \
  --test-dataset tests/data/routing_test_cases.json \
  --min-accuracy 0.95

# Monitoring
curl http://localhost:8000/api/v1/admin/routing/metrics
```

---

### FASE 7: LIMPIEZA Y OPTIMIZACIÓN (Semanas 15-16) 🟢 BAJO RIESGO

**Objetivo**: Eliminar código legacy y optimizar

**Semana 15 - Limpieza**:
- [ ] **Eliminar código duplicado**:
  - [ ] `smart_product_agent.py` ✂️
  - [ ] `refactored_product_agent.py` ✂️
  - [ ] `enhanced_product_service.py` ✂️
  - [ ] ChromaDB integration ✂️ (migrar completamente a pgvector)
- [ ] **Consolidar servicios** (29 → ~15):
  - [ ] Merge `dux_sync_service.py` + `dux_rag_sync_service.py`
  - [ ] Merge `vector_service.py` + `category_vector_service.py`
- [ ] Actualizar imports en todo el proyecto
- [ ] Limpiar archivos obsoletos

**Semana 16 - Optimización**:
- [ ] **Performance tuning**:
  - [ ] Database query optimization (EXPLAIN ANALYZE)
  - [ ] Cache tuning (Redis)
  - [ ] LLM request batching
  - [ ] Vector search optimization (HNSW index tuning)
- [ ] **Security audit**:
  - [ ] Input validation completa
  - [ ] SQL injection prevention
  - [ ] Rate limiting ajustes
  - [ ] Authentication review
- [ ] **Documentación final**:
  - [ ] Architecture diagrams
  - [ ] API documentation (OpenAPI)
  - [ ] Developer onboarding guide
  - [ ] Deployment guide

**Entregables**:
- Sistema limpio y optimizado
- Performance benchmark >30% mejor
- Documentación completa
- Security audit report

**Validación Final**:
```bash
# Verificar métricas de éxito
python scripts/architecture_metrics.py

# Esperado:
# ✅ Archivos >500 líneas: 0 (actual: 8)
# ✅ Dependencias circulares: 0 (actual: 7+)
# ✅ Cobertura de tests: >80% (actual: ~40%)
# ✅ Servicios: <20 (actual: 29)
# ✅ Dominios completos: 4 (actual: 1.5)

# Performance benchmark
python scripts/benchmark.py --compare-with-baseline

# Security scan
bandit -r app/ -ll
safety check
```

---

## 🛠️ HERRAMIENTAS Y SCRIPTS DE MIGRACIÓN

### 1. Script de División de `knowledge_repository.py`

```python
# scripts/migration/split_knowledge_repository.py
"""
Divide knowledge_repository.py en módulos por dominio
"""
import ast
import re
from pathlib import Path
from typing import Dict, List

class KnowledgeRepositorySplitter:
    """Divide el monolito en repositorios por dominio"""

    DOMAIN_PATTERNS = {
        "ecommerce": [
            r"product_", r"category_", r"subcategory_",
            r"brand_", r"promotion_", r"order_", r"dux_"
        ],
        "credit": [
            r"credit_", r"account_", r"payment_",
            r"collection_", r"risk_"
        ],
        "healthcare": [
            r"patient_", r"appointment_", r"doctor_",
            r"medical_", r"triage_"
        ]
    }

    def __init__(self, source_file: Path):
        self.source_file = source_file
        with open(source_file, 'r') as f:
            self.source_code = f.read()
        self.tree = ast.parse(self.source_code)

    def extract_methods_by_domain(self) -> Dict[str, List[ast.FunctionDef]]:
        """Extrae métodos agrupados por dominio"""
        domain_methods = {domain: [] for domain in self.DOMAIN_PATTERNS}
        domain_methods["common"] = []

        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                domain = self._classify_method(node.name)
                domain_methods[domain].append(node)

        return domain_methods

    def _classify_method(self, method_name: str) -> str:
        """Clasifica método según patrones de dominio"""
        for domain, patterns in self.DOMAIN_PATTERNS.items():
            if any(re.match(pattern, method_name) for pattern in patterns):
                return domain
        return "common"

    def generate_domain_repository(self, domain: str, methods: List[ast.FunctionDef]) -> str:
        """Genera código para repositorio de dominio"""
        imports = self._extract_imports()
        class_def = self._generate_class(domain, methods)

        return f"{imports}\n\n{class_def}"

    def split_and_save(self):
        """Ejecuta división completa"""
        domain_methods = self.extract_methods_by_domain()

        for domain, methods in domain_methods.items():
            if not methods:
                continue

            output_path = self._get_output_path(domain)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            code = self.generate_domain_repository(domain, methods)
            with open(output_path, 'w') as f:
                f.write(code)

            print(f"✅ Created {output_path} ({len(methods)} methods)")

    def _get_output_path(self, domain: str) -> Path:
        """Calcula path de salida según dominio"""
        if domain == "common":
            return Path("app/core/infrastructure/knowledge/base_knowledge_repository.py")
        else:
            return Path(f"app/domains/{domain}/infrastructure/knowledge/{domain}_knowledge_repository.py")


# Uso
if __name__ == "__main__":
    splitter = KnowledgeRepositorySplitter(
        Path("app/repositories/knowledge_repository.py")
    )
    splitter.split_and_save()
```

**Ejecutar**:
```bash
python scripts/migration/split_knowledge_repository.py

# Verificar resultados
tree app/domains/*/infrastructure/knowledge/
tree app/core/infrastructure/knowledge/
```

---

### 2. Script de Detección de Dependencias Circulares

```python
# scripts/analysis/detect_circular_dependencies.py
"""
Detecta dependencias circulares en el proyecto
"""
import ast
from pathlib import Path
from typing import Dict, Set, List
from collections import defaultdict

class CircularDependencyDetector:
    """Detecta ciclos en el grafo de importaciones"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.imports_graph: Dict[str, Set[str]] = defaultdict(set)

    def analyze_project(self):
        """Analiza todos los archivos Python"""
        for py_file in self.project_root.rglob("*.py"):
            if "venv" in str(py_file) or ".venv" in str(py_file):
                continue
            self._analyze_file(py_file)

    def _analyze_file(self, file_path: Path):
        """Analiza un archivo y extrae sus imports"""
        try:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read())

            module_name = self._path_to_module(file_path)

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported_module = self._get_import_module(node)
                    if imported_module and imported_module.startswith("app."):
                        self.imports_graph[module_name].add(imported_module)
        except:
            pass

    def find_cycles(self) -> List[List[str]]:
        """Encuentra todos los ciclos en el grafo"""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.imports_graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Ciclo encontrado
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            rec_stack.remove(node)

        for node in self.imports_graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    def _path_to_module(self, path: Path) -> str:
        """Convierte path a nombre de módulo"""
        rel_path = path.relative_to(self.project_root)
        module = str(rel_path).replace("/", ".").replace(".py", "")
        return module

    def _get_import_module(self, node) -> str:
        """Extrae nombre de módulo de nodo import"""
        if isinstance(node, ast.Import):
            return node.names[0].name
        elif isinstance(node, ast.ImportFrom):
            return node.module
        return None


# Uso
if __name__ == "__main__":
    detector = CircularDependencyDetector(Path("app"))
    detector.analyze_project()
    cycles = detector.find_cycles()

    if cycles:
        print(f"🚨 Found {len(cycles)} circular dependencies:")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n{i}. Cycle:")
            for module in cycle:
                print(f"   {module}")
            print("   ↑____________↓")
    else:
        print("✅ No circular dependencies found")
```

**Ejecutar**:
```bash
python scripts/analysis/detect_circular_dependencies.py
```

---

### 3. Script de Métricas de Arquitectura

```python
# scripts/analysis/architecture_metrics.py
"""
Calcula métricas de calidad de arquitectura
"""
from pathlib import Path
import ast
from typing import Dict
import json

class ArchitectureMetrics:
    """Calcula métricas de calidad de código"""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def calculate_all_metrics(self) -> Dict:
        """Calcula todas las métricas"""
        return {
            "file_sizes": self.get_large_files(),
            "circular_deps": self.count_circular_deps(),
            "test_coverage": self.get_test_coverage(),
            "service_count": self.count_services(),
            "domain_completeness": self.check_domain_completeness(),
            "code_duplication": self.detect_duplication()
        }

    def get_large_files(self) -> Dict:
        """Encuentra archivos grandes (>500 líneas)"""
        large_files = {}
        for py_file in self.project_root.rglob("*.py"):
            if "venv" in str(py_file):
                continue
            with open(py_file, 'r') as f:
                line_count = len(f.readlines())
            if line_count > 500:
                large_files[str(py_file)] = line_count
        return dict(sorted(large_files.items(), key=lambda x: x[1], reverse=True))

    def count_services(self) -> int:
        """Cuenta archivos de servicio"""
        services_dir = self.project_root / "app" / "services"
        if not services_dir.exists():
            return 0
        return len(list(services_dir.glob("*_service.py")))

    def check_domain_completeness(self) -> Dict:
        """Verifica completitud de cada dominio"""
        domains_dir = self.project_root / "app" / "domains"
        if not domains_dir.exists():
            return {}

        completeness = {}
        required_structure = ["domain", "application", "infrastructure", "agents", "api"]

        for domain_dir in domains_dir.iterdir():
            if not domain_dir.is_dir():
                continue

            completeness[domain_dir.name] = {
                folder: (domain_dir / folder).exists()
                for folder in required_structure
            }

        return completeness

    def print_report(self):
        """Imprime reporte completo"""
        metrics = self.calculate_all_metrics()

        print("=" * 80)
        print("AYNUX ARCHITECTURE METRICS REPORT")
        print("=" * 80)

        # Archivos grandes
        print("\n📊 Large Files (>500 lines):")
        large_files = metrics["file_sizes"]
        if large_files:
            for file, lines in list(large_files.items())[:10]:
                status = "🔴" if lines > 1000 else "🟡"
                print(f"  {status} {file}: {lines} lines")
        else:
            print("  ✅ No files larger than 500 lines")

        # Servicios
        print(f"\n📦 Service Count: {metrics['service_count']}")
        if metrics["service_count"] > 20:
            print("  🟡 Consider consolidating services")
        else:
            print("  ✅ Service count is reasonable")

        # Dominios
        print("\n🏢 Domain Completeness:")
        for domain, structure in metrics["domain_completeness"].items():
            complete = all(structure.values())
            status = "✅" if complete else "⚠️"
            print(f"  {status} {domain}:")
            for folder, exists in structure.items():
                icon = "✓" if exists else "✗"
                print(f"     {icon} {folder}")


# Uso
if __name__ == "__main__":
    metrics = ArchitectureMetrics(Path("."))
    metrics.print_report()
```

**Ejecutar**:
```bash
python scripts/analysis/architecture_metrics.py
```

---

## 📊 TABLERO DE SEGUIMIENTO

### Progreso General

| Fase | Duración | Estado | Progreso | Riesgo |
|------|----------|--------|----------|--------|
| 1. Preparación | 2 semanas | 🔵 Pendiente | 0% | 🟢 Bajo |
| 2. Core | 2 semanas | 🔵 Pendiente | 0% | 🟡 Medio |
| 3. E-commerce | 3 semanas | 🔵 Pendiente | 0% | 🟡 Medio-Alto |
| 4. Credit | 2 semanas | 🔵 Pendiente | 0% | 🟢 Bajo |
| 5. Nuevos Dominios | 3 semanas | 🔵 Pendiente | 0% | 🔴 Alto |
| 6. Orquestación | 2 semanas | 🔵 Pendiente | 0% | 🟡 Medio |
| 7. Limpieza | 2 semanas | 🔵 Pendiente | 0% | 🟢 Bajo |

**Total**: 16 semanas (~4 meses)

---

### Métricas Objetivo vs Actual

| Métrica | Actual | Objetivo | Estado |
|---------|--------|----------|--------|
| Archivos >500 líneas | 8 | 0 | 🔴 |
| Archivo más grande | 18,434 | <500 | 🔴 |
| Dependencias circulares | 7+ | 0 | 🔴 |
| Servicios | 29 | <20 | 🔴 |
| Cobertura tests | ~40% | >80% | 🟡 |
| Dominios completos | 1.5 | 4 | 🟡 |
| Tiempo de tests | ~5min | <2min | 🟡 |

---

## 🚦 CRITERIOS DE ACEPTACIÓN

### Por Fase

#### Fase 1: Preparación ✅
- [ ] Nueva estructura de directorios creada
- [ ] Interfaces base implementadas (`IRepository`, `IAgent`, etc.)
- [ ] Tests base configurados
- [ ] CI/CD funcionando con nueva estructura

#### Fase 2: Core ✅
- [ ] `knowledge_repository.py` dividido (18K → <500 líneas por archivo)
- [ ] Integraciones migradas con interfaces
- [ ] Zero dependencias circulares en `app/core/`
- [ ] Coverage >80% en `app/core/`

#### Fase 3: E-commerce ✅
- [ ] Dominio siguiendo estructura DDD completa
- [ ] Un solo agente de productos (3 → 1)
- [ ] Tests unitarios + integración + E2E pasando
- [ ] API endpoints funcionando sin regresiones

#### Fase 4: Credit ✅
- [ ] Dominio reorganizado siguiendo DDD
- [ ] Use cases reales implementados (no stubs)
- [ ] Tests >80%

#### Fase 5: Nuevos Dominios ✅
- [ ] Healthcare: Dominio completo con LangGraph
- [ ] Excelencia: Dominio completo con LangGraph
- [ ] Tests >75% para ambos

#### Fase 6: Orquestación ✅
- [ ] Super orchestrator robusto
- [ ] Routing accuracy >95%
- [ ] Tests E2E de domain switching pasando

#### Fase 7: Limpieza ✅
- [ ] Código duplicado eliminado
- [ ] ChromaDB eliminado (migrado 100% a pgvector)
- [ ] Performance +30% vs baseline
- [ ] Security audit completado

---

## 🎯 PRÓXIMOS PASOS INMEDIATOS

### Esta Semana (Semana 1)

1. **Lunes**: Revisar y aprobar esta propuesta
2. **Martes**: Crear estructura de directorios nueva
3. **Miércoles**: Implementar interfaces base (`app/core/interfaces/`)
4. **Jueves**: Configurar tests y CI/CD
5. **Viernes**: Ejecutar script de división de `knowledge_repository.py`

### Semana 2

1. **Lunes-Martes**: Migrar `app/utils/` y `app/core/`
2. **Miércoles-Jueves**: Migrar integraciones (Ollama, pgvector, WhatsApp)
3. **Viernes**: Sprint review y planning para Fase 3

---

## 📞 CONTACTO Y SOPORTE

### Preguntas Frecuentes

**Q: ¿Podemos hacer esto más rápido?**
A: Sí, pero con más riesgo. Recomendamos no comprimir más de 20% el cronograma.

**Q: ¿Qué pasa si necesitamos pausar la migración?**
A: Cada fase es autocontenida. Podemos pausar entre fases sin romper funcionalidad.

**Q: ¿Habrá downtime?**
A: No. La migración es gradual, el sistema actual sigue funcionando.

**Q: ¿Necesitamos más desarrolladores?**
A: Depende del equipo actual. Con 2-3 devs full-time, 16 semanas es realista.

---

## ✅ CHECKLIST DE INICIO

Antes de comenzar la migración, verificar:

- [ ] Toda la propuesta ha sido revisada y aprobada
- [ ] Equipo de desarrollo asignado (2-3 personas mínimo)
- [ ] Backup completo del código actual
- [ ] Branch de desarrollo creado (`git checkout -b architecture-migration`)
- [ ] Stakeholders informados del plan y cronograma
- [ ] Ambiente de staging disponible para testing
- [ ] CI/CD configurado
- [ ] Herramientas instaladas (`dependency-injector`, `pytest-asyncio`, etc.)

---

**Preparado por**: Claude Code (Arquitecto de Software)
**Fecha**: 2025-11-22
**Versión**: 1.0
**Próxima revisión**: Fin de Fase 1 (2 semanas)

---

## 📚 REFERENCIAS RÁPIDAS

- **Propuesta Arquitectónica Completa**: `docs/ARCHITECTURE_PROPOSAL.md`
- **Documentación LangGraph**: `docs/LangGraph.md`
- **Guía de Testing**: `docs/TESTING_GUIDE.md`
- **Guía SOLID**: `CLAUDE.md` (sección Code Quality)

---

**¿Listo para empezar? Ejecuta**:
```bash
# Iniciar migración
git checkout -b architecture-migration
python scripts/migration/phase1_setup.py
```
