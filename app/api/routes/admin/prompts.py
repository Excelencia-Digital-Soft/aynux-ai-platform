"""
API Admin para gestión de prompts.

Endpoints:
- GET {API_V1_STR}/admin/prompts - Listar prompts
- GET {API_V1_STR}/admin/prompts/{key} - Obtener prompt específico
- POST {API_V1_STR}/admin/prompts - Crear prompt dinámico
- PUT {API_V1_STR}/admin/prompts/{key} - Actualizar prompt
- DELETE {API_V1_STR}/admin/prompts/{key} - Desactivar prompt
- GET {API_V1_STR}/admin/prompts/{key}/versions - Obtener versiones
- POST {API_V1_STR}/admin/prompts/{key}/rollback - Rollback a versión anterior
- GET {API_V1_STR}/admin/prompts/stats - Estadísticas del sistema
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_prompt_manager
from app.database.async_db import get_async_db
from app.services.ai_model_service import AIModelService
from app.api.schemas.prompts import (
    AnalyticsResponse,
    LockStatusResponse,
    PromptCreateRequest,
    PromptListResponse,
    PromptResponse,
    PromptUpdateRequest,
    PromptVersionResponse,
    RecentChange,
    RollbackRequest,
    StatsResponse,
    TemplateUsage,
    TestPromptRequest,
    TestPromptResponse,
    TokenUsage,
)
from app.prompts import PromptManager, PromptRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/prompts", tags=["Admin - Prompts"])


# ===== LIST & ANALYTICS ENDPOINTS =====


@router.get("/", response_model=PromptListResponse)
async def list_prompts(
    domain: str | None = Query(None, description="Filtrar por dominio (ej: product, intent)"),
    is_dynamic: bool | None = Query(None, description="Filtrar por tipo dinámico/estático"),
    is_active: bool | None = Query(None, description="Filtrar por estado activo"),
    source: str | None = Query(None, description="Filtrar por origen: file o database"),
    page: int = Query(1, ge=1, description="Número de página"),
    pageSize: int = Query(25, ge=1, le=100, description="Tamaño de página"),
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Lista todos los prompts disponibles con paginación."""
    try:
        all_prompts = await prompt_manager.list_prompts(domain=domain, is_dynamic=is_dynamic, is_active=is_active)

        if source:
            all_prompts = [p for p in all_prompts if p.get("source") == source]

        total = len(all_prompts)
        total_pages = (total + pageSize - 1) // pageSize if total > 0 else 1
        start = (page - 1) * pageSize
        paginated = all_prompts[start : start + pageSize]

        return PromptListResponse(
            items=[PromptResponse.from_prompt_dict(p) for p in paginated],
            total=total,
            page=page,
            page_size=pageSize,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Error listing prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing prompts: {str(e)}") from e


@router.get("/registry", response_model=dict[str, list[str]])
async def get_registry():
    """Obtiene todas las claves registradas en el PromptRegistry agrupadas por dominio."""
    try:
        all_keys = PromptRegistry.get_all_keys()
        by_domain: dict[str, list[str]] = {}

        for key in all_keys:
            domain = key.split(".")[0]
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(key)

        return by_domain
    except Exception as e:
        logger.error(f"Error getting registry: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting registry: {str(e)}") from e


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Get analytics about YAML prompts."""
    try:
        all_prompts = await prompt_manager.list_prompts(is_active=None)
        active_prompts = await prompt_manager.list_prompts(is_active=True)

        # Count by domain
        domains_count: dict[str, int] = {}
        for prompt in all_prompts:
            domain = prompt.get("key", "").split(".")[0] if prompt.get("key") else "unknown"
            domains_count[domain] = domains_count.get(domain, 0) + 1

        # Most used templates - currently no usage tracking
        most_used_templates: list[TemplateUsage] = []

        # Recent changes from DB prompts
        recent_changes: list[RecentChange] = []
        prompts_with_dates = [p for p in all_prompts if p.get("updated_at")]
        sorted_prompts = sorted(
            prompts_with_dates,
            key=lambda p: p.get("updated_at") or "",
            reverse=True,
        )[:10]

        for prompt in sorted_prompts:
            recent_changes.append(
                RecentChange(
                    prompt_key=prompt.get("key", "unknown"),
                    changed_at=prompt.get("updated_at", ""),
                    changed_by=prompt.get("created_by") or "system",
                    change_type="updated" if prompt.get("created_at") != prompt.get("updated_at") else "created",
                )
            )

        return AnalyticsResponse(
            total_prompts=len(all_prompts),
            active_prompts=len(active_prompts),
            domains_count=domains_count,
            most_used_templates=most_used_templates,
            recent_changes=recent_changes,
        )
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting analytics: {str(e)}") from e


# ===== AI MODELS ENDPOINT =====
# IMPORTANT: This must be defined BEFORE /{key:path} routes to avoid being captured


@router.get("/models")
async def get_available_models(
    model_type: str = Query("llm", description="Model type (llm/embedding)"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get available AI models for selection in UI.

    Returns enabled models formatted for frontend Select components.
    Used by YamlEditor and YamlTestDialog.
    """
    try:
        service = AIModelService(db)
        models = await service.get_enabled_models(model_type=model_type)
        return models
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting available models: {str(e)}",
        ) from e


