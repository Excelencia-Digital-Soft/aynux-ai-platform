# ============================================================================
# SCOPE: GLOBAL
# Description: Admin API para gestionar modelos de IA disponibles. Permite
#              habilitar/deshabilitar modelos y configurar qué modelos ven
#              los usuarios. Soporta vLLM (local) y proveedores externos.
# Tenant-Aware: No - modelos son globales, visibilidad controlada por is_enabled.
# ============================================================================
"""
AI Models Admin API - Manage available AI models.

Provides endpoints for:
- Listing all AI models with filtering
- Seeding external provider models (OpenAI, Anthropic, DeepSeek)
- Toggling model visibility
- Updating model metadata
- Bulk operations (enable, disable, sort order)
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.async_db import get_async_db
from app.services.ai_model_service import AIModelService

router = APIRouter(tags=["AI Models"])


# ============================================================
# PYDANTIC SCHEMAS
# ============================================================


class AIModelCreate(BaseModel):
    """Schema for creating an AI model."""

    model_id: str = Field(..., min_length=1, max_length=255)
    provider: Literal["vllm", "openai", "anthropic", "deepseek", "kimi", "groq"]
    model_type: Literal["llm", "embedding"] = "llm"
    display_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = 4096
    supports_streaming: bool = True
    supports_functions: bool = False
    supports_vision: bool = False
    is_enabled: bool = False
    sort_order: int = 100


class AIModelUpdate(BaseModel):
    """Schema for updating an AI model."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_functions: bool | None = None
    supports_vision: bool | None = None
    is_enabled: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = None


class AIModelResponse(BaseModel):
    """Schema for AI model response."""

    id: str
    model_id: str
    provider: str
    model_type: str
    display_name: str
    description: str | None
    family: str | None
    parameter_size: str | None
    quantization_level: str | None
    context_window: int | None
    max_output_tokens: int | None
    supports_streaming: bool
    supports_functions: bool
    supports_vision: bool
    is_enabled: bool
    is_default: bool
    sort_order: int
    capabilities: dict
    sync_source: str
    last_synced_at: str | None
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


class AIModelListResponse(BaseModel):
    """Schema for AI model list response."""

    models: list[AIModelResponse]
    total: int
    enabled_count: int
    disabled_count: int


class SyncResult(BaseModel):
    """Schema for sync operation result."""

    added: int
    updated: int
    capability_updates: int = 0
    errors: list[str] = []


class CapabilityRefreshResult(BaseModel):
    """Schema for capability refresh operation result."""

    updated: int
    vision_detected: int
    functions_detected: int


class SeedResult(BaseModel):
    """Schema for seed operation result."""

    added: int
    skipped: int


class ModelSelectOption(BaseModel):
    """Schema for model select option (frontend consumption)."""

    value: str
    label: str
    provider: str | None
    family: str | None
    parameter_size: str | None
    supports_functions: bool
    supports_vision: bool
    max_tokens: int | None
    is_default: bool


class BulkEnableRequest(BaseModel):
    """Schema for bulk enable/disable request."""

    model_ids: list[str]


class SortOrderUpdate(BaseModel):
    """Schema for updating sort order."""

    id: str
    sort_order: int


class BulkSortOrderRequest(BaseModel):
    """Schema for bulk sort order update."""

    orders: list[SortOrderUpdate]


# ============================================================
# ENDPOINTS
# ============================================================


