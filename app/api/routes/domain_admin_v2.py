"""
API de administración para gestión del sistema multi-dominio - VERSION 2

✅ CLEAN ARCHITECTURE - Migrated to Use Cases

This is the new version of domain_admin.py that uses Clean Architecture
Admin Use Cases instead of legacy services.

MIGRATION STATUS:
  ✅ Uses Admin Use Cases from app/domains/shared/application/use_cases/
  ✅ Follows Dependency Injection via DependencyContainer
  ✅ Proper error handling with HTTP exceptions
  ✅ Maintains API contract compatibility with v1

MIGRATED ENDPOINTS (Proof-of-Concept):
  - GET /api/v1/admin/domains/ → ListDomainsUseCase
  - POST /api/v1/admin/domains/{domain}/enable → EnableDomainUseCase
  - POST /api/v1/admin/domains/{domain}/disable → DisableDomainUseCase
  - GET /api/v1/admin/domains/contacts/{wa_id} → GetContactDomainUseCase
  - PUT /api/v1/admin/domains/contacts/{wa_id} → AssignContactDomainUseCase

PENDING MIGRATION (from v1):
  - DELETE /api/v1/admin/domains/contacts/{wa_id} → RemoveContactDomainUseCase
  - GET /api/v1/admin/domains/stats → GetDomainStatsUseCase
  - POST /api/v1/admin/domains/test-classification → Needs new Use Case
  - GET /api/v1/admin/domains/health → Needs monitoring Use Case
  - DELETE /api/v1/admin/domains/cache/assignments → ClearDomainAssignmentsUseCase
  - PUT /api/v1/admin/domains/{domain}/config → UpdateDomainConfigUseCase

TODO: Complete remaining endpoints migration and replace domain_admin.py
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.domains.shared.application.use_cases import (
    AssignContactDomainUseCase,
    DisableDomainUseCase,
    EnableDomainUseCase,
    GetContactDomainUseCase,
    ListDomainsUseCase,
)

router = APIRouter(prefix="/api/v1/admin/domains", tags=["domain-admin-v2"])
logger = logging.getLogger(__name__)


# ============================================================
# PYDANTIC MODELS
# ============================================================


class DomainAssignmentRequest(BaseModel):
    """Request para asignar dominio a contacto"""

    domain: str
    confidence: Optional[float] = 1.0
    method: str = "manual"


# ============================================================
# DOMAIN CONFIGURATION ENDPOINTS
# ============================================================


@router.get("/")
async def list_domains(
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Listar todos los dominios disponibles con su configuración.

    Uses: ListDomainsUseCase
    """
    try:
        # Create Use Case via dependency injection pattern
        # In production, use FastAPI Depends for cleaner code
        from app.core.container import DependencyContainer

        container = DependencyContainer()
        use_case = container.create_list_domains_use_case(db_session)

        # Execute Use Case
        result = await use_case.execute()

        return result

    except Exception as e:
        logger.error(f"Error listing domains: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{domain}/enable")
async def enable_domain(
    domain: str,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Habilitar un dominio específico.

    Uses: EnableDomainUseCase
    """
    try:
        # Create Use Case
        from app.core.container import DependencyContainer

        container = DependencyContainer()
        use_case = container.create_enable_domain_use_case(db_session)

        # Execute Use Case
        result = await use_case.execute(domain=domain)

        logger.info(f"Domain enabled: {domain}")
        return result

    except ValueError as e:
        # Use Case raises ValueError for business logic errors
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error enabling domain {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{domain}/disable")
async def disable_domain(
    domain: str,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Deshabilitar un dominio específico.

    Uses: DisableDomainUseCase
    """
    try:
        # Create Use Case
        from app.core.container import DependencyContainer

        container = DependencyContainer()
        use_case = container.create_disable_domain_use_case(db_session)

        # Execute Use Case
        result = await use_case.execute(domain=domain)

        logger.info(f"Domain disabled: {domain}")
        return result

    except ValueError as e:
        # Use Case raises ValueError for business logic errors (default domain, not found)
        if "Cannot disable" in str(e):
            raise HTTPException(status_code=400, detail=str(e)) from e
        else:
            raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error disabling domain {domain}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================
# CONTACT-DOMAIN ASSIGNMENT ENDPOINTS
# ============================================================


@router.get("/contacts/{wa_id}")
async def get_contact_domain(
    wa_id: str,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Obtener dominio asignado a un contacto específico.

    Uses: GetContactDomainUseCase
    """
    try:
        # Create Use Case
        from app.core.container import DependencyContainer

        container = DependencyContainer()
        use_case = container.create_get_contact_domain_use_case(db_session)

        # Execute Use Case
        result = await use_case.execute(wa_id=wa_id)

        return result

    except Exception as e:
        logger.error(f"Error getting contact domain for {wa_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/contacts/{wa_id}")
async def assign_contact_domain(
    wa_id: str,
    assignment: DomainAssignmentRequest,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """
    Asignar dominio a un contacto manualmente.

    Uses: AssignContactDomainUseCase
    """
    try:
        # Create Use Case
        from app.core.container import DependencyContainer

        container = DependencyContainer()
        use_case = container.create_assign_contact_domain_use_case(db_session)

        # Execute Use Case
        result = await use_case.execute(
            wa_id=wa_id,
            domain=assignment.domain,
            method=assignment.method,
            confidence=assignment.confidence,
        )

        logger.info(f"Domain manually assigned: {wa_id} -> {assignment.domain}")
        return result

    except ValueError as e:
        # Use Case raises ValueError for invalid domain
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error assigning domain to {wa_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================
# MIGRATION NOTES
# ============================================================

"""
MIGRATION PATTERN EXAMPLE:

BEFORE (Legacy - domain_admin.py):
```python
@router.post("/{domain}/enable")
async def enable_domain(domain: str, db_session: AsyncSession = Depends(get_async_db)):
    try:
        # Legacy: Direct service instantiation and database access
        domain_manager = get_domain_manager()
        if domain not in domain_manager.get_available_domains():
            raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

        # Direct database manipulation
        query = select(DomainConfig).where(DomainConfig.domain == domain)
        result = await db_session.execute(query)
        config = result.scalar_one_or_none()

        if config:
            config.enabled = "true"
        else:
            config = DomainConfig(...)
            db_session.add(config)

        await db_session.commit()
        return {"status": "success", "domain": domain, "enabled": True}
    except Exception as e:
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

AFTER (Clean Architecture - domain_admin_v2.py):
```python
@router.post("/{domain}/enable")
async def enable_domain(domain: str, db_session: AsyncSession = Depends(get_async_db)):
    try:
        # Clean: Use Case via Dependency Container
        container = DependencyContainer()
        use_case = container.create_enable_domain_use_case(db_session)

        # Single responsibility: Execute business logic
        result = await use_case.execute(domain=domain)

        return result
    except ValueError as e:
        # Use Case handles business validation
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Use Case handles database rollback
        raise HTTPException(status_code=500, detail=str(e))
```

BENEFITS:
✅ Single Responsibility: Endpoint only handles HTTP concerns
✅ Testability: Use Case can be tested independently
✅ Reusability: Use Case can be used from CLI, tests, other endpoints
✅ Maintainability: Business logic centralized in Use Case
✅ Dependency Injection: Easy to mock dependencies in tests
"""