# ===== TEST ENDPOINT =====


@router.post("/{key:path}/test", response_model=TestPromptResponse)
async def test_prompt(
    key: str,
    request: TestPromptRequest,
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test a prompt template by rendering it with provided variables and optionally calling the LLM.

    Returns the rendered template and, if a model is configured, the LLM response.
    """
    import time

    start_time = time.time()

    try:
        # Get the template
        template = await prompt_manager.get_template(key)
        if not template:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        # Render the template with provided variables
        try:
            # PromptTemplate.template is the raw string with {variables}
            rendered_prompt = template.template.format(**request.variables)
        except KeyError as e:
            return TestPromptResponse(
                success=False,
                errors=[f"Missing required variable: {e}"],
                execution_time=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return TestPromptResponse(
                success=False,
                errors=[f"Error rendering template: {str(e)}"],
                execution_time=(time.time() - start_time) * 1000,
            )

        # Determine model settings
        model_name = request.model or template.metadata.get("model", "default")
        temperature = request.temperature if request.temperature is not None else template.metadata.get("temperature", 0.7)
        max_tokens = request.max_tokens if request.max_tokens is not None else template.metadata.get("max_tokens", 1000)

        # If model is 'default' or not specified, just return the rendered prompt
        if model_name in ("default", "none", ""):
            return TestPromptResponse(
                success=True,
                rendered_prompt=rendered_prompt,
                model_response=None,
                execution_time=(time.time() - start_time) * 1000,
                warnings=["No model specified - returning rendered template only"],
            )

        # Try to call the LLM if a valid model is specified
        try:
            from app.integrations.llm import VllmLLM

            llm_provider = VllmLLM()
            llm = llm_provider.get_llm()

            # Call the LLM
            response = await llm.ainvoke(rendered_prompt)
            model_response = response.content if hasattr(response, "content") else str(response)

            # Calculate token usage (approximate)
            token_usage = TokenUsage(
                prompt_tokens=len(rendered_prompt.split()) * 4 // 3,  # Rough estimate
                completion_tokens=len(model_response.split()) * 4 // 3,
                total_tokens=0,
            )
            token_usage.total_tokens = token_usage.prompt_tokens + token_usage.completion_tokens

            return TestPromptResponse(
                success=True,
                rendered_prompt=rendered_prompt,
                model_response=model_response,
                execution_time=(time.time() - start_time) * 1000,
                token_usage=token_usage,
            )

        except ImportError:
            return TestPromptResponse(
                success=True,
                rendered_prompt=rendered_prompt,
                model_response=None,
                execution_time=(time.time() - start_time) * 1000,
                warnings=["LLM integration not available - returning rendered template only"],
            )
        except Exception as e:
            logger.warning(f"LLM call failed during test: {e}")
            return TestPromptResponse(
                success=True,
                rendered_prompt=rendered_prompt,
                model_response=None,
                execution_time=(time.time() - start_time) * 1000,
                warnings=[f"LLM call failed: {str(e)} - returning rendered template only"],
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing prompt: {e}")
        return TestPromptResponse(
            success=False,
            errors=[str(e)],
            execution_time=(time.time() - start_time) * 1000,
        )


# ===== LOCK MANAGEMENT ENDPOINTS (STUBS) =====


@router.get("/{key:path}/lock/status", response_model=LockStatusResponse)
async def get_lock_status(key: str):
    """Get the lock status of a prompt."""
    return LockStatusResponse(locked=False)


@router.post("/{key:path}/lock", response_model=LockStatusResponse)
async def lock_prompt_endpoint(key: str):
    """Lock a prompt for editing."""
    return LockStatusResponse(locked=False)


@router.delete("/{key:path}/lock")
async def unlock_prompt(key: str):
    """Unlock a prompt."""
    return {"message": "Prompt unlocked", "key": key}


@router.post("/{key:path}/lock/extend", response_model=LockStatusResponse)
async def extend_lock(key: str):
    """Extend the lock on a prompt."""
    return LockStatusResponse(locked=False)


# ===== VERSION MANAGEMENT ENDPOINTS =====


@router.get("/{key:path}/versions", response_model=list[PromptVersionResponse])
async def get_prompt_versions(
    key: str,
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Get all historical versions of a prompt."""
    try:
        versions = await prompt_manager.get_versions(key)

        if not versions:
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
async def rollback_prompt(
    key: str,
    request: RollbackRequest,
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Revert a prompt to a previous version."""
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


# ===== CRUD ENDPOINTS =====


@router.get("/{key:path}")
async def get_prompt(
    key: str,
    include_template: bool = Query(True, description="Incluir template completo"),
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Obtiene un prompt específico por su clave."""
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
async def create_prompt(
    request: PromptCreateRequest,
    created_by: str | None = Query("admin"),
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Crea un nuevo prompt dinámico."""
    try:
        existing = await prompt_manager.get_template(request.key)
        if existing:
            raise HTTPException(status_code=409, detail=f"Prompt already exists: {request.key}")

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
    updated_by: str | None = Query("admin", description="Usuario que actualiza"),
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Actualiza un prompt existente."""
    try:
        existing = await prompt_manager.get_template(key)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Prompt not found: {key}")

        updated_name = request.name or existing.name
        updated_template = request.template or existing.template
        updated_description = request.description or existing.description
        updated_metadata = {**existing.metadata, **(request.metadata or {})}

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
    """Desactiva un prompt (no lo elimina físicamente)."""
    try:
        # TODO: Implementar método deactivate en PromptManager
        return {"message": f"Prompt '{key}' deactivation not yet implemented", "key": key}
    except Exception as e:
        logger.error(f"Error deleting prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting prompt: {str(e)}") from e


# ===== SYSTEM ENDPOINTS =====


@router.get("/system/stats", response_model=StatsResponse)
async def get_system_stats(
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Obtiene estadísticas del sistema de prompts."""
    try:
        cache_stats = prompt_manager.get_stats()

        registry_info = {
            "total_keys": len(PromptRegistry.get_all_keys()),
            "domains": list(set(key.split(".")[0] for key in PromptRegistry.get_all_keys())),
        }

        system_info = {"version": "1.0.0", "manager_status": "active", "cache_enabled": True}

        return StatsResponse(cache_stats=cache_stats, registry_info=registry_info, system_info=system_info)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}") from e


@router.post("/cache/clear")
async def clear_cache(
    prompt_manager: PromptManager = Depends(get_prompt_manager),  # noqa: B008
):
    """Limpia el caché de prompts."""
    try:
        prompt_manager.clear_cache()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}") from e
