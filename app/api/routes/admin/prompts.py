"""
API Admin para gestión de prompts.

Endpoints:
- GET /api/v1/admin/prompts - Listar prompts
- GET /api/v1/admin/prompts/{key} - Obtener prompt específico
- POST /api/v1/admin/prompts - Crear prompt dinámico
- PUT /api/v1/admin/prompts/{key} - Actualizar prompt
- DELETE /api/v1/admin/prompts/{key} - Desactivar prompt
- GET /api/v1/admin/prompts/{key}/versions - Obtener versiones
- POST /api/v1/admin/prompts/{key}/rollback - Rollback a versión anterior
- GET /api/v1/admin/prompts/stats - Estadísticas del sistema
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.prompts import PromptManager, PromptRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/prompts", tags=["Admin - Prompts"])

# Instancia global del manager
prompt_manager = PromptManager()


# ===== MODELS =====


class PromptCreateRequest(BaseModel):
    """Request para crear un prompt."""

    key: str = Field(..., description="Clave única del prompt (ej: product.search.custom)")
    name: str = Field(..., description="Nombre descriptivo")
    template: str = Field(..., description="Template del prompt con {variables}")
    description: Optional[str] = Field(None, description="Descripción opcional")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata adicional")


class PromptUpdateRequest(BaseModel):
    """Request para actualizar un prompt."""

    name: Optional[str] = Field(None, description="Nuevo nombre")
    template: Optional[str] = Field(None, description="Nuevo template")
    description: Optional[str] = Field(None, description="Nueva descripción")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Nueva metadata")


class PromptResponse(BaseModel):
    """Response con información de un prompt."""

    id: str
    key: str
    name: str
    description: Optional[str]
    template: str
    version: str
    is_active: bool
    is_dynamic: bool
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str
    created_by: Optional[str]


class PromptListResponse(BaseModel):
    """Response con lista de prompts."""

    prompts: List[PromptResponse]
    total: int
    domain_filter: Optional[str]


class PromptVersionResponse(BaseModel):
    """Response con información de una versión."""

    id: str
    prompt_id: str
    version: str
    template: str
    performance_metrics: Dict[str, Any]
    is_active: bool
    created_at: str
    created_by: Optional[str]
    notes: Optional[str]


class StatsResponse(BaseModel):
    """Response con estadísticas del sistema."""

    cache_stats: Dict[str, Any]
    registry_info: Dict[str, Any]
    system_info: Dict[str, Any]


class RollbackRequest(BaseModel):
    """Request para hacer rollback."""

    version_id: str = Field(..., description="ID de la versión a restaurar")


# ===== ENDPOINTS =====


@router.get("/", response_model=PromptListResponse)
async def list_prompts(
    domain: Optional[str] = Query(None, description="Filtrar por dominio (ej: product, intent)"),
    is_dynamic: Optional[bool] = Query(None, description="Filtrar por tipo dinámico/estático"),
    is_active: Optional[bool] = Query(True, description="Filtrar por estado activo"),
):
    """
    Lista todos los prompts disponibles.

    Parámetros opcionales de filtrado:
    - domain: Filtrar por dominio específico
    - is_dynamic: Solo prompts dinámicos (editables) o estáticos (archivos)
    - is_active: Solo prompts activos
    """
    try:
        prompts = await prompt_manager.list_prompts(domain=domain, is_dynamic=is_dynamic, is_active=is_active)

        return PromptListResponse(
            prompts=[PromptResponse(**prompt) for prompt in prompts], total=len(prompts), domain_filter=domain
        )

    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing prompts: {str(e)}") from e


@router.get("/registry", response_model=Dict[str, List[str]])
async def get_registry():
    """
    Obtiene todas las claves registradas en el PromptRegistry.

    Útil para ver qué prompts están disponibles en el sistema.
    """
    try:
        all_keys = PromptRegistry.get_all_keys()

        # Agrupar por dominio
        by_domain: Dict[str, List[str]] = {}
        for key in all_keys:
            domain = key.split(".")[0]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(key)

        return by_domain

    except Exception as e:
        logger.error(f"Error getting registry: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting registry: {str(e)}") from e


@router.get("/{key:path}")
async def get_prompt(key: str, include_template: bool = Query(True, description="Incluir template completo")):
    """
    Obtiene un prompt específico por su clave.

    Args:
        key: Clave del prompt (ej: product.search.intent_analysis)
        include_template: Si False, no incluye el template completo (útil para listar)
    """
    try:
        template = await prompt_manager.get_template(key)

        if not template:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        response = template.to_dict()

        if not include_template:
            response.pop("template", None)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting prompt: {str(e)}") from e


@router.post("/", response_model=PromptResponse, status_code=201)
async def create_prompt(request: PromptCreateRequest, created_by: Optional[str] = Query("admin")):
    """
    Crea un nuevo prompt dinámico.

    Solo se pueden crear prompts dinámicos (editables en BD).
    Los prompts estáticos deben agregarse como archivos YAML.
    """
    try:
        # Validar que la clave no exista
        existing = await prompt_manager.get_template(request.key)
        if existing:
            raise HTTPException(status_code=409, detail=f"Prompt already exists: {request.key}")

        # Crear prompt
        prompt = await prompt_manager.save_dynamic_prompt(
            key=request.key,
            name=request.name,
            template=request.template,
            description=request.description,
            metadata=request.metadata,
            created_by=created_by,
        )

        return PromptResponse(**prompt.to_dict())

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error creating prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating prompt: {str(e)}") from e


@router.put("/{key:path}", response_model=PromptResponse)
async def update_prompt(
    key: str,
    request: PromptUpdateRequest,
    updated_by: Optional[str] = Query("admin", description="Usuario que actualiza"),
):
    """
    Actualiza un prompt existente.

    Solo se pueden actualizar prompts dinámicos.
    Crea automáticamente una versión histórica del prompt anterior.
    """
    try:
        # Verificar que exista
        existing = await prompt_manager.get_template(key)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        # Actualizar campos proporcionados
        updated_name = request.name or existing.name
        updated_template = request.template or existing.template
        updated_description = request.description or existing.description
        updated_metadata = {**existing.metadata, **(request.metadata or {})}

        # Guardar (crea versión automáticamente)
        prompt = await prompt_manager.save_dynamic_prompt(
            key=key,
            name=updated_name,
            template=updated_template,
            description=updated_description,
            metadata=updated_metadata,
            created_by=updated_by,
        )

        return PromptResponse(**prompt.to_dict())

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating prompt: {str(e)}") from e


@router.delete("/{key:path}")
async def delete_prompt(key: str):
    """
    Desactiva un prompt (no lo elimina físicamente).

    El prompt se marca como inactivo pero permanece en la BD para historial.
    """
    try:
        # TODO: Implementar método deactivate en PromptManager
        # Por ahora, retornar mensaje
        return {"message": f"Prompt '{key}' deactivation not yet implemented", "key": key}

    except Exception as e:
        logger.error(f"Error deleting prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting prompt: {str(e)}") from e


@router.get("/{key:path}/versions", response_model=List[PromptVersionResponse])
async def get_prompt_versions(key: str):
    """
    Obtiene todas las versiones históricas de un prompt.

    Útil para ver el historial de cambios y hacer rollback.
    """
    try:
        versions = await prompt_manager.get_versions(key)

        if not versions:
            # Verificar si el prompt existe
            template = await prompt_manager.get_template(key)
            if not template:
                raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

            return []

        return [PromptVersionResponse(**version) for version in versions]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting versions: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting versions: {str(e)}") from e


@router.post("/{key:path}/rollback")
async def rollback_prompt(key: str, request: RollbackRequest):
    """
    Revierte un prompt a una versión anterior.

    Crea una copia de respaldo de la versión actual antes de revertir.
    """
    try:
        success = await prompt_manager.rollback_to_version(key, request.version_id)

        if not success:
            raise HTTPException(status_code=400, detail="Rollback failed")

        return {"message": f"Prompt '{key}' rolled back successfully", "version_id": request.version_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error rolling back prompt: {str(e)}") from e


@router.get("/system/stats", response_model=StatsResponse)
async def get_system_stats():
    """
    Obtiene estadísticas del sistema de prompts.

    Incluye:
    - Métricas de caché
    - Información del registry
    - Estado del sistema
    """
    try:
        cache_stats = prompt_manager.get_stats()

        registry_info = {
            "total_keys": len(PromptRegistry.get_all_keys()),
            "domains": list(set(key.split(".")[0] for key in PromptRegistry.get_all_keys())),  # Dominios únicos
        }

        system_info = {"version": "1.0.0", "manager_status": "active", "cache_enabled": True}

        return StatsResponse(cache_stats=cache_stats, registry_info=registry_info, system_info=system_info)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}") from e


@router.post("/cache/clear")
async def clear_cache():
    """
    Limpia el caché de prompts.

    Útil para forzar recarga después de cambios en archivos YAML.
    """
    try:
        prompt_manager.clear_cache()
        return {"message": "Cache cleared successfully"}

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}") from e
