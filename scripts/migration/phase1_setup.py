#!/usr/bin/env python3
"""
Fase 1: Script de Setup - Preparación de Nueva Estructura

Este script crea la estructura base de directorios para la nueva arquitectura
sin modificar el código existente.

Uso:
    python scripts/migration/phase1_setup.py
    python scripts/migration/phase1_setup.py --dry-run  # Ver cambios sin ejecutar
"""

import argparse
from pathlib import Path
from typing import List, Dict
import sys


class Phase1Setup:
    """Configuración inicial de la nueva estructura arquitectónica"""

    def __init__(self, project_root: Path, dry_run: bool = False):
        self.project_root = project_root
        self.dry_run = dry_run
        self.created_dirs: List[Path] = []
        self.created_files: List[Path] = []

    def run(self):
        """Ejecuta el setup completo de Fase 1"""
        print("=" * 80)
        print("AYNUX - PHASE 1 SETUP: PREPARACIÓN DE ESTRUCTURA")
        print("=" * 80)
        print()

        if self.dry_run:
            print("🔍 DRY RUN MODE - No se crearán archivos reales")
            print()

        # 1. Crear estructura core
        print("📁 Creando estructura core...")
        self.create_core_structure()

        # 2. Crear estructura de dominios
        print("\n📁 Creando estructura de dominios...")
        self.create_domains_structure()

        # 3. Crear estructura de orquestación
        print("\n📁 Creando estructura de orquestación...")
        self.create_orchestration_structure()

        # 4. Crear estructura de integraciones
        print("\n📁 Creando estructura de integraciones...")
        self.create_integrations_structure()

        # 5. Crear estructura de tests
        print("\n📁 Creando estructura de tests...")
        self.create_tests_structure()

        # 6. Crear archivos de configuración
        print("\n📄 Creando archivos de configuración base...")
        self.create_config_files()

        # 7. Resumen
        self.print_summary()

    def create_core_structure(self):
        """Crea estructura app/core/"""
        core_structure = {
            "app/core": [
                "__init__.py",
                "domain/__init__.py",
                "domain/events.py",
                "domain/entities.py",
                "domain/value_objects.py",
                "domain/exceptions.py",
                "infrastructure/__init__.py",
                "infrastructure/circuit_breaker.py",
                "infrastructure/retry.py",
                "infrastructure/rate_limiter.py",
                "infrastructure/monitoring.py",
                "interfaces/__init__.py",
                "interfaces/repository.py",
                "interfaces/agent.py",
                "interfaces/llm.py",
                "interfaces/vector_store.py",
                "interfaces/cache.py",
                "shared/__init__.py",
                "shared/cache.py",
                "shared/logger.py",
                "shared/validators.py",
                "shared/formatters.py",
                "config/__init__.py",
                "config/settings.py",
                "config/database.py",
                "config/redis.py",
                "config/llm.py",
            ]
        }

        for base_dir, files in core_structure.items():
            for file in files:
                self._create_file(Path(base_dir) / file)

    def create_domains_structure(self):
        """Crea estructura app/domains/ para cada dominio"""
        domains = ["ecommerce", "credit", "healthcare", "excelencia"]

        domain_template = [
            "__init__.py",
            "domain/__init__.py",
            "domain/entities/__init__.py",
            "domain/value_objects/__init__.py",
            "domain/services/__init__.py",
            "domain/events/__init__.py",
            "application/__init__.py",
            "application/use_cases/__init__.py",
            "application/dto/__init__.py",
            "application/ports/__init__.py",
            "infrastructure/__init__.py",
            "infrastructure/persistence/__init__.py",
            "infrastructure/persistence/sqlalchemy/__init__.py",
            "infrastructure/persistence/redis/__init__.py",
            "infrastructure/external/__init__.py",
            "infrastructure/vector/__init__.py",
            "agents/__init__.py",
            "agents/graph.py",
            "agents/state.py",
            "agents/nodes/__init__.py",
            "agents/tools/__init__.py",
            "agents/prompts/__init__.py",
            "api/__init__.py",
            "api/routes.py",
            "api/schemas.py",
            "api/dependencies.py",
        ]

        for domain in domains:
            for template_file in domain_template:
                file_path = Path(f"app/domains/{domain}") / template_file
                self._create_file(file_path)

    def create_orchestration_structure(self):
        """Crea estructura app/orchestration/"""
        orchestration_structure = {
            "app/orchestration": [
                "__init__.py",
                "super_orchestrator.py",
                "domain_router.py",
                "context_manager.py",
                "state.py",
                "strategies/__init__.py",
                "strategies/ai_based_routing.py",
                "strategies/keyword_routing.py",
                "strategies/hybrid_routing.py",
            ]
        }

        for base_dir, files in orchestration_structure.items():
            for file in files:
                self._create_file(Path(base_dir) / file)

    def create_integrations_structure(self):
        """Crea estructura app/integrations/"""
        integrations_structure = {
            "app/integrations": [
                "__init__.py",
                "whatsapp/__init__.py",
                "whatsapp/client.py",
                "whatsapp/flows.py",
                "whatsapp/catalog.py",
                "whatsapp/models.py",
                "llm/__init__.py",
                "llm/ollama.py",
                "llm/base.py",
                "vector_stores/__init__.py",
                "vector_stores/pgvector.py",
                "vector_stores/base.py",
                "databases/__init__.py",
                "databases/postgresql.py",
                "databases/redis.py",
                "monitoring/__init__.py",
                "monitoring/langsmith.py",
                "monitoring/sentry.py",
            ]
        }

        for base_dir, files in integrations_structure.items():
            for file in files:
                self._create_file(Path(base_dir) / file)

    def create_tests_structure(self):
        """Crea estructura tests/"""
        tests_structure = {
            "tests": [
                "__init__.py",
                "conftest.py",
                "unit/__init__.py",
                "unit/core/__init__.py",
                "unit/core/test_validators.py",
                "unit/domains/__init__.py",
                "unit/domains/ecommerce/__init__.py",
                "unit/domains/ecommerce/domain/__init__.py",
                "unit/domains/ecommerce/application/__init__.py",
                "unit/domains/credit/__init__.py",
                "unit/orchestration/__init__.py",
                "integration/__init__.py",
                "integration/ecommerce/__init__.py",
                "integration/credit/__init__.py",
                "integration/healthcare/__init__.py",
                "e2e/__init__.py",
                "e2e/test_ecommerce_flow.py",
                "e2e/test_domain_switching.py",
            ]
        }

        for base_dir, files in tests_structure.items():
            for file in files:
                self._create_file(Path(base_dir) / file)

    def create_config_files(self):
        """Crea archivos de configuración inicial"""
        # Base interface file
        interface_content = '''"""
Interfaces base para el sistema Aynux

Estos protocols definen contratos que deben implementar
las capas de infraestructura.
"""
from typing import Protocol, Optional, List, Any
from abc import abstractmethod


class IRepository(Protocol):
    """Interface base para repositorios"""

    @abstractmethod
    async def find_by_id(self, id: Any) -> Optional[Any]:
        """Encuentra entidad por ID"""
        ...

    @abstractmethod
    async def save(self, entity: Any) -> Any:
        """Guarda entidad"""
        ...

    @abstractmethod
    async def delete(self, id: Any) -> bool:
        """Elimina entidad"""
        ...


class IAgent(Protocol):
    """Interface base para agentes LangGraph"""

    @abstractmethod
    async def execute(self, state: dict) -> dict:
        """Ejecuta el agente con el estado dado"""
        ...


class ILLM(Protocol):
    """Interface para LLM providers"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Genera texto usando el LLM"""
        ...


class IVectorStore(Protocol):
    """Interface para vector stores"""

    @abstractmethod
    async def add_embeddings(self, texts: List[str], metadatas: List[dict]) -> None:
        """Agrega embeddings al store"""
        ...

    @abstractmethod
    async def search(self, query: str, top_k: int = 5) -> List[Any]:
        """Busca documentos similares"""
        ...


class ICache(Protocol):
    """Interface para cache providers"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del cache"""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Guarda valor en cache"""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Elimina valor del cache"""
        ...
'''

        # conftest.py base
        conftest_content = '''"""
Pytest configuration and fixtures

Fixtures globales para tests del proyecto Aynux.
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_engine():
    """Create test database engine"""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost/aynux_test",
        echo=False
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    from unittest.mock import Mock
    mock = Mock()
    mock.generate.return_value = "Mocked LLM response"
    return mock
'''

        # README para nueva estructura
        readme_content = '''# Nueva Estructura Arquitectónica - Aynux

Esta carpeta contiene la nueva arquitectura basada en Domain-Driven Design (DDD).

## Estructura

```
app/
├── core/           # Núcleo compartido (interfaces, domain primitives)
├── domains/        # Dominios de negocio (DDD bounded contexts)
├── orchestration/  # Orquestación multi-dominio
├── integrations/   # Integraciones externas
└── api/            # API global (FastAPI)
```

## Principios

1. **Domain-Driven Design**: Cada dominio es independiente
2. **Clean Architecture**: Dependencias apuntan hacia adentro
3. **SOLID**: Código mantenible y extensible
4. **Hexagonal Architecture**: Infraestructura intercambiable

## Documentación

- `docs/ARCHITECTURE_PROPOSAL.md`: Propuesta completa
- `docs/MIGRATION_ACTION_PLAN.md`: Plan de migración

## Next Steps

1. Implementar interfaces base en `app/core/interfaces/`
2. Migrar dominio e-commerce
3. Implementar super orchestrator

---

**Status**: 🚧 En construcción (Fase 1)
'''

        files_to_create = {
            "app/core/interfaces/repository.py": interface_content,
            "tests/conftest.py": conftest_content,
            "app/NEW_ARCHITECTURE_README.md": readme_content,
        }

        for file_path, content in files_to_create.items():
            self._create_file(Path(file_path), content=content)

    def _create_file(self, file_path: Path, content: str = ""):
        """Crea archivo con contenido opcional"""
        full_path = self.project_root / file_path

        if self.dry_run:
            print(f"  [DRY RUN] Crearía: {file_path}")
            return

        # Crear directorio padre si no existe
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # No sobrescribir archivos existentes
        if full_path.exists():
            print(f"  ⚠️  Ya existe: {file_path}")
            return

        # Crear archivo
        if content:
            full_path.write_text(content)
        else:
            # Crear __init__.py vacío o con docstring básico
            if file_path.name == "__init__.py":
                module_name = file_path.parent.name
                content = f'"""\n{module_name.title()} module\n"""\n'
                full_path.write_text(content)
            else:
                full_path.touch()

        print(f"  ✅ Creado: {file_path}")
        self.created_files.append(full_path)

    def print_summary(self):
        """Imprime resumen de cambios"""
        print()
        print("=" * 80)
        print("RESUMEN DE CAMBIOS")
        print("=" * 80)
        print()
        print(f"📁 Archivos creados: {len(self.created_files)}")
        print()

        if self.dry_run:
            print("⚠️  Esto fue un DRY RUN - no se crearon archivos reales")
            print("   Ejecuta sin --dry-run para crear la estructura")
        else:
            print("✅ Estructura base creada exitosamente")
            print()
            print("📋 Próximos pasos:")
            print("  1. Revisar estructura creada: tree app/core/ app/domains/")
            print("  2. Implementar interfaces en app/core/interfaces/")
            print("  3. Configurar tests: pytest tests/ -v")
            print("  4. Revisar docs/MIGRATION_ACTION_PLAN.md para siguiente fase")

        print()
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Setup inicial para nueva arquitectura Aynux"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ver cambios sin ejecutar (modo simulación)"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Raíz del proyecto (default: directorio actual)"
    )

    args = parser.parse_args()

    # Validar que estamos en el directorio correcto
    if not (args.project_root / "app").exists():
        print("❌ Error: No se encuentra carpeta 'app'")
        print(f"   Directorio actual: {args.project_root}")
        print("   Ejecuta este script desde la raíz del proyecto Aynux")
        sys.exit(1)

    # Ejecutar setup
    setup = Phase1Setup(args.project_root, dry_run=args.dry_run)
    setup.run()


if __name__ == "__main__":
    main()
