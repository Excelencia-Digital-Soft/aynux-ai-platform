"""
API de administración para gestión del sistema multi-dominio
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.models.db.contact_domains import ContactDomain, DomainConfig
from app.services.domain_detector import get_domain_detector
from app.services.domain_manager import get_domain_manager
from app.services.super_orchestrator_service import get_super_orchestrator
from app.services.super_orchestrator_service_refactored import get_super_orchestrator_refactored
from app.config.settings import get_settings

router = APIRouter(prefix="/api/v1/admin/domains", tags=["domain-admin"])
logger = logging.getLogger(__name__)


# Helper to get orchestrator based on feature flag
def _get_orchestrator():
    """Get super orchestrator based on configuration."""
    settings = get_settings()
    use_refactored = getattr(settings, "USE_REFACTORED_ORCHESTRATOR", True)
    return get_super_orchestrator_refactored() if use_refactored else get_super_orchestrator()


# Pydantic models para API
class DomainAssignmentRequest(BaseModel):
    """Request para asignar dominio a contacto"""

    domain: str
    confidence: Optional[float] = 1.0
    method: str = "manual"


class DomainTestRequest(BaseModel):
    """Request para probar clasificación de mensaje"""

    message: str
    expected_domain: Optional[str] = None


class DomainConfigUpdate(BaseModel):
    """Request para actualizar configuración de dominio"""

    enabled: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    phone_patterns: Optional[List[str]] = None
    keyword_patterns: Optional[List[str]] = None
    priority: Optional[float] = None


@router.get("/")
async def list_domains(db_session: AsyncSession = Depends(get_async_db)):  # noqa: B008
    """Listar todos los dominios disponibles con su configuración"""
    try:
        # Obtener configuraciones de dominio
        query = select(DomainConfig)
        result = await db_session.execute(query)
        configs = result.scalars().all()

        # Obtener dominios disponibles del manager
        domain_manager = get_domain_manager()
        available_domains = domain_manager.get_available_domains()
        initialized_domains = domain_manager.get_initialized_domains()

        # Combinar información
        domains_info = []
        for config in configs:
            domain_info = config.to_dict()
            domain_info.update(
                {
                    "available": config.domain in available_domains,
                    "initialized": config.domain in initialized_domains,
                }
            )
            domains_info.append(domain_info)

        # Agregar dominios registrados que no tienen configuración
        configured_domains = {config.domain for config in configs}
        for domain in available_domains:
            if domain not in configured_domains:
                domains_info.append(
                    {
                        "domain": domain,
                        "enabled": "true",
                        "display_name": domain.title(),
                        "available": True,
                        "initialized": domain in initialized_domains,
                        "note": "No database configuration found",
                    }
                )

        return {
            "domains": domains_info,
            "total": len(domains_info),
            "available_count": len(available_domains),
            "initialized_count": len(initialized_domains),
        }

    except Exception as e:
        logger.error(f"Error listing domains: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{domain}/enable")
async def enable_domain(domain: str, db_session: AsyncSession = Depends(get_async_db)):  # noqa: B008
    """Habilitar un dominio específico"""
    try:
        # Verificar que el dominio existe
        domain_manager = get_domain_manager()
        if domain not in domain_manager.get_available_domains():
            raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")

        # Actualizar configuración en base de datos
        query = select(DomainConfig).where(DomainConfig.domain == domain)
        result = await db_session.execute(query)
        config = result.scalar_one_or_none()

        if config:
            config.enabled = "true"  # type: ignore[assignment]
        else:
            # Crear configuración básica si no existe
            config = DomainConfig(
                domain=domain,
                enabled="true",
                display_name=domain.title(),
                description=f"Auto-generated configuration for {domain}",
            )
            db_session.add(config)

        await db_session.commit()

        logger.info(f"Domain enabled: {domain}")
        return {"status": "success", "domain": domain, "enabled": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling domain {domain}: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{domain}/disable")
async def disable_domain(domain: str, db_session: AsyncSession = Depends(get_async_db)):  # noqa: B008
    """Deshabilitar un dominio específico"""
    try:
        # Verificar que no sea el dominio por defecto
        if domain == "ecommerce":
            raise HTTPException(status_code=400, detail="Cannot disable default domain 'ecommerce'")

        # Actualizar configuración
        query = select(DomainConfig).where(DomainConfig.domain == domain)
        result = await db_session.execute(query)
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail=f"Domain configuration '{domain}' not found")

        config.enabled = "false"  # type: ignore[assignment]
        await db_session.commit()

        logger.info(f"Domain disabled: {domain}")
        return {"status": "success", "domain": domain, "enabled": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling domain {domain}: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/contacts/{wa_id}")
async def get_contact_domain(wa_id: str, db_session: AsyncSession = Depends(get_async_db)):  # noqa: B008
    """Obtener dominio asignado a un contacto específico"""
    try:
        query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
        result = await db_session.execute(query)
        contact_domain = result.scalar_one_or_none()

        if not contact_domain:
            return {
                "wa_id": wa_id,
                "domain": None,
                "status": "not_assigned",
                "message": "Contact has no domain assigned",
            }

        return {"wa_id": wa_id, "domain_info": contact_domain.to_dict(), "status": "assigned"}

    except Exception as e:
        logger.error(f"Error getting contact domain for {wa_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/contacts/{wa_id}")
async def assign_contact_domain(
    wa_id: str,
    assignment: DomainAssignmentRequest,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Asignar dominio a un contacto manualmente"""
    try:
        # Verificar que el dominio existe
        domain_manager = get_domain_manager()
        if assignment.domain not in domain_manager.get_available_domains():
            raise HTTPException(status_code=400, detail=f"Domain '{assignment.domain}' not available")

        # Asignar usando el detector
        domain_detector = get_domain_detector()
        success = await domain_detector.assign_domain(
            wa_id=wa_id,
            domain=assignment.domain,
            method=assignment.method,
            confidence=assignment.confidence,
            db_session=db_session,
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to assign domain")

        logger.info(f"Domain manually assigned: {wa_id} -> {assignment.domain}")
        return {
            "status": "success",
            "wa_id": wa_id,
            "domain": assignment.domain,
            "confidence": assignment.confidence,
            "method": assignment.method,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning domain to {wa_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/contacts/{wa_id}")
async def remove_contact_domain(wa_id: str, db_session: AsyncSession = Depends(get_async_db)):  # noqa: B008
    """Remover asignación de dominio de un contacto"""
    try:
        query = select(ContactDomain).where(ContactDomain.wa_id == wa_id)
        result = await db_session.execute(query)
        contact_domain = result.scalar_one_or_none()

        if not contact_domain:
            raise HTTPException(status_code=404, detail=f"Contact '{wa_id}' has no domain assigned")

        await db_session.delete(contact_domain)
        await db_session.commit()

        # Ya se eliminó de la base de datos arriba, no hay cache que limpiar

        logger.info(f"Domain assignment removed: {wa_id}")
        return {"status": "success", "wa_id": wa_id, "action": "removed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing domain assignment for {wa_id}: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/stats")
async def get_domain_stats(db_session: AsyncSession = Depends(get_async_db)):  # noqa: B008
    """Obtener estadísticas generales del sistema multi-dominio"""
    try:
        # Estadísticas de contactos por dominio
        query = select(ContactDomain.domain, ContactDomain.assigned_method).order_by(ContactDomain.created_at.desc())
        result = await db_session.execute(query)
        contact_data = result.all()

        # Agrupar estadísticas
        domain_stats = {}
        method_stats = {}

        for domain, method in contact_data:
            # Por dominio
            if domain not in domain_stats:
                domain_stats[domain] = 0
            domain_stats[domain] += 1

            # Por método
            if method not in method_stats:
                method_stats[method] = 0
            method_stats[method] += 1

        # Estadísticas de los servicios
        domain_detector = get_domain_detector()
        domain_manager = get_domain_manager()
        super_orchestrator = _get_orchestrator()

        return {
            "contacts": {
                "total_assigned": len(contact_data),
                "by_domain": domain_stats,
                "by_method": method_stats,
            },
            "detector_stats": domain_detector.get_stats(),
            "orchestrator_stats": super_orchestrator.get_stats(),
            "available_domains": domain_manager.get_available_domains(),
            "initialized_domains": domain_manager.get_initialized_domains(),
        }

    except Exception as e:
        logger.error(f"Error getting domain stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/test-classification")
async def test_message_classification(test_request: DomainTestRequest):
    """Probar clasificación de un mensaje sin persistir"""
    try:
        super_orchestrator = _get_orchestrator()
        result = await super_orchestrator.test_classification(test_request.message)

        # Agregar evaluación si se proporcionó dominio esperado
        evaluation = None
        if test_request.expected_domain:
            evaluation = {
                "expected": test_request.expected_domain,
                "actual": result["domain"],
                "correct": result["domain"] == test_request.expected_domain,
                "confidence_threshold": result["confidence"] >= 0.7,
            }

        return {
            "message": test_request.message,
            "classification": result,
            "evaluation": evaluation,
            "timestamp": "now",  # Para testing
        }

    except Exception as e:
        logger.error(f"Error testing classification: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
async def domain_system_health():
    """Verificar estado de salud de todo el sistema multi-dominio"""
    try:
        domain_manager = get_domain_manager()
        health_status = await domain_manager.health_check_all()

        # Estadísticas adicionales
        domain_detector = get_domain_detector()
        super_orchestrator = _get_orchestrator()

        overall_status = "healthy"
        for _, status in health_status.items():
            if status.get("status") in ["error", "unavailable"]:
                overall_status = "degraded"
                break

        return {
            "overall_status": overall_status,
            "domains": health_status,
            "detector": {"status": "healthy", "stats": domain_detector.get_stats()},
            "orchestrator": {"status": "healthy", "stats": super_orchestrator.get_stats()},
            "timestamp": "now",
        }

    except Exception as e:
        logger.error(f"Error checking domain system health: {e}")
        return {"overall_status": "error", "error": str(e), "timestamp": "now"}


@router.delete("/cache/assignments")
async def clear_domain_assignments(
    wa_id: Optional[str] = Query(None, description="WhatsApp ID específico (opcional)"),
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Limpiar asignaciones de dominio de la base de datos"""
    try:
        if wa_id:
            # Limpiar asignación específica
            domain_detector = get_domain_detector()
            success = await domain_detector.clear_domain_assignment(wa_id, db_session)

            if success:
                message = f"Domain assignment cleared for {wa_id}"
                return {"status": "success", "action": "assignment_cleared", "wa_id": wa_id, "message": message}
            else:
                raise HTTPException(status_code=404, detail=f"No domain assignment found for {wa_id}")
        else:
            # Limpiar todas las asignaciones (operación peligrosa)
            from sqlalchemy import delete

            query = delete(ContactDomain)
            result = await db_session.execute(query)
            await db_session.commit()

            deleted_count = result.rowcount
            message = f"All domain assignments cleared ({deleted_count} entries)"
            logger.warning(message)

            return {
                "status": "success",
                "action": "all_assignments_cleared",
                "deleted_count": deleted_count,
                "message": message,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing domain assignments: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{domain}/config")
async def update_domain_config(
    domain: str,
    config_update: DomainConfigUpdate,
    db_session: AsyncSession = Depends(get_async_db),  # noqa: B008
):
    """Actualizar configuración de un dominio"""
    try:
        query = select(DomainConfig).where(DomainConfig.domain == domain)
        result = await db_session.execute(query)
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail=f"Domain configuration '{domain}' not found")

        # Actualizar campos proporcionados
        update_data = config_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(config, field, value)

        await db_session.commit()

        logger.info(f"Domain configuration updated: {domain}")
        return {"status": "success", "domain": domain, "updated_config": config.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating domain config for {domain}: {e}")
        await db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
