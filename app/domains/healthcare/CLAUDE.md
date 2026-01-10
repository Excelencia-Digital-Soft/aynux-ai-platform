# CLAUDE.md - Healthcare Domain

Guidance for Claude Code working with the Healthcare domain.

## Domain Overview

**Healthcare Domain** - Healthcare operations management within Aynux multi-domain platform.

| Feature | Description |
|---------|-------------|
| **Architecture** | Clean Architecture + DDD |
| **Domain Key** | `healthcare` |

## Critical Development Rules

### 1. Exception Handling - Always preserve stack traces
```python
# ✅ Good
except ValueError as e:
    raise HTTPException(status_code=400, detail="Invalid") from e
```

### 2. Modern Typing (Python 3.10+)
```python
# ✅ Use native types
def func(ids: list[int], data: dict[str, str] | None) -> None: ...
# ❌ Avoid: List, Dict, Optional from typing
```

### 3. UTC Timezone
```python
from datetime import UTC, datetime
now = datetime.now(UTC)  # ✅ Always UTC
```

### 4. pgvector with asyncpg - CRITICAL Bug
When using SQLAlchemy `text()` with asyncpg and pgvector, **NEVER use `::vector` cast syntax** with named parameters:

```python
# ❌ BROKEN - asyncpg confuses :param::type syntax
sql = text("SELECT * FROM docs WHERE 1 - (embedding <=> :vec::vector) > 0.5")

# ✅ CORRECT - use CAST() instead
sql = text("SELECT * FROM docs WHERE 1 - (embedding <=> CAST(:vec AS vector)) > 0.5")
```

## Domain Structure

```
healthcare/
├── agents/            # Healthcare agents
├── application/       # Use Cases, DTOs, Ports
├── domain/           # Entities, Value Objects, Domain Services
├── infrastructure/   # Repositories, External Services
└── services/         # Domain-specific services
```

## Database Tables

| Table | Purpose |
|-------|---------|
| patients | Patient records |
| appointments | Medical appointments |

## Architecture (Clean Architecture + DDD)

### Layer Structure

| Layer | Location | Contents |
|-------|----------|----------|
| **Domain** | `domain/` | Entities, Value Objects, Domain Services |
| **Application** | `application/` | Use Cases, DTOs, Ports (Protocol) |
| **Infrastructure** | `infrastructure/` | Repositories, External Services |

## Code Quality Standards

### SOLID Principles (Mandatory)

| Principle | Rule |
|-----------|------|
| **SRP** | One responsibility per class. Functions <20 lines. |
| **OCP** | Extend via inheritance, don't modify base. |
| **LSP** | Subclasses honor parent contracts. |
| **ISP** | Small, focused Protocol interfaces. |
| **DIP** | Depend on abstractions, inject dependencies. |

### Quality Rules
- **DRY**: Extract common logic, use base classes
- **KISS**: Simple solutions, no premature optimization
- **YAGNI**: Only implement current requirements

### Naming Conventions
- Classes: `PascalCase` (`PatientService`)
- Functions: `snake_case` (`get_patient`)
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`

### Size Limits
- Functions: <20 lines (max 50)
- Classes: <200 lines (max 500)

## Development Patterns

### Adding Use Cases
1. Create in `application/use_cases/`
2. Define Port (Protocol) in `ports/`
3. Implement Repository in `infrastructure/repositories/`
4. Register in `DependencyContainer`
5. Add FastAPI dependency in `app/api/dependencies.py`

### Agent Template Method Pattern
```python
class HealthcareAgent(BaseAgent):
    async def _process_internal(self, state: dict) -> dict:
        # Your logic here - process() wrapper handles:
        # - Input validation
        # - Error handling with stack traces
        # - Metrics collection
        pass
```

## Code Review Checklist

- [ ] SRP: Single responsibility per class?
- [ ] Functions <20 lines?
- [ ] Dependencies injected?
- [ ] Type hints complete?
- [ ] Error handling with `from e`?
- [ ] Tests can run independently?