@router.get("", response_model=AIModelListResponse)
async def list_models(
    provider: str | None = Query(None, description="Filter by provider"),
    model_type: str | None = Query(None, description="Filter by type (llm/embedding)"),
    enabled_only: bool = Query(False, description="Only return enabled models"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all AI models with optional filtering.

    Admin endpoint - shows all models including disabled ones.
    """
    service = AIModelService.with_session(db)

    models = await service.list_models(
        provider=provider,
        model_type=model_type,
        enabled_only=enabled_only,
    )

    enabled = sum(1 for m in models if m.is_enabled)

    return AIModelListResponse(
        models=[AIModelResponse(**m.to_dict()) for m in models],
        total=len(models),
        enabled_count=enabled,
        disabled_count=len(models) - enabled,
    )


@router.get("/select-options", response_model=list[ModelSelectOption])
async def get_select_options(
    model_type: str = Query("llm", description="Model type (llm/embedding)"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get enabled models formatted for frontend Select components.

    Public endpoint - only returns enabled models.
    """
    service = AIModelService.with_session(db)
    models = await service.get_enabled_models(model_type=model_type)
    return [ModelSelectOption(**m) for m in models]


@router.get("/{model_id}", response_model=AIModelResponse)
async def get_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific AI model by ID."""
    service = AIModelService.with_session(db)
    model = await service.get_by_id(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )

    return AIModelResponse(**model.to_dict())


@router.post("", response_model=AIModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    data: AIModelCreate,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new AI model entry."""
    service = AIModelService.with_session(db)

    # Check if model_id already exists
    existing = await service.get_by_model_id(data.model_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model with ID '{data.model_id}' already exists",
        )

    model_data = data.model_dump()
    model_data["sync_source"] = "manual"

    model = await service.create(model_data)
    return AIModelResponse(**model.to_dict())


@router.put("/{model_id}", response_model=AIModelResponse)
async def update_model(
    model_id: UUID,
    data: AIModelUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    """Update an existing AI model."""
    service = AIModelService.with_session(db)

    update_data = data.model_dump(exclude_none=True)
    model = await service.update(model_id, update_data)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )

    return AIModelResponse(**model.to_dict())


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an AI model."""
    service = AIModelService.with_session(db)
    deleted = await service.delete(model_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )


@router.post("/{model_id}/toggle", response_model=AIModelResponse)
async def toggle_model_enabled(
    model_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle model enabled status."""
    service = AIModelService.with_session(db)
    model = await service.toggle_enabled(model_id)

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found",
        )

    return AIModelResponse(**model.to_dict())


@router.post("/refresh-capabilities", response_model=CapabilityRefreshResult)
async def refresh_model_capabilities(
    model_ids: list[str] | None = Query(
        None,
        description="Specific model IDs to refresh. If omitted, refreshes all models.",
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Refresh capability detection for AI models.

    Uses pattern matching to detect vision and function calling
    support for each model. Updates the database with detected capabilities.
    """
    service = AIModelService.with_session(db)
    result = await service.refresh_capabilities(model_ids=model_ids)
    return CapabilityRefreshResult(**result)


@router.post("/seed/external", response_model=SeedResult)
async def seed_external_models(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Seed database with known external provider models.

    Adds predefined models for OpenAI, Anthropic, and DeepSeek.
    Models are disabled by default - admin must enable them.
    """
    service = AIModelService.with_session(db)
    result = await service.seed_external_models()
    return SeedResult(**result)


@router.post("/bulk/enable")
async def bulk_enable_models(
    data: BulkEnableRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Enable multiple models at once."""
    service = AIModelService.with_session(db)
    model_uuids = [UUID(id_str) for id_str in data.model_ids]
    count = await service.enable_models(model_uuids)
    return {"updated": count}


@router.post("/bulk/disable")
async def bulk_disable_models(
    data: BulkEnableRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Disable multiple models at once."""
    service = AIModelService.with_session(db)
    model_uuids = [UUID(id_str) for id_str in data.model_ids]
    count = await service.disable_models(model_uuids)
    return {"updated": count}


@router.post("/bulk/sort-order")
async def bulk_update_sort_order(
    data: BulkSortOrderRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Update sort order for multiple models."""
    service = AIModelService.with_session(db)
    orders = [{"id": UUID(o.id), "sort_order": o.sort_order} for o in data.orders]
    count = await service.update_sort_order(orders)
    return {"updated": count}
