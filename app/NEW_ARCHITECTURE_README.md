# Nueva Estructura Arquitectónica - Aynux

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
