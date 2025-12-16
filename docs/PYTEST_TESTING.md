# Pytest Testing System - Aynux

Este documento describe el sistema de testing automatizado con pytest y pyright implementado en el proyecto Aynux.

## Tabla de Contenidos

1. [Resumen](#resumen)
2. [Configuración](#configuración)
3. [Estructura de Tests](#estructura-de-tests)
4. [Ejecutar Tests](#ejecutar-tests)
5. [Cobertura de Código](#cobertura-de-código)
6. [Type Checking](#type-checking)
7. [CI/CD](#cicd)

## Resumen

El proyecto ahora cuenta con:

- ✅ **Pytest** configurado con coverage reporting
- ✅ **Pyright** para type checking estático estricto
- ✅ **Conftest.py** con fixtures compartidos
- ✅ **Test utilities** (builders, factories, assertions)
- ✅ **GitHub Actions** workflow para CI/CD
- ✅ **Script de testing** (`run_pytest.sh`)

## Configuración

### Archivos de Configuración

**pytest.ini** - Configuración principal de pytest:
```ini
[pytest]
minversion = 6.0
testpaths = tests
asyncio_mode = auto

# Coverage reporting
addopts =
    --cov=app
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-report=xml
    --cov-branch
    --cov-fail-under=60
    --strict-markers
    -v
```

**pyrightconfig.json** - Type checking configuration:
```json
{
  "typeCheckingMode": "standard",
  "reportUnusedImport": "warning",
  "strictListInference": true,
  "strictDictionaryInference": true
}
```

**pyproject.toml** - Coverage settings:
```toml
[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/__pycache__/*"]
branch = true

[tool.coverage.report]
precision = 2
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError"
]
```

## Estructura de Tests

```
tests/
├── conftest.py                          # Fixtures compartidos globales
├── utils/                               # Utilidades de testing
│   ├── __init__.py
│   ├── builders.py                      # Builders para objetos de test
│   ├── factories.py                     # Factories para mocks
│   └── assertions.py                    # Assertions personalizadas
├── unit/                                # Tests unitarios
│   ├── domains/
│   │   ├── credit/
│   │   │   └── test_credit_use_cases.py # Tests de Credit use cases
│   │   └── shared/
│   │       ├── test_customer_use_cases.py
│   │       └── test_knowledge_use_cases.py
│   └── repositories/
│       └── test_product_repository.py    # Tests de repositorios
└── integration/                         # Tests de integración
    └── ...
```

## Ejecutar Tests

### Usando el Script

```bash
# Ejecutar todos los tests
./run_pytest.sh all

# Solo tests unitarios
./run_pytest.sh unit

# Tests con reporte de cobertura
./run_pytest.sh coverage

# Tests de Use Cases
./run_pytest.sh use-case

# Tests de Repositorios
./run_pytest.sh repository

# Re-ejecutar tests fallidos
./run_pytest.sh failed

# Ver ayuda
./run_pytest.sh help
```

### Usando pytest directamente

```bash
# Todos los tests
uv run pytest tests/

# Tests unitarios
uv run pytest tests/unit/ -v

# Tests con cobertura
uv run pytest tests/ --cov=app --cov-report=html

# Tests por marker
uv run pytest tests/ -m unit
uv run pytest tests/ -m use_case
uv run pytest tests/ -m repository

# Tests específicos
uv run pytest tests/unit/domains/credit/test_credit_use_cases.py -v
```

## Cobertura de Código

### Generar Reporte de Cobertura

```bash
# HTML report (recomendado)
./run_pytest.sh coverage

# Ver reporte en navegador
# El reporte se genera en htmlcov/index.html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Interpretar Resultados

```
Name                                    Stmts   Miss  Branch BrPart  Cover
---------------------------------------------------------------------------
app/domains/credit/application/...        85      5      12      2    92%
app/domains/shared/application/...       156     12      24      4    88%
---------------------------------------------------------------------------
TOTAL                                   2450    180     420     35    85%
```

**Objetivos de Cobertura:**
- **Mínimo aceptable**: 60% (configurado en pytest.ini)
- **Objetivo proyecto**: 80%+
- **Ideal**: 90%+ en código crítico (use cases, repositorios)

## Type Checking

### Ejecutar Pyright

```bash
# Usando script
./run_pytest.sh lint

# Directamente
uv run pyright app/

# Solo warnings
uv run pyright app/ --warnings

# Archivo específico
uv run pyright app/domains/credit/application/use_cases/
```

### Niveles de Type Checking

Pyright está configurado en modo **standard** con:
- ✅ Strict list/dict/set inference
- ✅ Warning en unused imports
- ✅ Warning en optional member access
- ✅ Warning en argument/call issues

## Markers Disponibles

Los tests están organizados con pytest markers:

| Marker | Descripción |
|--------|-------------|
| `@pytest.mark.unit` | Tests unitarios |
| `@pytest.mark.integration` | Tests de integración |
| `@pytest.mark.e2e` | Tests end-to-end |
| `@pytest.mark.use_case` | Tests de Use Cases |
| `@pytest.mark.repository` | Tests de Repositorios |
| `@pytest.mark.agent` | Tests de Agentes |
| `@pytest.mark.service` | Tests de Servicios |
| `@pytest.mark.api` | Tests de API endpoints |
| `@pytest.mark.slow` | Tests lentos |
| `@pytest.mark.smoke` | Tests de smoke testing |

### Ejemplo de Uso

```python
@pytest.mark.unit
@pytest.mark.use_case
@pytest.mark.asyncio
async def test_get_credit_balance_success():
    """Test successfully getting credit balance."""
    # ...
```

## CI/CD

### GitHub Actions

El workflow `.github/workflows/test.yml` se ejecuta automáticamente en:
- Push a `main`, `develop`, `claude/**`
- Pull requests a `main`, `develop`

**Pipeline de CI/CD:**
1. ✅ Setup Python 3.12 + uv
2. ✅ Install dependencies
3. ✅ Run pyright type checking
4. ✅ Run black/isort/ruff format checks
5. ✅ Run unit tests con coverage
6. ✅ Run integration tests
7. ✅ Upload coverage a Codecov
8. ✅ Comment coverage en PRs

### Local Pre-commit Checks

Antes de hacer commit, ejecuta:

```bash
# Formatear código
./run_pytest.sh format

# Verificar calidad
./run_pytest.sh lint

# Ejecutar tests
./run_pytest.sh unit
```

## Fixtures Disponibles

### Conftest.py Global

**Database fixtures:**
- `async_engine` - AsyncEngine para PostgreSQL
- `async_session` - AsyncSession para tests
- `db_session` - Session con auto-rollback

**Redis fixtures:**
- `redis_client` - Redis async client
- `mock_redis` - Mock Redis client

**LLM fixtures:**
- `mock_llm` - Mock LLM general
- `mock_ollama_llm` - Mock Ollama LLM

**Vector Store fixtures:**
- `mock_vector_store` - Mock vector store
- `mock_pgvector_service` - Mock pgvector

**Repository fixtures:**
- `mock_product_repository`
- `mock_customer_repository`
- `mock_conversation_repository`

**Agent fixtures:**
- `mock_agent_state` - Estado de agente
- `mock_base_agent` - Agente base
- `mock_orchestrator` - Orchestrator
- `mock_supervisor` - Supervisor

**Test Data fixtures:**
- `sample_product` - Producto de ejemplo
- `sample_customer` - Cliente de ejemplo
- `sample_conversation` - Conversación de ejemplo
- `sample_order` - Orden de ejemplo

## Test Utilities

### Builders (Fluent Interface)

```python
from tests.utils import ProductBuilder, CustomerBuilder

# Construir producto personalizado
product = (
    ProductBuilder()
    .with_name("Laptop Gaming")
    .with_price(1500.00)
    .out_of_stock()
    .build()
)

# Construir cliente
customer = (
    CustomerBuilder()
    .with_phone("+5491234567890")
    .with_name("John Doe")
    .inactive()
    .build()
)
```

### Factories (Quick Creation)

```python
from tests.utils import create_mock_product, create_mock_customer

# Crear objetos rápidamente con defaults
product = create_mock_product(product_id=1, price=99.99)
customer = create_mock_customer(phone="+5491234567890")
```

### Assertions Helpers

```python
from tests.utils import (
    assert_product_valid,
    assert_agent_state_valid,
    assert_repository_called_with,
)

# Validar estructura de producto
assert_product_valid(product)

# Validar estado de agente
assert_agent_state_valid(state)

# Verificar llamadas a repositorio
assert_repository_called_with(
    mock_repo, "get_by_id", product_id=1
)
```

## Escribir Nuevos Tests

### Template de Test Unitario

```python
"""
Unit tests for MyService.

Tests:
- Feature A
- Feature B
"""

import pytest
from unittest.mock import AsyncMock

from app.my_module import MyService


@pytest.fixture
def mock_dependency():
    """Create mock dependency."""
    return AsyncMock()


@pytest.mark.unit
@pytest.mark.service
@pytest.mark.asyncio
async def test_my_feature_success(mock_dependency):
    """Test successfully executing my feature."""
    # Arrange
    mock_dependency.method.return_value = "expected"
    service = MyService(dependency=mock_dependency)

    # Act
    result = await service.my_feature()

    # Assert
    assert result == "expected"
    mock_dependency.method.assert_called_once()


@pytest.mark.unit
@pytest.mark.service
@pytest.mark.asyncio
async def test_my_feature_error(mock_dependency):
    """Test error handling in my feature."""
    # Arrange
    mock_dependency.method.side_effect = Exception("Error")
    service = MyService(dependency=mock_dependency)

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await service.my_feature()

    assert "Error" in str(exc_info.value)
```

### Best Practices

1. **Seguir AAA Pattern**: Arrange - Act - Assert
2. **Un test, una cosa**: Cada test debe probar solo un comportamiento
3. **Nombres descriptivos**: `test_feature_condition_expected_result`
4. **Usar fixtures**: Reutilizar setup común
5. **Mock dependencias**: Aislar unidad bajo test
6. **Assertions claras**: Mensajes de error informativos
7. **Clean up**: Usar fixtures con yield para cleanup

## Próximos Pasos

### Tests por Implementar

**Prioridad Alta:**
- [ ] Agent tests (15+ agents)
- [ ] API endpoint tests (todos los endpoints)
- [ ] Integration service tests (LLM, Vector Stores)

**Prioridad Media:**
- [ ] E2E tests (flujos completos)
- [ ] Performance tests (load testing)

**Prioridad Baja:**
- [ ] Model validation tests
- [ ] Utility function tests

### Mejoras Planeadas

- [ ] Aumentar cobertura a 80%+
- [ ] Implementar property-based testing (Hypothesis)
- [ ] Mutation testing (mutmut)
- [ ] Contract testing para APIs externas
- [ ] Performance regression testing

## Recursos

- **Pytest Docs**: https://docs.pytest.org/
- **Pyright Docs**: https://github.com/microsoft/pyright
- **Coverage.py**: https://coverage.readthedocs.io/
- **Proyecto Documentation**: `docs/TESTING_GUIDE.md`

## Troubleshooting

### Tests Fallan con Import Errors

```bash
# Asegurar que estás en el virtualenv
uv sync

# Verificar que el path está correcto
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Coverage no Detecta Archivos

Verificar que `source = ["app"]` esté en `[tool.coverage.run]` en `pyproject.toml`.

### Pyright Reporta Muchos Errores

Pyright está en modo `standard`. Para reducir errores temporalmente:
1. Editar `pyrightconfig.json`
2. Cambiar `"typeCheckingMode": "basic"`
3. Aumentar gradualmente la strictness

---

**Última actualización**: 2025-01-24
**Autor**: Claude (Anthropic)
**Versión**: 1.0.0
